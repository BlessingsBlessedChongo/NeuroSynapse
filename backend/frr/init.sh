#!/bin/bash
# NeuroSynapse - FRR container initialization script.
#
# Runs as the container entrypoint (see docker-compose.yml). Prepares the
# container so NeuroSynapse's backend can manage it exactly like a real
# router: SSH access as the 'admin' user, a stable management IP, and the
# FRR routing daemons (zebra/ospfd/staticd) running.
#
# Robust & OS-Agnostic (Alpine Linux & Debian/Ubuntu compatible).

set -uo pipefail

FRR_USER="${FRR_USER:-admin}"
FRR_PASSWORD="${FRR_PASSWORD:-admin}"
MGMT_IP="${MGMT_IP:-192.168.56.100/24}"
MGMT_IFACE="${MGMT_IFACE:-eth0}"

echo "[INIT] Starting NeuroSynapse FRR container setup..."

# ---------------------------------------------------------------------
# 1. Install SSH server + basic tools if not already present.
# ---------------------------------------------------------------------
if ! command -v sshd >/dev/null 2>&1; then
    echo "[INIT] Installing SSH server and utility tools..."
    if command -v apk >/dev/null 2>&1; then
        # Alpine Linux
        apk add --no-cache openssh bash sudo iproute2 iptables openrc >/dev/null 2>&1 || true
    elif command -v apt-get >/dev/null 2>&1; then
        # Debian/Ubuntu
        apt-get update -qq >/dev/null 2>&1 || true
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openssh-server iproute2 iptables sudo >/dev/null 2>&1 || true
    fi

    if command -v sshd >/dev/null 2>&1; then
        echo "[OK] SSH server installed successfully"
    else
        echo "[WARN] SSH server installation failed; SSH connectivity will not work"
    fi
else
    echo "[INFO] openssh-server already present"
    # Ensure Alpine tooling is present even when sshd already ships in the image.
    if command -v apk >/dev/null 2>&1; then
        apk add --no-cache sudo iproute2 iptables openrc >/dev/null 2>&1 || true
    fi
fi

mkdir -p /var/run/sshd

# Generate SSH host keys if missing
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    echo "[INIT] Generating SSH host keys..."
    ssh-keygen -A >/dev/null 2>&1 || echo "[WARN] Failed to generate SSH host keys"
fi

# Configure SSH daemon settings
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config 2>/dev/null || true
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config 2>/dev/null || true

# ---------------------------------------------------------------------
# 2. Create/update the management user NeuroSynapse authenticates as.
# ---------------------------------------------------------------------
if id "$FRR_USER" >/dev/null 2>&1; then
    echo "[INFO] User '$FRR_USER' already exists"
else
    echo "[INIT] Creating user '$FRR_USER'..."
    if command -v adduser >/dev/null 2>&1 && [ -f /etc/alpine-release ]; then
        # Alpine syntax
        adduser -D -s /bin/bash "$FRR_USER" 2>/dev/null || adduser -D "$FRR_USER" 2>/dev/null || true
    else
        # Debian/Linux standard syntax
        useradd -m -s /bin/bash "$FRR_USER" 2>/dev/null || useradd -m "$FRR_USER" 2>/dev/null || true
    fi
fi

# Set password for the user
echo "${FRR_USER}:${FRR_PASSWORD}" | chpasswd
echo "[OK] Password set for user '$FRR_USER'"

# Add user to sudo and frrvty groups if available
if command -v usermod >/dev/null 2>&1; then
    usermod -aG sudo "$FRR_USER" 2>/dev/null || true
    usermod -aG frrvty "$FRR_USER" 2>/dev/null || true
elif [ -f /etc/alpine-release ]; then
    addgroup "$FRR_USER" sudo 2>/dev/null || true
    addgroup "$FRR_USER" frrvty 2>/dev/null || true
fi

# Passwordless sudo for healing actions issued over SSH
mkdir -p /etc/sudoers.d
echo "${FRR_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${FRR_USER}"
chmod 0440 "/etc/sudoers.d/${FRR_USER}"

# ---------------------------------------------------------------------
# 3. Assign a stable management IP (best-effort).
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
# 5. Start SSH Daemon in the background.
# ---------------------------------------------------------------------
echo "[INIT] Starting SSH daemon..."
/usr/sbin/sshd
if pgrep -x sshd >/dev/null 2>&1; then
    echo "[OK] SSH daemon running on port 22"
else
    echo "[WARN] SSH daemon did not start; check container logs"
fi

# ---------------------------------------------------------------------
# 6. Start FRR routing daemons and hand off to foreground process.
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