"""
monitoring/connector.py
Robust SSH connector for NeuroSynapse.
Handles exec channels properly – waits for command completion.
"""

import time
import paramiko


class NetworkDeviceConnector:
    """
    Connects to a network device via SSH and collects telemetry.
    """

    def __init__(self, device):
        self.device = device
        self.client = None
        self._transport = None

    def connect(self):
        """Establish SSH connection to the device."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.device.ip_address,
                port=self.device.ssh_port,
                username=self.device.username,
                password=self.device.password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False,
            )
            return True
        except Exception as e:
            print(f"[CONNECTOR] Connection failed to {self.device.name}: {e}")
            return False

    def disconnect(self):
        """Close the SSH connection."""
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None

    def _execute_command(self, command, timeout=5):
        """
        Execute a single command and return the output.
        Waits for the remote command to finish before reading stdout.
        """
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            # Wait for the remote command to finish (with a timeout)
            exit_status = stdout.channel.recv_exit_status(timeout=timeout)
            output = stdout.read().decode('utf-8', errors='ignore')
            return output.strip()
        except Exception as e:
            print(f"[CONNECTOR] Error executing '{command}': {e}")
            return None

    def collect_telemetry(self):
        """
        Collect CPU, memory, and interface status from the device.
        Returns a dictionary with telemetry data, or None on failure.
        """
        if not self.client and not self.connect():
            return None

        telemetry_data = {
            'cpu_usage': None,
            'memory_usage': None,
            'packet_loss': 0.0,
            'interface_status': None,
            'raw_output': '',
        }

        # --- Collect CPU usage ---
        cpu_raw = self._execute_command('show cpu')
        if cpu_raw:
            telemetry_data['raw_output'] += cpu_raw + '\n'
            for line in cpu_raw.splitlines():
                if 'five seconds' in line.lower():
                    try:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            value = parts[1].replace('%', '').strip()
                            telemetry_data['cpu_usage'] = float(value)
                    except (ValueError, IndexError):
                        pass

        # --- Collect Memory usage ---
        mem_raw = self._execute_command('show memory')
        if mem_raw:
            telemetry_data['raw_output'] += mem_raw + '\n'
            for line in mem_raw.splitlines():
                if 'Processor' in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            total = float(parts[2])
                            used = float(parts[3])
                            if total > 0:
                                telemetry_data['memory_usage'] = (used / total) * 100
                        except (ValueError, IndexError):
                            pass

        # --- Collect Interface Status ---
        iface_raw = self._execute_command('show interface')
        if iface_raw:
            telemetry_data['raw_output'] += iface_raw + '\n'
            interfaces = {}
            lines = iface_raw.splitlines()[1:]  # skip header
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    name = parts[0]
                    status = parts[-1]  # 'up' or 'down'
                    interfaces[name] = {'status': status}
            telemetry_data['interface_status'] = interfaces

        return telemetry_data