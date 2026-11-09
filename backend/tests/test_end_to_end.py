from monitoring.models import Device
from ai_engine.orchestrator import NeuroSynapseOrchestrator


def test_simulated_mape_k_cycle_runs():
    device, _ = Device.objects.get_or_create(
        ip_address='127.0.0.1',
        defaults={'name': 'PytestSim', 'device_type': 'simulated', 'status': 'ONLINE'},
    )
    result = NeuroSynapseOrchestrator().run_cycle(device=device, monitor=True)
    assert result['device'] == device.name
    assert result['telemetry_id'] is not None
