"""Test failure classification with actual telemetry values."""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from monitoring.simulated_device import SimulatedDevice
from ai_engine.inference import engine


def test_failure(failure_type, **kwargs):
    sim = SimulatedDevice()
    sim.inject_failure(failure_type, **kwargs)
    t = sim.get_telemetry()
    
    print(f'\n=== {failure_type.upper()} TELEMETRY ===')
    print(f'  CPU: {t["cpu_usage"]}')
    print(f'  Memory: {t["memory_usage"]}')
    print(f'  Packet Loss: {t["packet_loss"]}')
    print(f'  Latency: {t["latency_ms"]}')
    print(f'  Bandwidth: {t["bandwidth_util"]}')
    print(f'  Errors: {t["error_count"]}')
    print(f'  OSPF: {t["ospf_neighbors"]}')
    print(f'  Interface Up: {t["interface_up_count"]}')
    
    diagnosis = engine.diagnose(t)
    print(f'  ---> Diagnosis: {diagnosis["failure_type"]}')
    print(f'  ---> Anomaly Confidence: {diagnosis["anomaly_confidence"]:.0%}')
    print(f'  ---> Classification Confidence: {diagnosis["classification_confidence"]:.0%}')
    
    return diagnosis


print('=' * 60)
print('FAILURE CLASSIFICATION TEST')
print('=' * 60)

# Test DDoS
test_failure('ddos', source_ip='10.0.0.99', destination_port=443, traffic_volume=75000)

# Test Service Crash
test_failure('service_crash', service_name='nginx', process_id=1234, destination_port=80)

# Test Link Failure
test_failure('link_failure', interface_name='ether1')

print('\n' + '=' * 60)