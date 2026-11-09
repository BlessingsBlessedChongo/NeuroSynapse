from types import SimpleNamespace

from healing.logging_system.healing_logger import write_incident_log


class ActionList(list):
    def order_by(self, _field):
        return self


def test_incident_log_is_structured(tmp_path, monkeypatch):
    import healing.logging_system.healing_logger as module
    monkeypatch.setattr(module, 'LOG_DIR', tmp_path)
    incident = SimpleNamespace(
        id=9001,
        detected_at=__import__('django.utils.timezone', fromlist=['now']).now(),
        failure_type='LINK_FAILURE',
        confidence_score=0.98,
        device=SimpleNamespace(ip_address='127.0.0.1'),
        interface_name='eth1',
        telemetry_snapshot=SimpleNamespace(
            id=1, cpu_usage=10, memory_usage=20, latency_ms=5,
            packet_loss=0, bandwidth_util=30,
        ),
        status='HEALED',
        healing_actions=ActionList([SimpleNamespace(
            action_type='REROUTE_TRAFFIC', command='ip link set eth1 up',
            sandbox_result='PASS', status='EXECUTED', execution_output='ok',
        )]),
    )
    path = write_incident_log(incident)
    content = path.read_text(encoding='utf-8')
    assert path.exists()
    assert '[STEP 1] MONITOR' in content
    assert '[STEP VERIFY]' in content
    assert 'REROUTE_TRAFFIC' in content
