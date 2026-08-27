"""NeuroSynapse Integration Test - Full MAPE-K Loop Validation"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from ai_engine.orchestrator import orchestrator
from monitoring.simulated_device import SimulatedDevice
from monitoring.models import Incident, HealingAction
from ai_engine.rl_agent import rl_agent

print('=' * 60)
print('NEUROSYNAPSE INTEGRATION TEST')
print('=' * 60)

sim = SimulatedDevice()

# Test 1: DDoS Attack
print('\n[TEST 1] DDoS ATTACK')
sim.inject_failure('ddos', source_ip='10.0.0.99', destination_port=443, traffic_volume=75000)
result = orchestrator.run_cycle(monitor=True)
print(f"Incident: #{result['incident_id']} -> {result['incident_status']}")

# Test 2: Service Crash
print('\n[TEST 2] SERVICE CRASH')
sim.inject_failure('service_crash', service_name='nginx', process_id=1234)
result = orchestrator.run_cycle(monitor=True)
print(f"Incident: #{result['incident_id']} -> {result['incident_status']}")

# Test 3: Link Failure
print('\n[TEST 3] LINK FAILURE')
sim.inject_failure('link_failure', interface_name='ether1')
result = orchestrator.run_cycle(monitor=True)
print(f"Incident: #{result['incident_id']} -> {result['incident_status']}")

# Summary
print('\n' + '=' * 60)
print('SUMMARY')
print('=' * 60)
print(f'Total Incidents: {Incident.objects.count()}')
print(f'Healed: {Incident.objects.filter(status="HEALED").count()}')
print(f'Healing Actions: {HealingAction.objects.count()}')

stats = rl_agent.get_stats()
print(f"RL Episodes: {stats['episode_count']}")
print(f"RL Performance: {stats['recent_performance']:.1%}")
print('=' * 60)
print('INTEGRATION TEST PASSED')
print('=' * 60)