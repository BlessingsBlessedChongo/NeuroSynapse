# monitoring/scheduler.py
import time
import threading
from monitoring.models import Device, Telemetry
from monitoring.connector import NetworkDeviceConnector


class TelemetryCollector:
    """
    Background collector that polls device telemetry every N seconds.
    """

    def __init__(self, interval: int = 5):
        self.interval = interval
        self.running = False
        self._thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._thread.start()
        print("[SCHEDULER] Collector thread started.")

    def stop(self):
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        print("[SCHEDULER] Collector stopped.")

    def _collection_loop(self):
        """Main loop: collect telemetry from all devices."""
        while self.running:
            print("[DEBUG] Loop iteration", flush=True)
            try:
                devices = Device.objects.filter(status__in=['ONLINE', 'DEGRADED'])
                print(f"[DEBUG] Found {devices.count()} devices: {[d.name for d in devices]}", flush=True)

                if not devices.exists():
                    # Create default mock device if none exist
                    device, created = Device.objects.get_or_create(
                        ip_address='127.0.0.1',
                        defaults={
                            'name': 'MockRouter01',
                            'device_type': 'cisco_ios',
                            'vendor': 'Mock',
                            'ssh_port': 2222,
                            'username': 'admin',
                            'password': 'anything',
                        }
                    )
                    if created:
                        print(f"[SCHEDULER] Created default device: {device.name}")
                    devices = Device.objects.filter(id=device.id)

                for device in devices:
                    connector = NetworkDeviceConnector(device)

                    # Collect telemetry
                    data = connector.collect_telemetry()

                    if data:
                        Telemetry.objects.create(
                            device=device,
                            cpu_usage=data.get('cpu_usage'),
                            memory_usage=data.get('memory_usage'),
                            packet_loss=data.get('packet_loss'),
                            interface_status=data.get('interface_status'),
                            raw_output=data.get('raw_output', ''),
                        )
                        print(f"[SCHEDULER] Saved telemetry from {device.name}")
                    else:
                        print(f"[SCHEDULER] Failed to collect from {device.name}")

                    connector.disconnect()

            except Exception as e:
                print(f"[SCHEDULER] Error: {e}")

            time.sleep(self.interval)


# Singleton instance – what the management command imports
collector = TelemetryCollector(interval=5)