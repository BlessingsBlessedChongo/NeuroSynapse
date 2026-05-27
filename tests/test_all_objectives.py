"""
Complete test suite for all 5 NeuroSynapse objectives.
Run this file directly to validate all requirements.
"""

import os
import sys
import time
import json
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
django.setup()

from monitoring.models import Device, Telemetry, Incident, HealingAction, RLReward
from ai_engine.inference import engine
from ai_engine.xai import xai_engine
from ai_engine.rl_agent import rl_agent
from healing.actuator import actuator, HEALING_POLICIES


class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def record(self, test_name, passed, details=""):
        self.results.append({
            'test': test_name,
            'passed': passed,
            'details': details,
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def summary(self):
        total = self.passed + self.failed
        print("\n" + "=" * 60)
        print(f"TEST SUMMARY: {self.passed}/{total} passed")
        print("=" * 60)
        for r in self.results:
            icon = "✅" if r['passed'] else "❌"
            print(f"  {icon} {r['test']}")
            if r['details']:
                print(f"     {r['details']}")
        return self.failed == 0


def get_or_create_device():
    """Get or create the test device."""
    device, _ = Device.objects.get_or_create(
        ip_address='127.0.0.1',
        defaults={
            'name': 'TestRouter01',
            'device_type': 'router',
            'vendor': 'Mock',
            'ssh_port': 2222,
            'username': 'admin',
            'password': 'anything',
        }
    )
    return device


def test_objective_1(results):
    """Test Objective 1: Real-time anomaly detection >90% accuracy."""
    print("\n" + "=" * 60)
    print("TESTING OBJECTIVE 1: Anomaly Detection Accuracy")
    print("=" * 60)
    
    if not engine.loaded:
        results.record("Objective 1: Models loaded", False, "Models not found. Run training first.")
        return
    
    results.record("Objective 1: Models loaded", True)
    
    device = get_or_create_device()
    
    test_cases = [
        {'cpu': 28, 'memory': 38, 'packet_loss': 0.1, 'latency': 5, 'bandwidth': 30,
         'interfaces': {'G0/1': {'status': 'up'}, 'G0/2': {'status': 'up'}}, 'expected': 'NORMAL'},
        {'cpu': 30, 'memory': 42, 'packet_loss': 0.2, 'latency': 6, 'bandwidth': 35,
         'interfaces': {'G0/1': {'status': 'up'}, 'G0/2': {'status': 'up'}}, 'expected': 'NORMAL'},
        {'cpu': 94, 'memory': 87, 'packet_loss': 3, 'latency': 55, 'bandwidth': 62,
         'interfaces': {'G0/1': {'status': 'up'}, 'G0/2': {'status': 'up'}}, 'expected': 'SERVICE_CRASH'},
        {'cpu': 91, 'memory': 84, 'packet_loss': 2, 'latency': 48, 'bandwidth': 58,
         'interfaces': {'G0/1': {'status': 'up'}, 'G0/2': {'status': 'up'}}, 'expected': 'SERVICE_CRASH'},
        {'cpu': 33, 'memory': 44, 'packet_loss': 78, 'latency': 420, 'bandwidth': 18,
         'interfaces': {'G0/1': {'status': 'down'}}, 'expected': 'LINK_FAILURE'},
        {'cpu': 28, 'memory': 40, 'packet_loss': 82, 'latency': 380, 'bandwidth': 22,
         'interfaces': {'G0/1': {'status': 'down'}}, 'expected': 'LINK_FAILURE'},
        {'cpu': 97, 'memory': 73, 'packet_loss': 36, 'latency': 210, 'bandwidth': 94,
         'interfaces': {'G0/1': {'status': 'up'}, 'G0/2': {'status': 'up'}}, 'expected': 'DDOS_ATTACK'},
        {'cpu': 98, 'memory': 68, 'packet_loss': 42, 'latency': 240, 'bandwidth': 97,
         'interfaces': {'G0/1': {'status': 'up'}, 'G0/2': {'status': 'up'}}, 'expected': 'DDOS_ATTACK'},
    ]
    
    correct = 0
    for i, tc in enumerate(test_cases):
        telemetry = Telemetry.objects.create(
            device=device,
            cpu_usage=tc['cpu'],
            memory_usage=tc['memory'],
            packet_loss=tc['packet_loss'],
            latency_ms=tc['latency'],
            bandwidth_util=tc['bandwidth'],
            interface_status=tc['interfaces'],
        )
        
        diagnosis = engine.diagnose(telemetry)
        predicted = diagnosis['failure_type'] if diagnosis['is_anomaly'] else 'NORMAL'
        is_correct = predicted == tc['expected']
        if is_correct:
            correct += 1
    
    accuracy = correct / len(test_cases)
    results.record(
        f"Objective 1: Detection accuracy",
        accuracy >= 0.90,
        f"{accuracy:.1%} ({correct}/{len(test_cases)}), target: 90%"
    )
    
    return accuracy


def test_objective_2(results):
    """Test Objective 2: Failure classification with confidence scores."""
    print("\n" + "=" * 60)
    print("TESTING OBJECTIVE 2: Failure Classification")
    print("=" * 60)
    
    device = get_or_create_device()
    
    failure_tests = [
        {'failure': 'SERVICE_CRASH', 'cpu': 95, 'memory': 88, 'packet_loss': 2, 'latency': 50, 'bandwidth': 60,
         'interfaces': {'G0/1': {'status': 'up'}, 'G0/2': {'status': 'up'}}},
        {'failure': 'LINK_FAILURE', 'cpu': 30, 'memory': 42, 'packet_loss': 80, 'latency': 400, 'bandwidth': 15,
         'interfaces': {'G0/1': {'status': 'down'}}},
        {'failure': 'DDOS_ATTACK', 'cpu': 98, 'memory': 70, 'packet_loss': 35, 'latency': 200, 'bandwidth': 95,
         'interfaces': {'G0/1': {'status': 'up'}, 'G0/2': {'status': 'up'}}},
    ]
    
    all_passed = True
    for test in failure_tests:
        telemetry = Telemetry.objects.create(
            device=device,
            cpu_usage=test['cpu'],
            memory_usage=test['memory'],
            packet_loss=test['packet_loss'],
            latency_ms=test['latency'],
            bandwidth_util=test['bandwidth'],
            interface_status=test['interfaces'],
        )
        
        diagnosis = engine.diagnose(telemetry)
        correct = diagnosis['failure_type'] == test['failure']
        has_confidence = diagnosis['classification_confidence'] > 0
        
        if not correct:
            all_passed = False
        
        results.record(
            f"Objective 2: Classify {test['failure']}",
            correct and has_confidence,
            f"Predicted: {diagnosis['failure_type']}, Confidence: {diagnosis['classification_confidence']:.1%}"
        )
    
    return all_passed


def test_objective_3(results):
    """Test Objective 3: Healing actions are defined and executable."""
    print("\n" + "=" * 60)
    print("TESTING OBJECTIVE 3: Healing Actions")
    print("=" * 60)
    
    # Check healing policies exist for all failure types
    for failure_type in ['SERVICE_CRASH', 'LINK_FAILURE', 'DDOS_ATTACK']:
        actions = HEALING_POLICIES.get(failure_type, [])
        results.record(
            f"Objective 3: {failure_type} has healing actions",
            len(actions) > 0,
            f"{len(actions)} actions defined"
        )
    
    # Test that actuator can select actions
    for failure_type in ['SERVICE_CRASH', 'LINK_FAILURE', 'DDOS_ATTACK']:
        action = actuator.select_action(failure_type)
        results.record(
            f"Objective 3: Can select action for {failure_type}",
            action is not None,
            f"Selected: {action['action_type'] if action else 'None'}"
        )
    
    # Test sandbox validation
    safe_command = "restart service nginx"
    safe_result = actuator._validate_in_sandbox(safe_command)
    results.record(
        "Objective 3: Sandbox accepts safe commands",
        safe_result,
        f"'{safe_command}' validated"
    )
    
    dangerous_command = "rm -rf /"
    dangerous_result = actuator._validate_in_sandbox(dangerous_command)
    results.record(
        "Objective 3: Sandbox blocks dangerous commands",
        not dangerous_result,
        f"'{dangerous_command}' blocked"
    )


def test_objective_4(results):
    """Test Objective 4: Dashboard and XAI."""
    print("\n" + "=" * 60)
    print("TESTING OBJECTIVE 4: Dashboard and XAI")
    print("=" * 60)
    
    device = get_or_create_device()
    
    # Test XAI explanations for each failure type
    for failure_type in ['SERVICE_CRASH', 'LINK_FAILURE', 'DDOS_ATTACK']:
        telemetry = Telemetry.objects.create(
            device=device,
            cpu_usage=90,
            memory_usage=80,
            packet_loss=30,
            latency_ms=100,
            bandwidth_util=70,
            interface_status={'G0/1': {'status': 'up'}},
        )
        
        explanation = xai_engine.explain_diagnosis(telemetry, failure_type, 0.94)
        
        results.record(
            f"Objective 4: XAI explanation for {failure_type}",
            explanation['summary'] != '' and len(explanation['key_evidence']) > 0,
            f"Summary: {explanation['summary'][:80]}..."
        )
    
    # Test confidence levels
    levels = [
        (0.95, 'Very High'),
        (0.85, 'High'),
        (0.70, 'Moderate'),
        (0.50, 'Low'),
        (0.30, 'Very Low'),
    ]
    for confidence, expected_level in levels:
        level = xai_engine._confidence_level(confidence)
        results.record(
            f"Objective 4: Confidence level {confidence}",
            level == expected_level,
            f"Got: {level}, Expected: {expected_level}"
        )


def test_objective_5(results):
    """Test Objective 5: RL agent learns and improves."""
    print("\n" + "=" * 60)
    print("TESTING OBJECTIVE 5: RL Learning")
    print("=" * 60)
    
    # Check agent initializes
    results.record(
        "Objective 5: RL agent initializes",
        rl_agent is not None,
        f"Epsilon: {rl_agent.epsilon}, Episodes: {rl_agent.episode_count}"
    )
    
    # Check agent can select actions
    for failure_type in ['SERVICE_CRASH', 'LINK_FAILURE', 'DDOS_ATTACK']:
        num_actions = len(HEALING_POLICIES.get(failure_type, []))
        if num_actions > 0:
            action = rl_agent.select_action(failure_type, num_actions)
            results.record(
                f"Objective 5: Select action for {failure_type}",
                0 <= action < num_actions,
                f"Action {action}/{num_actions}"
            )
    
    # Check agent updates Q-values
    initial_q = rl_agent.get_q_value('SERVICE_CRASH', 0)
    rl_agent.update('SERVICE_CRASH', 0, 1)  # Positive reward
    updated_q = rl_agent.get_q_value('SERVICE_CRASH', 0)
    
    results.record(
        "Objective 5: Q-value updates with positive reward",
        updated_q > initial_q,
        f"Q-value: {initial_q:.3f} → {updated_q:.3f}"
    )
    
    # Check reward recording
    device = get_or_create_device()
    incident = Incident.objects.create(
        device=device,
        failure_type='SERVICE_CRASH',
        confidence_score=0.90,
        status='DETECTED',
    )
    
    healing = HealingAction.objects.create(
        incident=incident,
        action_type='RESTART_SERVICE',
        command='restart service nginx',
        status='EXECUTED',
    )
    
    rl_agent.record_reward(healing, success=True)
    
    reward_exists = RLReward.objects.filter(healing_action=healing).exists()
    results.record(
        "Objective 5: Reward recorded in database",
        reward_exists,
        "Reward saved successfully"
    )
    
    # Get stats
    stats = rl_agent.get_stats()
    results.record(
        "Objective 5: Agent statistics available",
        'episode_count' in stats and 'recent_performance' in stats,
        f"Episodes: {stats['episode_count']}, Performance: {stats['recent_performance']}"
    )


def run_all_tests():
    """Run all objective tests."""
    print("=" * 60)
    print("NEUROSYNAPSE - COMPLETE OBJECTIVE VALIDATION")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    results = TestResults()
    
    test_objective_1(results)
    test_objective_2(results)
    test_objective_3(results)
    test_objective_4(results)
    test_objective_5(results)
    
    all_passed = results.summary()
    
    # Save results to file
    output = {
        'timestamp': datetime.now().isoformat(),
        'passed': results.passed,
        'failed': results.failed,
        'total': results.passed + results.failed,
        'all_passed': all_passed,
        'results': results.results,
    }
    
    os.makedirs('test_results', exist_ok=True)
    with open('test_results/validation_report.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to: test_results/validation_report.json")
    
    return all_passed


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)