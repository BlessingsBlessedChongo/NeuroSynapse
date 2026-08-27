"""
Django management command to demonstrate NeuroSynapse's self‑healing
by injecting SERVICE_CRASH, LINK_FAILURE, and DDOS_ATTACK sequentially.
"""

import time
from django.core.management.base import BaseCommand
from monitoring.simulated_device import SimulatedDevice
from monitoring.models import Incident


class Command(BaseCommand):
    help = 'Inject all three failure types one by one and monitor healing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delay',
            type=int,
            default=20,
            help='Seconds to wait for healing between injections (default 20)',
        )

    def handle(self, *args, **options):
        delay = options['delay']
        sim = SimulatedDevice()
        failures = ['service_crash', 'link_failure', 'ddos']

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('NEUROSYNAPSE SELF‑HEALING DEMO'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        for failure in failures:
            self.stdout.write(f'\n>>> Injecting {failure.upper()}...')
            sim.inject_failure(failure)
            self.stdout.write(f'    Device state: {sim.health}')

            # Wait for the orchestrator to detect and heal
            self.stdout.write(f'    Waiting {delay}s for detection & healing...')
            time.sleep(delay)

            # Check final state
            current_health = sim.health
            if current_health == 'HEALTHY':
                self.stdout.write(
                    self.style.SUCCESS(f'    [OK] {failure.upper()} healed successfully.')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'    [ERROR] {failure.upper()} still in state {current_health}.')
                )

        # Final summary
        self.stdout.write('\n' + '=' * 60)
        total_incidents = Incident.objects.count()
        healed = Incident.objects.filter(status='HEALED').count()
        self.stdout.write(f'Total incidents created: {total_incidents}')
        self.stdout.write(f'Healed: {healed}')
        if total_incidents > 0:
            self.stdout.write(f'Healing rate: {healed / total_incidents * 100:.1f}%')
        self.stdout.write(self.style.SUCCESS('Demo complete. Check the dashboard for XAI explanations.'))