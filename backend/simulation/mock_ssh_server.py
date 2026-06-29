"""
NeuroSynapse Mock SSH Server – FIXED (No premature channel close)
"""

import socket
import threading
import random
import paramiko
import time


class MockRouterServer(paramiko.ServerInterface):
    def __init__(self):
        self.device_state = self._get_default_state()

    def _get_default_state(self):
        return {
            'cpu_usage': 25.0,
            'memory_usage': 40.0,
            'interface_status': {
                'GigabitEthernet0/1': {'status': 'up', 'speed': '1000Mbps', 'errors': 0},
                'GigabitEthernet0/2': {'status': 'up', 'speed': '1000Mbps', 'errors': 0},
                'GigabitEthernet0/3': {'status': 'down', 'speed': 'auto', 'errors': 0},
            },
            'health_status': 'HEALTHY',
            'active_incident': None,
        }

    def get_allowed_auths(self, username):
        return 'password'

    def check_auth_password(self, username, password):
        print(f"[MOCK ROUTER] Auth: {username}")
        return paramiko.AUTH_SUCCESSFUL

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_exec_request(self, channel, command):
        cmd = command.decode('utf-8').strip()
        print(f"[MOCK ROUTER] CMD: {cmd}")

        try:
            output = self._process_command(cmd)
            if output:
                channel.sendall(output.encode('utf-8'))
            channel.send_exit_status(0)
            print(f"[MOCK ROUTER] Command '{cmd}' completed")
        except Exception as e:
            print(f"[MOCK ROUTER] Error executing '{cmd}': {e}")
            try:
                channel.send_exit_status(1)
            except:
                pass
        finally:
            # ✅ Close the channel – this signals EOF to the client
            try:
                channel.close()
            except:
                pass

        return True     

    # --- command processing (unchanged) ---
    def _process_command(self, cmd):
        lower = cmd.lower()

        if lower in ['show cpu', 'system resource print', 'show processes cpu']:
            return self._cpu_output()
        if lower in ['show memory', 'show processes memory']:
            return self._memory_output()
        if lower in ['show interface', 'show interfaces', 'interface print']:
            return self._interface_output()

        if lower == 'inject_service_crash':
            self.device_state['cpu_usage'] = 98.0
            self.device_state['memory_usage'] = 88.0
            self.device_state['health_status'] = 'CRITICAL'
            self.device_state['active_incident'] = 'SERVICE_CRASH'
            return "INJECTED: SERVICE_CRASH (CPU: 98%, Memory: 88%)\r\n"
        if lower == 'inject_link_failure':
            self.device_state['interface_status']['GigabitEthernet0/1']['status'] = 'down'
            self.device_state['interface_status']['GigabitEthernet0/1']['errors'] = 999
            self.device_state['health_status'] = 'CRITICAL'
            self.device_state['active_incident'] = 'LINK_FAILURE'
            return "INJECTED: LINK_FAILURE (Gig0/1 down, 999 errors)\r\n"
        if lower == 'inject_ddos':
            self.device_state['cpu_usage'] = 99.0
            self.device_state['health_status'] = 'CRITICAL'
            self.device_state['active_incident'] = 'DDOS_ATTACK'
            return "INJECTED: DDOS_ATTACK (CPU: 99%)\r\n"
        if lower == 'reset_network':
            self.device_state = self._get_default_state()
            return "NETWORK RESET TO HEALTHY STATE\r\n"

        return f"% Invalid input: '{cmd}'\r\n"

    def _cpu_output(self):
        cpu = self.device_state['cpu_usage']
        if self.device_state['health_status'] != 'CRITICAL':
            cpu = max(5, min(45, cpu + random.uniform(-8, 12)))
        return f"""CPU utilization for five seconds: {cpu:.1f}%
CPU utilization for one minute: {cpu-3:.1f}%
CPU utilization for five minutes: {cpu-6:.1f}%
 PID  Runtime(ms)  Invoked   uSecs   5Sec   1Min   5Min TTY Process
   1        1234     5000     246   0.00%  0.00%  0.00%   0 Chunk Manager
  42       89000    12000    7416   {cpu*0.4:.2f}% {cpu*0.35:.2f}% {cpu*0.3:.2f}%   0 IP Input
"""

    def _memory_output(self):
        total = 4096
        used_pct = self.device_state['memory_usage']
        if self.device_state['health_status'] != 'CRITICAL':
            used_pct = max(20, min(60, used_pct + random.uniform(-8, 12)))
        used = total * used_pct / 100
        free = total - used
        return f"""                Head    Total(MB)   Used(MB)   Free(MB)  Lowest(MB) Largest(MB)
Processor   0x1F0     {total}       {used:.0f}       {free:.0f}       2800       2800
      I/O   0x1F0     {total}       {used*0.3:.0f}        {free*0.7:.0f}       2800       2800
"""

    def _interface_output(self):
        lines = ["Interface              IP-Address      OK? Method Status                Protocol"]
        for name, details in self.device_state['interface_status'].items():
            status = details['status']
            proto = 'up' if status == 'up' else 'down'
            lines.append(f"{name:22} 192.168.1.1     YES manual {status:8}            {proto}")
        return "\r\n".join(lines) + "\r\n"


# ====================== CLIENT HANDLER ======================
def handle_client(client_socket):
    transport = paramiko.Transport(client_socket)
    channels = []  # Prevent GC from closing channels prematurely
    try:
        host_key = paramiko.RSAKey.generate(2048)
        transport.add_server_key(host_key)
        server = MockRouterServer()
        transport.start_server(server=server)

        while transport.is_active():
            channel = transport.accept(30)
            if channel is None:
                time.sleep(0.2)
                # Clean out closed channels
                channels = [ch for ch in channels if not ch.closed]
                continue
            channels.append(channel)
    except Exception as e:
        if "Socket is closed" not in str(e) and "Connection reset" not in str(e):
            print(f"[MOCK ROUTER] Handler error: {e}")
    finally:
        try:
            transport.close()
        except:
            pass


def start_server():
    host = '0.0.0.0'
    port = 2222
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(10)

    print("=" * 60)
    print("  NEUROSYNAPSE MOCK ROUTER SSH SERVER (FIXED)")
    print("=" * 60)
    print(f"  Listening: {host}:{port}")
    print("=" * 60)

    try:
        while True:
            client, addr = sock.accept()
            print(f"[MOCK ROUTER] Connection from {addr}")
            t = threading.Thread(target=handle_client, args=(client,), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[MOCK ROUTER] Shutting down...")
    finally:
        sock.close()


if __name__ == '__main__':
    start_server()