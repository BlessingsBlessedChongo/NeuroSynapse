"""
Start the MAPE-K orchestrator loop.
Usage: python manage.py start_orchestrator
"""

import signal
from django.core.management.base import BaseCommand
from ai_engine.orchestrator import orchestrator


class Command(BaseCommand):
    help = 'Start the MAPE-K orchestrator (auto-detect and heal)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting NeuroSynapse Orchestrator...'))
        self.stdout.write(self.style.WARNING('Press Ctrl+C to stop'))
        
        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING('\nStopping orchestrator...'))
            orchestrator.stop()
            self.stdout.write(self.style.SUCCESS('Orchestrator stopped.'))
        
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            orchestrator.start()
            while orchestrator.running:
                import time
                time.sleep(0.5)
        except KeyboardInterrupt:
            orchestrator.stop()