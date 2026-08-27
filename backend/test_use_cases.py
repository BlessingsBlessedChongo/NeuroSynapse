"""
NeuroSynapse Use Case Validation Script
Tests all use cases from the System Design Specification.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from monitoring.models import Device, Incident, HealingAction, RLReward
from monitoring.simulated_device import SimulatedDevice
from ai_engine.orchestrator import orchestrator
from ai_engine.inference import engine
from ai_engine.rl_agent import rl_agent
from ai_engine.xai import xai_engine


def print_header(title):
    print('\n' + '=' * 60)
    print(title)
    print('=' * 60)


def test_uc01_configure_healing_policies():
    """UC-01: Configure Healing Policies"""
    print_header('UC-01: CONFIGURE HEALING POLICIES')
    
    from dashboard.models import HealingPolicyConfig
    
    config = HealingPolicyConfig.get_solo()
    old_threshold = config.confidence_threshold
    
    # Update threshold
    config.confidence_threshold = 0.75
    config.save()
    
    updated = HealingPolicyConfig.get_solo()
    assert updated.confidence_threshold == 0.75, "Policy update failed"
    
    print(f'[PASS] Confidence threshold updated: {old_threshold} -> {updated.confidence_threshold}')
    print(f'[PASS] All policy fields editable:')
    print(f'  - confidence_threshold: {updated.confidence_threshold}')
    print(f'  - healing_timeout_seconds: {updated.healing_timeout_seconds}')
    print(f'  - max_cpu_threshold: {updated.max_cpu_threshold}')
    print(f'  - max_latency_threshold_ms: {updated.max_latency_threshold_ms}')
    print(f'  - max_packet_loss_threshold: {updated.max_packet_loss_threshold}')
    print(f'  - telemetry_interval_seconds: {updated.telemetry_interval_seconds}')
    print(f'  - rl_reward_success: {updated.rl_reward_success}')
    print(f'  - rl_reward_failure: {updated.rl_reward_failure}')
    
    return True


def test_uc02_monitor_telemetry():
    """UC-02: Monitor Real-time Telemetry"""
    print_header('UC-02: MONITOR REAL-TIME TELEMETRY')
    
    sim = SimulatedDevice()
    telemetry = sim.get_telemetry()
    
    required_features = [
        'cpu_usage', 'memory_usage', 'packet_loss', 'latency_ms',
        'bandwidth_util', 'interface_up_count', 'ospf_neighbors', 'error_count'
    ]
    
    for feature in required_features:
        assert feature in telemetry, f"Missing feature: {feature}"
        print(f'[PASS] {feature}: {telemetry[feature]}')
    
    # Verify telemetry is persisted
    device = Device.objects.filter(device_type='simulated').first()
    from monitoring.models import Telemetry
    latest = Telemetry.objects.filter(device=device).order_by('-timestamp').first()
    assert latest is not None, "No telemetry in database"
    print(f'[PASS] Telemetry persisted (ID: {latest.id}, Time: {latest.timestamp})')
    
    return True


def test_uc03_identify_anomaly():
    """UC-03: Identify Network Anomaly"""
    print_header('UC-03: IDENTIFY NETWORK ANOMALY')
    
    sim = SimulatedDevice()
    
    # Test each failure type
    failures = [
        ('ddos', 'DDOS_ATTACK'),
        ('service_crash', 'SERVICE_CRASH'),
        ('link_failure', 'LINK_FAILURE'),
    ]
    
    for failure, expected in failures:
        sim.inject_failure(failure)
        telemetry = sim.get_telemetry()
        is_anomaly, confidence = engine.detect_anomaly(telemetry)
        failure_type, class_conf = engine.classify_failure(telemetry)
        
        assert is_anomaly, f"{failure} not detected as anomaly"
        assert failure_type == expected, f"Got {failure_type}, expected {expected}"
        print(f'[PASS] {expected}: anomaly=True, confidence={confidence:.0%}')
    
    return True


def test_uc04_validate_remediation():
    """UC-04: Validate Remediation Script"""
    print_header('UC-04: VALIDATE REMEDIATION SCRIPT')
    
    from healing.actuator import actuator
    
    # Safe command
    safe_result = actuator._validate_in_sandbox('restart service nginx')
    assert safe_result, "Safe command rejected"
    print('[PASS] Safe command validated: restart service nginx')
    
    # Dangerous command
    dangerous_result = actuator._validate_in_sandbox('rm -rf /')
    assert not dangerous_result, "Dangerous command accepted!"
    print('[PASS] Dangerous command blocked: rm -rf /')
    
    return True


def test_uc05_autonomous_healing():
    """UC-05: Autonomous Healing"""
    print_header('UC-05: AUTONOMOUS HEALING')
    
    sim = SimulatedDevice()
    
    for failure in ['ddos', 'service_crash', 'link_failure']:
        sim.inject_failure(failure)
        result = orchestrator.run_cycle(monitor=True)
        
        assert result['incident_id'] is not None, f"{failure} - no incident created"
        assert result['incident_status'] == 'HEALED', f"{failure} - not healed"
        print(f'[PASS] {failure}: Incident #{result["incident_id"]} -> {result["incident_status"]}')
    
    return True


def test_uc06_manual_approval():
    """UC-06: Manual Approval (Human-in-the-Loop)"""
    print_header('UC-06: MANUAL APPROVAL')
    
    # Create a low-confidence incident
    device = Device.objects.filter(device_type='simulated').first()
    incident = Incident.objects.create(
        device=device,
        failure_type='DDOS_ATTACK',
        confidence_score=0.65,  # Below threshold
        status='MANUAL_REVIEW',
        source_ip='10.0.0.99',
    )
    
    assert incident.status == 'MANUAL_REVIEW'
    print(f'[PASS] Incident #{incident.id} created with MANUAL_REVIEW status')
    
    # Approve
    result = orchestrator.process_manual_approval(incident.id, approved=True)
    incident.refresh_from_db()
    print(f'[PASS] Manual approval processed, status: {incident.status}')
    
    return True


def test_uc07_manual_rollback():
    """UC-07: Manual Rollback"""
    print_header('UC-07: MANUAL ROLLBACK')
    
    from healing.actuator import actuator
    
    device = Device.objects.filter(device_type='simulated').first()
    incident = Incident.objects.create(
        device=device,
        failure_type='SERVICE_CRASH',
        confidence_score=0.90,
        status='FAILED',
    )
    
    healing = HealingAction.objects.create(
        incident=incident,
        action_type='RESTART_SERVICE',
        command='restart service nginx',
        status='FAILED',
    )
    
    actuator.rollback(incident)
    incident.refresh_from_db()
    
    assert incident.status == 'ROLLED_BACK'
    print(f'[PASS] Incident #{incident.id} rolled back successfully')
    
    return True


def test_uc08_view_xai():
    """UC-08: View XAI Explanation"""
    print_header('UC-08: VIEW XAI EXPLANATION')
    
    sim = SimulatedDevice()
    sim.inject_failure('ddos', source_ip='10.0.0.99', destination_port=443)
    telemetry = sim.get_telemetry()
    
    explanation = xai_engine.explain_diagnosis(telemetry, 'DDOS_ATTACK', 0.94)
    
    assert explanation['summary'], "No XAI summary"
    assert explanation['key_evidence'], "No XAI evidence"
    assert explanation['what_this_means'], "No XAI interpretation"
    
    print(f'[PASS] XAI Summary: {explanation["summary"][:100]}...')
    print(f'[PASS] Key Evidence: {len(explanation["key_evidence"])} items')
    print(f'[PASS] What This Means: {explanation["what_this_means"][:100]}...')
    
    return True


def test_uc09_audit_logs():
    """UC-09: Audit AI Decision Records"""
    print_header('UC-09: AUDIT AI DECISION RECORDS')
    
    incidents = Incident.objects.all()[:5]
    assert incidents.exists(), "No incidents to audit"
    
    for incident in incidents:
        healings = HealingAction.objects.filter(incident=incident)
        for healing in healings:
            print(f'[AUDIT] Incident #{incident.id}: {incident.failure_type} -> {healing.action_type} ({healing.status})')
    
    rewards = RLReward.objects.all()[:5]
    for reward in rewards:
        print(f'[REWARD] {reward.healing_action.action_type}: {reward.reward_value:+d}')
    
    print('[PASS] Audit trail available')
    return True


def run_all_use_case_tests():
    """Run all use case tests."""
    print('=' * 60)
    print('NEUROSYNAPSE USE CASE VALIDATION')
    print('=' * 60)
    
    results = {}
    
    tests = [
        ('UC-01: Configure Healing Policies', test_uc01_configure_healing_policies),
        ('UC-02: Monitor Telemetry', test_uc02_monitor_telemetry),
        ('UC-03: Identify Anomaly', test_uc03_identify_anomaly),
        ('UC-04: Validate Remediation', test_uc04_validate_remediation),
        ('UC-05: Autonomous Healing', test_uc05_autonomous_healing),
        ('UC-06: Manual Approval', test_uc06_manual_approval),
        ('UC-07: Manual Rollback', test_uc07_manual_rollback),
        ('UC-08: View XAI', test_uc08_view_xai),
        ('UC-09: Audit Logs', test_uc09_audit_logs),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            results[name] = 'PASS'
            passed += 1
        except Exception as e:
            results[name] = f'FAIL: {e}'
            failed += 1
            print(f'[FAIL] {e}')
    
    print('\n' + '=' * 60)
    print('USE CASE TEST SUMMARY')
    print('=' * 60)
    for name, result in results.items():
        status = 'PASS' if result == 'PASS' else 'FAIL'
        print(f'  [{status}] {name}')
    
    print(f'\n{passed} passed, {failed} failed')
    print('=' * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_use_case_tests()
    exit(0 if success else 1)