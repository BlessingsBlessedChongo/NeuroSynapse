"""
Background task for collecting telemetry from network devices.
Runs every 5 seconds and saves data to the database.
"""

import time
import threading
from datetime import datetime
from monitoring.ssh_client import NetworkDeviceConnector
from monitoring.models import Device, Telemetry


class TelemetryCollector:
    """Collects telemetry from all managed devices on a schedule."""
    
    def __init__(self, interval=5):
        self.interval = interval
        self.running = False
        self.thread = None
        self.connectors = {}
    
    def start(self):
        """Start the telemetry collection loop in a background thread."""
        if self.running:
            print("[SCHEDULER] Already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.thread.start()
        print(f"[SCHEDULER] Started (interval: {self.interval}s)")
    
    def stop(self):
        """Stop the telemetry collection loop."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        for connector in self.connectors.values():
            connector.disconnect()
        print("[SCHEDULER] Stopped")
    
    def _get_or_create_connector(self, device):
        """Get existing connector or create a new one."""
        if device.id not in self.connectors:
            self.connectors[device.id] = NetworkDeviceConnector(
                host=device.ip_address,
                port=device.ssh_port,
                username=device.username,
                password=device.password,
            )
        return self.connectors[device.id]
    
    def _collection_loop(self):
        """Main loop: collect telemetry from all devices."""
        while self.running:
            try:
                devices = Device.objects.filter(status__in=['ONLINE', 'DEGRADED'])
                
                if not devices.exists():
                    # If no devices in DB, create default mock device
                    device, created = Device.objects.get_or_create(
                        ip_address='127.0.0.1',
                        defaults={
                            'name': 'MockRouter01',
                            'device_type': 'router',
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
                    connector = self._get_or_create_connector(device)
                    
                    # Collect telemetry
                    data = connector.collect_telemetry()
                    
                    if data:
                        # Save to database
                        Telemetry.objects.create(
                            device=device,
                            cpu_usage=data.get('cpu_usage'),
                            memory_usage=data.get('memory_usage'),
                            latency_ms=data.get('latency_ms'),
                            packet_loss=data.get('packet_loss'),
                            interface_status=data.get('interface_status'),
                            raw_output=data.get('raw_output', ''),
                        )
                        print(f"[SCHEDULER] Saved telemetry from {device.name}")
                    else:
                        print(f"[SCHEDULER] Failed to collect from {device.name}")
                
            except Exception as e:
                print(f"[SCHEDULER] Error in collection loop: {e}")
            
            # Wait for next interval
            time.sleep(self.interval)


# Global instance
collector = TelemetryCollector(interval=5)