#!/bin/bash
# NeuroSynapse - FRR container initialization script.
#
# Runs as the container entrypoint (see docker-compose.yml). Prepares the
# container so NeuroSynapse's backend can manage it exactly like a real
# router: SSH access as the 'admin' user, a stable management IP, and the
# FRR routing daemons (zebra/ospfd/staticd) running.
#
# This script is intentionally defensive: steps that are non-essential to
# SSH/telemetry connectivity (e.g. assigning an IP that may already be
# taken by Docker's own networking) are best-effort and never abort the
# whole startup.

set -uo pipefail

FRR_USER="${FRR_USER:-admin}"
FRR_PASSWORD="${FRR_PASSWORD:-admin}"
MGMT_IP="${MGMT_IP:-192.168.56.100/24}"
MGMT_IFACE="${MGMT_IFACE:-eth0}"

echo "[INIT] Starting NeuroSynapse FRR container setup..."

# ---------------------------------------------------------------------
# 1. Install SSH server + basic tools if not already present.
#    The base frrouting/frr image does not ship an SSH daemon.
# ---------------------------------------------------------------------
if ! command -v sshd >/dev/null 2>&1; then
    echo "[INIT] Installing openssh-server..."
    apt-get update -qq >/dev/null 2>&1 || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openssh-server iproute2 iptables sudo >/dev/null 2>&1
    if command -v sshd >/dev/null 2>&1; then
        echo "[OK] openssh-server installed"
    else
        echo "[WARN] openssh-server installation failed; SSH connectivity will not work"
    fi
else
    echo "[INFO] openssh-server already present"
fi

mkdir -p /var/run/sshd

if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    echo "[INIT] Generating SSH host keys..."
    ssh-keygen -A >/dev/null 2>&1 || echo "[WARN] Failed to generate SSH host keys"
fi

# Allow password authentication (default images often disable it).
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config 2>/dev/null || true
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config 2>/dev/null || true

# ---------------------------------------------------------------------
# 2. Create/update the management user NeuroSynapse authenticates as.
# ---------------------------------------------------------------------
if id "$FRR_USER" >/dev/null 2>&1; then
    echo "[INFO] User '$FRR_USER' already exists"
else
    echo "[INIT] Creating user '$FRR_USER'..."
    useradd -m -s /bin/bash "$FRR_USER" 2>/dev/null || useradd -m "$FRR_USER"
    usermod -aG sudo "$FRR_USER" 2>/dev/null || true
    # frrvty group grants access to vtysh without full root (best effort;
    # not all images define this group).
    usermod -aG frrvty "$FRR_USER" 2>/dev/null || true
fi

echo "${FRR_USER}:${FRR_PASSWORD}" | chpasswd
echo "[OK] Password set for user '$FRR_USER'"

# Passwordless sudo so 'systemctl restart frr' / 'iptables' healing
# commands issued over SSH by NeuroSynapse succeed without an interactive
# sudo prompt.
echo "${FRR_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${FRR_USER}"
chmod 0440 "/etc/sudoers.d/${FRR_USER}"

# ---------------------------------------------------------------------
# 3. Assign a stable management IP for NeuroSynapse to reach this router.
#    Best-effort: Docker's bridge networking may already own the primary
#    interface, so failure here must not abort container startup.
# ---------------------------------------------------------------------
if ip link show "$MGMT_IFACE" >/dev/null 2>&1; then
    if ip addr add "$MGMT_IP" dev "$MGMT_IFACE" 2>/dev/null; then
        echo "[OK] Assigned $MGMT_IP to $MGMT_IFACE"
    else
        echo "[WARN] Could not assign $MGMT_IP to $MGMT_IFACE (may already be configured)"
    fi
    ip link set "$MGMT_IFACE" up 2>/dev/null || true
else
    echo "[WARN] Interface $MGMT_IFACE not found; skipping management IP assignment"
fi

# ---------------------------------------------------------------------
# 4. Ensure FRR config files/permissions are correct.
# ---------------------------------------------------------------------
mkdir -p /etc/frr /var/log/frr /var/run/frr
chown -R frr:frr /etc/frr /var/log/frr /var/run/frr 2>/dev/null || true
chmod 640 /etc/frr/daemons /etc/frr/vtysh.conf 2>/dev/null || true

# ---------------------------------------------------------------------
# 5. Start SSH in the background.
# ---------------------------------------------------------------------
echo "[INIT] Starting SSH daemon..."
/usr/sbin/sshd
if pgrep -x sshd >/dev/null 2>&1; then
    echo "[OK] SSH daemon running on port 22"
else
    echo "[WARN] SSH daemon did not start; check container logs"
fi

# ---------------------------------------------------------------------
# 6. Start the FRR routing daemons (zebra, ospfd, staticd per ./daemons)
#    and keep the container alive in the foreground.
# ---------------------------------------------------------------------
echo "[INIT] Starting FRR daemons (zebra, ospfd, staticd)..."
if [ -x /usr/lib/frr/docker-start ]; then
    echo "[OK] Handing off to FRR's docker-start (foreground)"
    exec /usr/lib/frr/docker-start
elif command -v /etc/init.d/frr >/dev/null 2>&1; then
    /etc/init.d/frr start
    echo "[OK] FRR started via init.d; tailing logs to keep container alive"
    exec tail -F /var/log/frr/*.log 2>/dev/null || exec sleep infinity
else
    echo "[WARN] Could not locate FRR startup script; falling back to manual daemon start"
    /usr/lib/frr/zebra -d -A 127.0.0.1 2>/dev/null || true
    /usr/lib/frr/ospfd -d -A 127.0.0.1 2>/dev/null || true
    /usr/lib/frr/staticd -d -A 127.0.0.1 2>/dev/null || true
    echo "[INFO] NeuroSynapse FRR container ready"
    exec sleep infinity
fi
