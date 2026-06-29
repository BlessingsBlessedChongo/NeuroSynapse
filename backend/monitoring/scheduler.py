import time
import threading

from monitoring.models import Device, Telemetry
from monitoring.connector import get_connector, normalize_telemetry, attach_metrics_to_interface_status


class TelemetryCollector:
    def __init__(self, interval=5):
        self.interval = interval
        self.running = False
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self.running:
                return
            self.running = True
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            print("[SCHEDULER] Collector started.")

    def stop(self):
        with self._lock:
            self.running = False
        if self._thread:
            self._thread.join(timeout=10)
        print("[SCHEDULER] Collector stopped.")

    def collect_once(self):
        """Collect telemetry for all active devices (non-blocking helper)."""
        devices = Device.objects.filter(status__in=['ONLINE', 'DEGRADED'])
        if not devices.exists():
            Device.objects.get_or_create(
                ip_address='0.0.0.0',
                defaults={
                    'name': 'SimRouter',
                    'device_type': 'simulated',
                    'status': 'ONLINE',
                },
            )
            devices = Device.objects.filter(status__in=['ONLINE', 'DEGRADED'])

        saved = []
        for device in devices:
            connector = get_connector(device)
            try:
                raw = connector.collect_telemetry()
                if not raw:
                    print(f"[SCHEDULER] Failed to collect from {device.name}")
                    continue

                normalized = normalize_telemetry(raw)
                telemetry = Telemetry.objects.create(
                    device=device,
                    cpu_usage=normalized['cpu_usage'],
                    memory_usage=normalized['memory_usage'],
                    packet_loss=normalized['packet_loss'],
                    latency_ms=normalized['latency_ms'],
                    bandwidth_util=normalized['bandwidth_util'],
                    interface_status=attach_metrics_to_interface_status(normalized),
                    raw_output=normalized.get('raw_output', ''),
                )
                saved.append(telemetry)
                print(
                    f"[SCHEDULER] Saved telemetry from {device.name} "
                    f"(cpu={normalized['cpu_usage']}, loss={normalized['packet_loss']})"
                )
            except Exception as exc:
                print(f"[SCHEDULER] Error collecting from {device.name}: {exc}")
            finally:
                connector.disconnect()
        return saved

    def _loop(self):
        while self.running:
            try:
                self.collect_once()
            except Exception as e:
                print(f"[SCHEDULER] Error: {e}")
            time.sleep(self.interval)


collector = TelemetryCollector(interval=5)
