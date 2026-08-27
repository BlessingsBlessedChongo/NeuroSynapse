"""
Vendor profiles for common network devices.
Each profile defines:
1. Commands to collect telemetry
2. Parsers to extract structured data from command output
3. Healing commands for each failure type

To add a new vendor: just add a new profile here.
No other code needs to change.
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


class CiscoParser(BaseParser):
    """Parses Cisco IOS command output."""
    
    def parse_cpu(self, output):
        # Cisco: "CPU utilization for five seconds: 25%/0%"
        return self.extract_percentage(output, r'five seconds:\s*(\d+)%')
    
    def parse_memory(self, output):
        # Cisco: "Processor Pool Total: 4096 Used: 2048 Free: 2048"
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
            # Match interface name line: "GigabitEthernet0/1 is up, line protocol is up"
            iface_match = re.match(r'(\S+)\s+is\s+(up|down|administratively down)', line)
            if iface_match:
                name = iface_match.group(1)
                status = 'up' if iface_match.group(2) == 'up' else 'down'
                interfaces[name] = {'status': status, 'errors': 0}
                current_iface = name
            
            # Match error count
            if current_iface and 'errors' in line.lower():
                errors_match = re.search(r'(\d+)\s+input errors', line)
                if errors_match:
                    interfaces[current_iface]['errors'] = int(errors_match.group(1))
        
        return interfaces
    
    def parse_packet_loss(self, interfaces_output):
        """Calculate packet loss from interface stats."""
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
        # MikroTik: "cpu-load: 25" (in system resource print)
        return self.extract_number(output, r'cpu-load:\s*(\d+)')
    
    def parse_memory(self, output):
        # MikroTik: "free-memory: 3072KiB" and "total-memory: 4096KiB"
        free = self.extract_number(output, r'free-memory:\s*(\d+)')
        total = self.extract_number(output, r'total-memory:\s*(\d+)')
        if free is not None and total and total > 0:
            return round(((total - free) / total) * 100, 1)
        return None
    
    def parse_interfaces(self, output):
        interfaces = {}
        # MikroTik interface print detail output
        blocks = output.split('\n\n')
        
        for block in blocks:
            name_match = re.search(r'name="?([^"\s]+)"?', block)
            running_match = re.search(r'running=(\w+)', block)
            disabled_match = re.search(r'disabled=(\w+)', block)
            
            if name_match:
                name = name_match.group(1)
                status = 'up' if running_match and running_match.group(1).lower() == 'true' else 'down'
                interfaces[name] = {'status': status, 'errors': 0}
        
        return interfaces
    
    def parse_packet_loss(self, interfaces_output):
        # MikroTik doesn't always expose packet loss directly
        # Return 0 if all interfaces are up
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
        return 0.0  # Simplified


class HuaweiParser(BaseParser):
    """Parses Huawei VRP command output."""
    
    def parse_cpu(self, output):
        return self.extract_percentage(output, r'CPU\s+usage:\s*(\d+%)')
    
    def parse_memory(self, output):
        return self.extract_percentage(output, r'Memory\s+usage:\s*(\d+%)')
    
    def parse_interfaces(self, output):
        interfaces = {}
        lines = output.split('\n')
        current_iface = None
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
    """Parses FRRouting (FRR) command output."""

    def parse_cpu(self, output: str):
        # /proc/loadavg: "0.00 0.01 0.05 1/123 4567"
        match = re.match(r'\s*([0-9]+\.?[0-9]*)', output.strip())
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def parse_memory(self, output: str):
        # free -m output: look for line starting with Mem:
        for line in output.splitlines():
            if line.startswith('Mem:') or line.lower().startswith('mem:'):
                parts = re.split(r'\s+', line.strip())
                # expected: Mem: total used free shared buff/cache available
                if len(parts) >= 7:
                    try:
                        total = float(parts[1])
                        available = float(parts[6])
                        if total > 0:
                            return round(((total - available) / total) * 100, 1)
                    except Exception:
                        return None
        # fallback: try to find "available" value anywhere
        total = self.extract_number(output, r'Total:\s*(\d+)')
        available = self.extract_number(output, r'Available:\s*(\d+)')
        if total and available and total > 0:
            return round(((total - available) / total) * 100, 1)
        return None

    def parse_interfaces(self, output: str):
        interfaces = {}
        lines = [l for l in output.splitlines() if l.strip()]
        for line in lines:
            # Typical brief: "Interface    IP-Address    Status/Protocol"
            cols = re.split(r'\s{2,}|\t', line.strip())
            # If line looks like a header, skip
            if 'interface' in line.lower() and 'status' in line.lower():
                continue
            # try to find name and status token like up/down or up/up
            if len(cols) >= 2:
                name = cols[0]
                status_field = cols[-1]
                status = 'up' if 'up' in status_field.lower() else 'down'
                interfaces[name] = {'status': status, 'errors': 0}
        return interfaces

    def parse_packet_loss(self, interfaces_output: str):
        # Not provided directly; approximate via down interfaces
        if not interfaces_output:
            return 0.0
        interfaces = self.parse_interfaces(interfaces_output)
        down = sum(1 for v in interfaces.values() if v.get('status') == 'down')
        total = max(len(interfaces), 1)
        return round((down / total) * 100, 1)


# ============================================================
# VENDOR PROFILES
# ============================================================
# Each vendor profile maps:
#   - telemetry_commands: what commands to run for each metric
#   - parser: the parser class to use
#   - healing_commands: what commands to run for each failure type
#   - device_type: netmiko device_type value

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
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': 'interface {interface}\nno shutdown',
                    'description': 'Enable the specified interface',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': 'access-list 100 deny ip host {ip} any',
                    'description': 'Block attacking IP via access list',
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
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': 'interface enable {interface}',
                    'description': 'Enable the specified interface',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': 'ip firewall filter add chain=input src-address={ip} action=drop',
                    'description': 'Add firewall rule to block attacking IP',
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
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': 'configure\nset interfaces {interface} enable\ncommit',
                    'description': 'Enable the specified interface',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': 'set firewall family inet filter block-attack term 1 from source-address {ip} then discard',
                    'description': 'Add firewall filter to block attacking IP',
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
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': 'interface {interface}\nundo shutdown',
                    'description': 'Enable the specified interface',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': 'acl 3000\nrule deny ip source {ip} 0',
                    'description': 'Create ACL to block attacking IP',
                },
            ],
        },
    },
    
    'generic': {
        'name': 'Generic Router (Mock/Unknown)',
        'device_type': 'generic',
        'parser': CiscoParser(),  # Default parser
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
                    'command': 'restart service {service}',
                    'description': 'Restart the crashed service',
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': 'no shutdown',
                    'description': 'Re-enable the failed interface',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': 'block {ip}',
                    'description': 'Block attacking IP address',
                },
            ],
        },
    },
    'frr': {
        'name': 'FRRouting (FRR)',
        'device_type': 'frr',
        'parser': FRRParser(),
        'telemetry_commands': {
            'cpu': "cat /proc/loadavg",
            'memory': "free -m",
            'interfaces': "vtysh -c 'show interface brief'",
            'packet_loss': "vtysh -c 'show interface brief'",
        },
        'healing_commands': {
            'SERVICE_CRASH': [
                {
                    'action_type': 'RESTART_SERVICE',
                    'command': 'systemctl restart frr',
                    'description': 'Restart FRR service',
                },
            ],
            'LINK_FAILURE': [
                {
                    'action_type': 'REROUTE_TRAFFIC',
                    'command': "vtysh -c 'configure terminal' -c 'interface {interface}' -c 'no shutdown'",
                    'description': 'Bring interface back up',
                },
            ],
            'DDOS_ATTACK': [
                {
                    'action_type': 'BLOCK_SOURCE_IP',
                    'command': "iptables -A INPUT -s {ip} -j DROP",
                    'description': 'Drop packets from attacking IP',
                },
            ],
        },
    },
}


def get_profile(device_type):
    """Get the vendor profile for a device type.
    
    Args:
        device_type: 'cisco_ios', 'mikrotik_routeros', 'juniper_junos', 'huawei_vrp'
    
    Returns:
        Vendor profile dictionary
    """
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