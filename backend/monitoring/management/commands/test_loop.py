"""
End-to-end MAPE-K loop verification command.

Injects a simulated failure, runs one complete MAPE-K iteration, and prints
phase transitions plus final RL reward status.
"""

from django.core.management.base import BaseCommand

from monitoring.models import Device, RLReward
from monitoring.connector import get_connector, telemetry_to_feature_vector
from ai_engine.orchestrator import orchestrator


class Command(BaseCommand):
    help = 'Inject a failure and execute one full MAPE-K loop iteration for verification'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='service_crash',
            choices=['service_crash', 'link_failure', 'ddos', 'ddos_attack'],
            help='Failure type to inject before running the loop',
        )
        parser.add_argument(
            '--device',
            type=str,
            default='SimRouter',
            help='Simulated device name',
        )

    def handle(self, *args, **options):
        failure_type = options['type']
        device_name = options['device']

        def log(message):
            self.stdout.write(message)

        self.stdout.write(self.style.HTTP_INFO('=' * 72))
        self.stdout.write(self.style.HTTP_INFO('NeuroSynapse MAPE-K E2E Verification'))
        self.stdout.write(self.style.HTTP_INFO('=' * 72))

        device, _ = Device.objects.get_or_create(
            ip_address='0.0.0.0',
            defaults={
                'name': device_name,
                'device_type': 'simulated',
                'status': 'ONLINE',
            },
        )
        if device.name != device_name:
            device.name = device_name
            device.device_type = 'simulated'
            device.status = 'ONLINE'
            device.save()

        log(f"[SETUP] Using device: {device.name} ({device.device_type})")

        connector = get_connector(device)
        injection_result = connector.inject_failure(failure_type)
        preview = connector.collect_telemetry()
        connector.disconnect()

        log(f"[INJECT] {injection_result}")
        if preview:
            vector = telemetry_to_feature_vector(preview)
            log(f"[INJECT] Feature vector: {vector}")

        log('')
        log('[LOOP] Starting single MAPE-K iteration...')
        result = orchestrator.run_cycle(device=device, logger=log, monitor=True)

        log('')
        self.stdout.write(self.style.HTTP_INFO('-' * 72))
        self.stdout.write(self.style.HTTP_INFO('MAPE-K Iteration Summary'))
        self.stdout.write(self.style.HTTP_INFO('-' * 72))
        log(f"  Telemetry ID : {result.get('telemetry_id')}")
        log(f"  Incident ID  : {result.get('incident_id')}")
        log(f"  Incident State: {result.get('incident_status')}")
        log(f"  Healing State : {result.get('healing_status')}")

        rl_stats = result.get('rl_stats') or {}
        latest_reward = RLReward.objects.order_by('-created_at').first()

        log('')
        self.stdout.write(self.style.HTTP_INFO('RL Reward Status'))
        log(f"  Episodes           : {rl_stats.get('episode_count', 0)}")
        log(f"  Recent Performance : {rl_stats.get('recent_performance', 0):.1%}")
        log(f"  Optimization Delta : {rl_stats.get('optimization_delta', 0):+.1%}")
        log(f"  Target Improvement : {rl_stats.get('target_improvement', 0.15):.0%}")
        log(f"  Replay Buffer Size : {rl_stats.get('replay_buffer_size', 0)}")
        log(f"  Epsilon            : {rl_stats.get('epsilon', 0)}")

        if latest_reward:
            log(
                f"  Latest Reward      : {latest_reward.reward_value:+d} "
                f"(incident #{latest_reward.state_context.get('incident_id')})"
            )
        else:
            log("  Latest Reward      : none recorded")

        success = result.get('incident_status') == 'HEALED'
        if success:
            self.stdout.write(self.style.SUCCESS('\nE2E VERIFICATION PASSED'))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\nE2E VERIFICATION COMPLETED WITH STATE: {result.get('incident_status')}"
                )
            )
