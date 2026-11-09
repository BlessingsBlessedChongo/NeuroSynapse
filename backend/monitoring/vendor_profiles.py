"""
Vendor profiles for common network devices.

Each profile defines:
1. Commands to collect telemetry
2. Parsers to extract structured data from command output
3. Healing commands for each failure type (with optional verify_command
   used by the actuator to confirm a healing action actually worked)

To add a new vendor: just add a new profile here.
No other code needs to change.

--------------------------------------------------------------------------
ALPINE / FRR-IN-DOCKER NOTES
--------------------------------------------------------------------------
The 'frr' profile below targets FRRouting running inside an Alpine Linux
Docker container, reached over Netmiko SSH with device_type='linux'
(BusyBox / ash shell, usually as root).

Three Alpine-specific realities drove the changes here:

1. Alpine containers almost never run systemd. `systemctl` will not
   exist. Any service-restart command must fall back through
   OpenRC (`/etc/init.d/frr`) and finally to killing/reloading the FRR
   daemons directly.
2. `tc` and `iptables` are optional packages in a minimal Alpine image.
   Every command that depends on them checks `command -v <tool>` first
   and falls back to a plain `ip link` / `ip route` equivalent.
3. BusyBox's `ping` prints a slightly different summary line than
   iputils ping, so packet loss must be parsed with a BusyBox-aware
   regex rather than assumed from interface counts alone.
"""

import re


class BaseParser:
    """Base parser with common extraction methods."""

    @staticmethod
    def extract_number(text, pattern):
        """Extract a number using a regex pattern."""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def extract_percentage(text, pattern):
        """Extract a percentage value."""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace('%', ''))
        return None


# ============================================================
# ALPINE / FRR SHELL-COMMAND HELPERS
# ============================================================

def vtysh_cmd(*stages):
    """
    Build a single, correctly-quoted vtysh invocation from a sequence of
    vtysh command stages, e.g.:

        vtysh_cmd('configure terminal', 'interface eth0', 'no shutdown')
        -> 'vtysh -c "configure terminal" -c "interface eth0" -c "no shutdown"'

    Sending this as ONE Netmiko send_command() call avoids the classic
    bug where each `-c` stage gets sent as a separate shell command and
    loses vtysh's in-session context (the root cause of the FRR link
    failure healing bug: mixing vtysh config-mode commands with raw
    kernel-level `ip link` commands in the same command list).
    """
    parts = ' '.join(f'-c "{stage}"' for stage in stages if stage)
    return f'vtysh {parts}'.strip()


def guarded_command(tool, primary_cmd, fallback_cmd):
    """
    Build a POSIX-sh one-liner that only runs `primary_cmd` if `tool` is
    present on the Alpine container (checked via `command -v`), otherwise
    runs `fallback_cmd`. Runs as a single Netmiko send_command() call so
    the conditional executes atomically on-device.
    """
    return f'if command -v {tool} >/dev/null 2>&1; then {primary_cmd}; else {fallback_cmd}; fi'


def sudo_cmd(cmd):
    """
    Prefix a command with non-interactive sudo.

    The NeuroSynapse FRR container's init.sh provisions the SSH
    management user (default 'admin') with passwordless sudo
    (`/etc/sudoers.d/<user>` -> NOPASSWD:ALL) specifically so that
    privileged networking commands (ip link, iptables, tc, systemctl)
    can be run over a non-root SSH session. Docker-level
    `privileged: true` / `cap_add` on the container only grants
    capabilities to processes that run as root -- an unprivileged SSH
    login still gets `RTNETLINK answers: Operation not permitted` on
    `ip link ... down/up` without this. `-n` makes sudo fail fast
    instead of hanging on a password prompt if sudoers isn't set up as
    expected, so a misconfigured container fails loudly rather than
    silently blocking on stdin.
    """
    return f'sudo -n {cmd}'


def service_restart_command(service_name_placeholder='{service}'):
    """
    Alpine-safe, sudo-wrapped service restart / recover.

        Preference order for Alpine FRR Docker containers:
            1. rc-service <svc> restart (wrapped in timeout)
            2. /etc/init.d/<svc> start (recover without full OpenRC restart hang)
      3. Direct zebra/ospfd daemon start under /usr/lib/frr
      4. supervisorctl / systemctl / SIGHUP fallbacks

    Every branch runs under `sudo -n` since the SSH management user is
    non-root (passwordless sudo is provisioned by frr/init.sh).
    """
    svc = service_name_placeholder
    return (
        f"sudo -n sh -c '"
        f"(command -v rc-service >/dev/null 2>&1 && timeout 12 rc-service {svc} restart) "
        f">/dev/null 2>&1 || true; "
        f"(test -x /etc/init.d/{svc} && /etc/init.d/{svc} start) >/dev/null 2>&1 || true; "
        f"(command -v supervisorctl >/dev/null 2>&1 && supervisorctl restart {svc}) "
        f">/dev/null 2>&1 || true; "
        f"pgrep -x zebra >/dev/null 2>&1 || "
        f"(/usr/lib/frr/zebra -d -A 127.0.0.1 2>/dev/null || true); "
        f"pgrep -x ospfd >/dev/null 2>&1 || "
        f"(/usr/lib/frr/ospfd -d -A 127.0.0.1 2>/dev/null || true); "
        f"pgrep -x staticd >/dev/null 2>&1 || "
        f"(/usr/lib/frr/staticd -d -A 127.0.0.1 2>/dev/null || true); "
        f"pgrep -x zebra >/dev/null 2>&1 && echo RESTARTED || echo RESTART_FAILED'"
    )


def service_status_command(service_name_placeholder='{service}'):
    """
    Alpine-safe service status probe.

    Official FRR Alpine images ship an /etc/init.d/frr that calls Debian's
    ``status_of_proc``, which is missing on Alpine — so ``rc-service frr status``
    prints errors even when daemons are healthy. Prefer a process probe first.
    """
    svc = service_name_placeholder
    return (
        f"sh -c '"
        f"if pgrep -x zebra >/dev/null 2>&1 || pgrep -a zebra >/dev/null 2>&1; then echo active; "
        f"elif pgrep -a {svc} >/dev/null 2>&1; then echo active; "
        f"elif command -v supervisorctl >/dev/null 2>&1 && "
        f"supervisorctl status {svc} 2>/dev/null | grep -qi RUNNING; then echo active; "
        f"elif command -v rc-service >/dev/null 2>&1 && "
        f"rc-service {svc} status >/dev/null 2>&1; then echo active; "
        f"else echo inactive; fi"
        f"'"
    )


class CiscoParser(BaseParser):
    """Parses Cisco IOS command output."""

    def parse_cpu(self, output):
        return self.extract_percentage(output, r'five seconds:\s*(\d+)%')

    def parse_memory(self, output):
        total = self.extract_number(output, r'Total:\s*(\d+)')
        used = self.extract_number(output, r'Used:\s*(\d+)')
        if total and used and total > 0:
            return round((used / total) * 100, 1)
        return None

    def parse_interfaces(self, output):
        interfaces = {}
        lines = output.split('\n')
        current_iface = None

        for line in lines:
            iface_match = re.match(r'(\S+)\s+is\s+(up|down|administratively down)', line)
            if iface_match:
                name = iface_match.group(1)
                status = 'up' if iface_match.group(2) == 'up' else 'down'
                interfaces[name] = {'status': status, 'errors': 0}
                current_iface = name

            if current_iface and 'errors' in line.lower():
                errors_match = re.search(r'(\d+)\s+input errors', line)
                if errors_match:
                    interfaces[current_iface]['errors'] = int(errors_match.group(1))

        return interfaces

    def parse_packet_loss(self, interfaces_output):
        total_packets = 0
        total_errors = 0
        lines = interfaces_output.split('\n')

        for line in lines:
            packets_match = re.search(r'(\d+)\s+packets input', line)
            errors_match = re.search(r'(\d+)\s+input errors', line)
            if packets_match:
                total_packets += int(packets_match.group(1))
            if errors_match:
                total_errors += int(errors_match.group(1))

        if total_packets > 0:
            return round((total_errors / total_packets) * 100, 2)
        return 0.0


class MikroTikParser(BaseParser):
    """Parses MikroTik RouterOS command output."""

    def parse_cpu(self, output):
        return self.extract_number(output, r'cpu-load:\s*(\d+)')

    def parse_memory(self, output):
        free = self.extract_number(output, r'free-memory:\s*(\d+)')
        total = self.extract_number(output, r'total-memory:\s*(\d+)')
        if free is not None and total and total > 0:
            return round(((total - free) / total) * 100, 1)
        return None

    def parse_interfaces(self, output):
        interfaces = {}
        blocks = output.split('\n\n')

        for block in blocks:
            name_match = re.search(r'name="?([^"\s]+)"?', block)
            running_match = re.search(r'running=(\w+)', block)

            if name_match:
                name = name_match.group(1)
                status = 'up' if running_match and running_match.group(1).lower() == 'true' else 'down'
                interfaces[name] = {'status': status, 'errors': 0}

        return interfaces

    def parse_packet_loss(self, interfaces_output):
        interfaces = self.parse_interfaces(interfaces_output)
        down_count = sum(1 for iface in interfaces.values() if iface['status'] == 'down')
        total = len(interfaces) or 1
        return round((down_count / total) * 100, 1)


class JuniperParser(BaseParser):
    """Parses Juniper JunOS command output."""

    def parse_cpu(self, output):
        return self.extract_number(output, r'CPU\s+usage:\s*(\d+)')

    def parse_memory(self, output):
        total = self.extract_number(output, r'Total\s+memory:\s*(\d+)')
        used = self.extract_number(output, r'Used\s+memory:\s*(\d+)')
        if total and used and total > 0:
            return round((used / total) * 100, 1)
        return None

    def parse_interfaces(self, output):
        interfaces = {}
        lines = output.split('\n')
        for line in lines:
            match = re.match(r'(\S+)\s+(\d+)\s+\d+\s+\d+\s+\d+\s+(\S+)', line)
            if match:
                name = match.group(1)
                status = 'up' if match.group(3).lower() == 'up' else 'down'
                interfaces[name] = {'status': status, 'errors': 0}
        return interfaces

    def parse_packet_loss(self, interfaces_output):
        return 0.0


class HuaweiParser(BaseParser):
    """Parses Huawei VRP command output."""

    def parse_cpu(self, output):
        return self.extract_percentage(output, r'CPU\s+usage:\s*(\d+%)')

    def parse_memory(self, output):
        return self.extract_percentage(output, r'Memory\s+usage:\s*(\d+%)')

    def parse_interfaces(self, output):
        interfaces = {}
        lines = output.split('\n')
        for line in lines:
            match = re.match(r'(\S+)\s+current state\s*:\s*(\S+)', line)
            if match:
                name = match.group(1)
                status = 'up' if 'UP' in match.group(2).upper() else 'down'
                interfaces[name] = {'status': status, 'errors': 0}
        return interfaces

    def parse_packet_loss(self, interfaces_output):
        return 0.0


class FRRParser(BaseParser):
    """
    Parses FRRouting (FRR) command output collected from an Alpine Linux
    Docker container over a Netmiko `linux` (BusyBox/ash) SSH session.
    """

    # BusyBox ping summary line, e.g.:
    #   "4 packets transmitted, 4 packets received, 0% packet loss"
    #   "4 packets transmitted, 2 received, 50% packet loss"
    # (BusyBox sometimes omits the word "packets" before "received";
    # iputils ping on non-Alpine images also matches this pattern.)
    PING_LOSS_RE = re.compile(
        r'(\d+)\s+packets\s+transmitted,\s*(\d+)\s*(?:packets\s+)?received.*?'
        r'(\d+(?:\.\d+)?)%\s+packet\s+loss',
        re.IGNORECASE | re.DOTALL,
    )

    def parse_cpu(self, output: str):
        if not output:
            return None
        match = re.match(r'\s*([0-9]+\.?[0-9]*)', output.strip())
        if match:
            try:
                # Convert 1-min load average to pseudo CPU percentage
                val = float(match.group(1)) * 100.0
                return min(round(val, 1), 100.0)
            except ValueError:
                return None
        return None

    def parse_memory(self, output: str):
        if not output:
            return None
        for line in output.splitlines():
            if line.lower().startswith('mem:'):
                parts = re.split(r'\s+', line.strip())
                # BusyBox `free -m` on Alpine only reliably provides
                # total/used/free (3 numeric columns); iputils/procps
                # `free -m` provides the fuller 6-7 column layout with
                # an "available" column. Support both.
                try:
                    if len(parts) >= 7:
                        total = float(parts[1])
                        available = float(parts[6])
                        if total > 0:
                            return round(((total - available) / total) * 100, 1)
                    elif len(parts) >= 4:
                        total = float(parts[1])
                        used = float(parts[2])
                        if total > 0:
                            return round((used / total) * 100, 1)
                except (ValueError, IndexError):
                    return None
        return None

    def parse_interfaces(self, output: str):
        """
        Parse `ip -br link` output. Handles the Alpine/BusyBox quirk
        where the loopback interface reports state UNKNOWN (not UP or
        DOWN) even though it is fully functional -- UNKNOWN is mapped
        to 'up', and 'lo' is always treated as up regardless of the
        reported state token.
        """
        interfaces = {}
        if not output:
            return interfaces

        lines = [l.strip() for l in output.splitlines() if l.strip()]

        for line in lines:
            if (
                line.startswith('-')
                or line.startswith('ERROR:')
                or line.startswith('Traceback')
                or 'pattern not detected' in line.lower()
                or 'interface' in line.lower()
            ):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            name = parts[0].split('@', 1)[0]
            # Strip internal bookkeeping keys if they ever leak into
            # raw device output (defensive; normally injected later by
            # the connector layer, not present in `ip -br link`).
            if name.startswith('__') and name.endswith('__'):
                continue

            status_token = parts[1].lower()
            is_up = status_token == 'up' or status_token == 'unknown' or name == 'lo'
            interfaces[name] = {'status': 'up' if is_up else 'down', 'errors': 0}

        return interfaces

    def parse_packet_loss(self, output: str):
        """
        Parse packet loss from a BusyBox `ping` summary block:
            "4 packets transmitted, 4 packets received, 0% packet loss"

        Returns 0.0 (not None) whenever there is no loss, or whenever
        the ping output can't be parsed at all -- an unreachable/garbled
        result should never silently look like 100% loss to the ML
        pipeline, and a missing/erroring ping should not be conflated
        with confirmed packet loss.
        """
        if not output:
            return 0.0

        match = self.PING_LOSS_RE.search(output)
        if match:
            try:
                return float(match.group(3))
            except (ValueError, IndexError):
                return 0.0

        # Anything that isn't a recognizable ping summary (SSH error,
        # "bad address", empty string, truncated output, etc.) is
        # treated as "no loss data" rather than guessed at -- an
        # unparseable result must never be silently misread as either
        # 0% or 100% loss, since either false reading would feed a
        # confidently wrong signal into the ML pipeline.
        return 0.0


# ============================================================
# VENDOR PROFILES
# ============================================================

VENDOR_PROFILES = {
    'cisco_ios': {
        'name': 'Cisco IOS',
        'device_type': 'cisco_ios',
        'parser': CiscoParser(),
        'telemetry_commands': {
            'cpu': 'show processes cpu',
            'memory': 'show processes memory',
            'interfaces': 'show interfaces',
            'packet_loss': 'show interfaces',
        },
        'healing_commands': {
            'SERVICE_CRASH': [
                {
                    'action_type': 'RESTART_SERVICE',
                    'command': 'reload',
                    'description': 'Reload the device to restart all services',
                    'verify_command': 'show version',
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': 'interface {interface}\nno shutdown',
                    'description': 'Enable the specified interface',
                    'verify_command': 'show interfaces {interface}',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': 'access-list 100 deny ip host {ip} any',
                    'description': 'Block attacking IP via access list',
                    'verify_command': 'show access-list 100',
                },
                {
                    'action_type': 'UNBLOCK_SOURCE_IP',
                    'command': 'no access-list 100 deny ip host {ip} any',
                    'description': 'Remove the block once the attack subsides',
                    'verify_command': 'show access-list 100',
                },
            ],
        },
    },

    'mikrotik_routeros': {
        'name': 'MikroTik RouterOS',
        'device_type': 'mikrotik_routeros',
        'parser': MikroTikParser(),
        'telemetry_commands': {
            'cpu': 'system resource print',
            'memory': 'system resource print',
            'interfaces': 'interface print detail',
            'packet_loss': 'interface print detail',
        },
        'healing_commands': {
            'SERVICE_CRASH': [
                {
                    'action_type': 'RESTART_SERVICE',
                    'command': 'system reboot',
                    'description': 'Reboot the MikroTik device',
                    'verify_command': 'system resource print',
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': 'interface enable {interface}',
                    'description': 'Enable the specified interface',
                    'verify_command': 'interface print detail where name={interface}',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': 'ip firewall filter add chain=input src-address={ip} action=drop',
                    'description': 'Add firewall rule to block attacking IP',
                    'verify_command': 'ip firewall filter print where src-address={ip}',
                },
                {
                    'action_type': 'UNBLOCK_SOURCE_IP',
                    'command': 'ip firewall filter remove [find src-address={ip}]',
                    'description': 'Remove the firewall rule once the attack subsides',
                    'verify_command': 'ip firewall filter print where src-address={ip}',
                },
            ],
        },
    },

    'juniper_junos': {
        'name': 'Juniper JunOS',
        'device_type': 'juniper_junos',
        'parser': JuniperParser(),
        'telemetry_commands': {
            'cpu': 'show system processes summary',
            'memory': 'show system memory',
            'interfaces': 'show interfaces terse',
            'packet_loss': 'show interfaces terse',
        },
        'healing_commands': {
            'SERVICE_CRASH': [
                {
                    'action_type': 'RESTART_SERVICE',
                    'command': 'request system reboot',
                    'description': 'Reboot the Juniper device',
                    'verify_command': 'show system uptime',
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': 'configure\nset interfaces {interface} enable\ncommit',
                    'description': 'Enable the specified interface',
                    'verify_command': 'show interfaces terse {interface}',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': 'set firewall family inet filter block-attack term 1 from source-address {ip} then discard',
                    'description': 'Add firewall filter to block attacking IP',
                    'verify_command': 'show firewall filter block-attack',
                },
                {
                    'action_type': 'UNBLOCK_SOURCE_IP',
                    'command': 'delete firewall family inet filter block-attack term 1',
                    'description': 'Remove the firewall filter once the attack subsides',
                    'verify_command': 'show firewall filter block-attack',
                },
            ],
        },
    },

    'huawei_vrp': {
        'name': 'Huawei VRP',
        'device_type': 'huawei_vrp',
        'parser': HuaweiParser(),
        'telemetry_commands': {
            'cpu': 'display cpu-usage',
            'memory': 'display memory-usage',
            'interfaces': 'display interface',
            'packet_loss': 'display interface',
        },
        'healing_commands': {
            'SERVICE_CRASH': [
                {
                    'action_type': 'RESTART_SERVICE',
                    'command': 'reboot',
                    'description': 'Reboot the Huawei device',
                    'verify_command': 'display version',
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': 'interface {interface}\nundo shutdown',
                    'description': 'Enable the specified interface',
                    'verify_command': 'display interface {interface}',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': 'acl 3000\nrule deny ip source {ip} 0',
                    'description': 'Create ACL to block attacking IP',
                    'verify_command': 'display acl 3000',
                },
                {
                    'action_type': 'UNBLOCK_SOURCE_IP',
                    'command': 'acl 3000\nundo rule deny ip source {ip} 0',
                    'description': 'Remove the ACL rule once the attack subsides',
                    'verify_command': 'display acl 3000',
                },
            ],
        },
    },

    'generic': {
        'name': 'Generic Router (Mock/Unknown)',
        'device_type': 'generic',
        'parser': CiscoParser(),
        'telemetry_commands': {
            'cpu': 'show cpu',
            'memory': 'show memory',
            'interfaces': 'show interface',
            'packet_loss': 'show interface',
        },
        'healing_commands': {
            'SERVICE_CRASH': [
                {
                    'action_type': 'RESTART_SERVICE',
                    'command': 'systemctl restart {service}',
                    'description': 'Restart the crashed service',
                    'verify_command': 'systemctl is-active {service}',
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': 'ip link set dev {interface} up',
                    'description': 'Re-enable the failed interface',
                    'verify_command': 'ip link show {interface}',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': 'iptables -I INPUT 1 -s {ip} -j DROP',
                    'description': 'Block attacking IP address via iptables',
                    'verify_command': 'iptables -C INPUT -s {ip} -j DROP',
                },
            ],
        },
    },

    # ------------------------------------------------------------
    # FRRouting on Alpine Linux (Docker container), Netmiko linux/SSH
    # ------------------------------------------------------------
    'frr': {
        'name': 'FRRouting (FRR) - Alpine Docker',
        'device_type': 'frr',
        'parser': FRRParser(),
        'telemetry_commands': {
            'cpu': 'cat /proc/loadavg',
            'memory': 'free -m',
            'interfaces': 'ip -br link',
            # Process health — used to distinguish SERVICE_CRASH from LINK_FAILURE
            # when gateway ping fails because routing is down.
            'service': (
                'if pgrep -x zebra >/dev/null 2>&1; then echo FRR_UP; '
                'else echo FRR_DOWN; fi'
            ),
            'ospf': (
                "vtysh -c 'show ip ospf neighbor' 2>/dev/null || echo NO_OSPF"
            ),
            # BusyBox-compatible connectivity probe: ping the container's
            # default gateway; fall back to loopback so the command always
            # returns a parsable ping summary.
            'packet_loss': (
                'ping -c 4 -W 1 -q '
                '$(ip route show default 2>/dev/null | awk \'{print $3; exit}\') '
                '2>/dev/null || ping -c 4 -W 1 -q 127.0.0.1'
            ),
        },
        'healing_commands': {
            'SERVICE_CRASH': [
                {
                    'action_type': 'RESTART_SERVICE',
                    'command': service_restart_command('frr'),
                    'description': (
                        'Restart the FRR routing daemon on Alpine: '
                        'rc-service, then supervisorctl, then '
                        '/etc/init.d/frr, then SIGHUP to zebra.'
                    ),
                    'verify_command': service_status_command('frr'),
                },
                {
                    'action_type': 'RESTART_SERVICE',
                    'command': service_restart_command('{service}'),
                    'description': 'Restart specific target service (Alpine-safe)',
                    'verify_command': service_status_command('{service}'),
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': sudo_cmd('ip link set dev {interface} up'),
                    'description': (
                        'Bring target interface up at the kernel/netlink level '
                        '(requires iproute2; provisioned by frr/init.sh)'
                    ),
                    'verify_command': 'ip -br link show {interface}',
                },
                {
                    'action_type': 'RESTART_FRR_INTERFACE',
                    'command': vtysh_cmd('configure terminal', 'interface {interface}', 'no shutdown'),
                    'description': (
                        'Enable the interface from inside FRR via vtysh '
                        '(routing-protocol level; no sudo needed since the '
                        'management user is a member of the frrvty group '
                        'granted vtysh socket access by init.sh)'
                    ),
                    'verify_command': vtysh_cmd('show interface {interface}'),
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': guarded_command(
                        'iptables',
                        sudo_cmd('iptables -A INPUT -s {ip} -j DROP'),
                        sudo_cmd('ip route add blackhole {ip}'),
                    ),
                    'description': (
                        'Drop traffic from attacking source IP via iptables '
                        '(-A INPUT -s {ip} -j DROP); fall back to blackhole '
                        'route when iptables is not installed'
                    ),
                    'verify_command': guarded_command(
                        'iptables',
                        sudo_cmd('iptables -C INPUT -s {ip} -j DROP') + ' && echo blocked',
                        'ip route show table main | grep -q "blackhole {ip}" && echo blocked',
                    ),
                },
                {
                    'action_type': 'UNBLOCK_SOURCE_IP',
                    'command': guarded_command(
                        'iptables',
                        sudo_cmd('iptables -D INPUT -s {ip} -j DROP') + ' 2>/dev/null || true',
                        sudo_cmd('ip route del blackhole {ip}') + ' 2>/dev/null || true',
                    ),
                    'description': 'Remove the source-IP DROP rule or blackhole route during rollback',
                    'verify_command': guarded_command(
                        'iptables',
                        sudo_cmd('iptables -C INPUT -s {ip} -j DROP')
                        + ' 2>/dev/null && echo still-blocked || echo clear',
                        'ip route show table main | grep -q "blackhole {ip}" && echo still-blocked || echo clear',
                    ),
                },
                {
                    'action_type': 'CLEAR_TRAFFIC_SHAPING',
                    'command': guarded_command(
                        'tc',
                        sudo_cmd('tc qdisc del dev {interface} root') + ' 2>/dev/null || true',
                        'true',
                    ),
                    'description': 'Clear kernel traffic shaping if `tc` is installed (no-op otherwise)',
                    'verify_command': guarded_command(
                        'tc',
                        'tc qdisc show dev {interface}',
                        'echo "tc not installed"',
                    ),
                },
            ],
            'PERFORMANCE_DEGRADATION': [
                {
                    'action_type': 'CLEAR_CACHE',
                    'command': sudo_cmd('sh -c "sync; echo 3 > /proc/sys/vm/drop_caches"')
                    + ' 2>/dev/null || true',
                    'description': 'Flush pagecache (falls through silently if the container lacks permission)',
                    'verify_command': 'free -m',
                },
            ],
        },
    },

    # ------------------------------------------------------------
    # In-memory PythonRouter — commands are symbolic; connector maps
    # them to PythonRouter.heal() action types.
    # ------------------------------------------------------------
    'python_router': {
        'name': 'Python Router Simulator',
        'device_type': 'python_router',
        'parser': CiscoParser(),
        'telemetry_commands': {},
        'healing_commands': {
            'SERVICE_CRASH': [
                {
                    'action_type': 'RESTART_SERVICE',
                    'command': 'rc-service {service} restart',
                    'description': 'Restart crashed control-plane service (simulated)',
                    'verify_command': 'rc-service {service} status',
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': 'ip link set dev {interface} up',
                    'description': 'Bring failed interface up (simulated)',
                    'verify_command': 'ip -br link show {interface}',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': 'iptables -A INPUT -s {ip} -j DROP',
                    'description': 'Block attacking source IP (simulated ACL)',
                    'verify_command': 'iptables -C INPUT -s {ip} -j DROP',
                },
            ],
        },
    },
}


def get_profile(device_type):
    """Get the vendor profile for a device type."""
    return VENDOR_PROFILES.get(device_type, VENDOR_PROFILES['generic'])


def get_supported_vendors():
    """Return list of supported vendor device types."""
    return [
        {
            'device_type': key,
            'name': profile['name'],
        }
        for key, profile in VENDOR_PROFILES.items()
    ]