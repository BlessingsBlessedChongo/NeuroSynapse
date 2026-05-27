"""
Vendor-agnostic SSH client.
Uses vendor profiles to translate device-specific commands.
Write once, configure for any supported router.
"""

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
from monitoring.vendor_profiles import get_profile, VENDOR_PROFILES


class NetworkDeviceConnector:
    """
    Connects to any supported network device via SSH.
    Automatically uses the correct commands based on the vendor profile.
    """
    
    def __init__(self, device):
        self.device = device
        self.profile = get_profile(device.device_type)
        self.connection = None
    
        self.netmiko_config = {
            'device_type': self.profile['device_type'],
            'host': device.ip_address,
            'port': device.ssh_port,
            'username': device.username,
            'password': device.password,
            'timeout': 15,
            'allow_agent': False,
            'look_for_keys': False,
            'auth_timeout': 15,
            'banner_timeout': 10,
        }
    
    def connect(self):
        """Establish SSH connection."""
        try:
            vendor_name = self.profile['name']
            print(f"[SSH] Connecting to {vendor_name} at {self.device.ip_address}:{self.device.ssh_port}...")
            self.connection = ConnectHandler(**self.netmiko_config)
            print(f"[SSH] Connected to {self.device.name}")
            return True
        except NetmikoTimeoutException:
            print(f"[SSH] TIMEOUT: {self.device.ip_address}")
            return False
        except NetmikoAuthenticationException:
            print(f"[SSH] AUTH FAILED: {self.device.ip_address}")
            return False
        except Exception as e:
            print(f"[SSH] Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close connection."""
        if self.connection:
            try:
                self.connection.disconnect()
            except:
                pass
            self.connection = None
    
    def collect_telemetry(self):
        """Collect telemetry using vendor-specific commands."""
        if not self.connection:
            if not self.connect():
                return None
        
        commands = self.profile['telemetry_commands']
        parser = self.profile['parser']
        telemetry = {}
        
        try:
            # CPU
            cpu_output = self._send(commands.get('cpu'))
            telemetry['cpu_usage'] = parser.parse_cpu(cpu_output) if cpu_output else None
            
            # Memory
            mem_output = self._send(commands.get('memory'))
            telemetry['memory_usage'] = parser.parse_memory(mem_output) if mem_output else None
            
            # Interfaces
            int_output = self._send(commands.get('interfaces'))
            telemetry['interface_status'] = parser.parse_interfaces(int_output) if int_output else {}
            
            # Packet loss
            pl_output = self._send(commands.get('packet_loss'))
            telemetry['packet_loss'] = parser.parse_packet_loss(pl_output) if pl_output else 0.0
            
            # Store raw output for debugging
            telemetry['raw_output'] = (
                f"=== CPU ===\n{cpu_output}\n"
                f"=== MEMORY ===\n{mem_output}\n"
                f"=== INTERFACES ===\n{int_output}\n"
            )
            
            print(f"[TELEMETRY] {self.device.name}: CPU={telemetry.get('cpu_usage')}%, "
                  f"Memory={telemetry.get('memory_usage')}%")
            
        except Exception as e:
            print(f"[TELEMETRY] Error: {e}")
        
        return telemetry
    
    def execute_healing_command(self, command):
        """Execute a healing command."""
        print(f"[HEALING] {self.device.name}: {command}")
        output = self._send(command)
        return {
            'success': output is not None and 'invalid' not in str(output).lower(),
            'command': command,
            'output': str(output) if output else 'No output',
        }
    
    def get_healing_actions(self, failure_type, **kwargs):
        """Get healing actions for a failure type with variables filled in."""
        actions = self.profile['healing_commands'].get(failure_type, [])
        
        # Fill in template variables like {interface} or {ip}
        filled_actions = []
        for action in actions:
            filled = action.copy()
            try:
                filled['command'] = action['command'].format(**kwargs)
            except KeyError:
                pass  # Keep original if variables not provided
            filled_actions.append(filled)
        
        return filled_actions
    
    def _send(self, command):
        """Send command with error handling."""
        if not self.connection:
            if not self.connect():
                return None
        
        try:
            return self.connection.send_command(command, read_timeout=10)
        except Exception as e:
            print(f"[SSH] Command failed: {e}")
            return None
    
    # ---------- Mock Server Support ----------
    
    def inject_failure(self, failure_type):
        """Inject simulated failure (mock server only)."""
        commands = {
            'service_crash': 'inject_service_crash',
            'link_failure': 'inject_link_failure',
            'ddos': 'inject_ddos',
        }
        command = commands.get(failure_type)
        if command:
            return self._send(command)
        return None
    
    def reset_network(self):
        """Reset mock network (mock server only)."""
        return self._send('reset_network')