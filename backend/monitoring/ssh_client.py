import paramiko

class NetworkDeviceConnector:
    def __init__(self, host, port, username, password):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = None

    def connect(self):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False,
                banner_timeout=10,
            )
            print(f"[SSH] ✓ Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[SSH] ✗ Connection failed: {e}")
            return False

    def _execute_command(self, command, timeout=8):
        if not self.client and not self.connect():
            return None
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            # Read all output AFTER the channel closes (EOF)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8', errors='ignore')
            return output.strip()
        except Exception as e:
            print(f"[EXEC] '{command}' failed: {e}")
            self.disconnect()
            return None

    def collect_telemetry(self):
        if not self.client and not self.connect():
            return None
        telemetry = {'raw_output': ''}

        cpu_raw = self._execute_command('show cpu')
        if cpu_raw:
            telemetry['raw_output'] += f"=== CPU ===\n{cpu_raw}\n"
            for line in cpu_raw.splitlines():
                if 'five seconds' in line.lower():
                    try:
                        val = line.split(':')[1].replace('%', '').strip()
                        telemetry['cpu_usage'] = float(val)
                    except:
                        pass

        mem_raw = self._execute_command('show memory')
        if mem_raw:
            telemetry['raw_output'] += f"=== MEMORY ===\n{mem_raw}\n"

        iface_raw = self._execute_command('show interface')
        if iface_raw:
            telemetry['raw_output'] += f"=== INTERFACES ===\n{iface_raw}\n"

        print(f"[TELEMETRY] {self.host}: CPU={telemetry.get('cpu_usage')}%")
        return telemetry

    def disconnect(self):
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None