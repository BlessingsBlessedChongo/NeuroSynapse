"""
Management command to start the telemetry collector.
Usage: python manage.py start_collector
"""

import signal
from django.core.management.base import BaseCommand
from monitoring.scheduler import collector


class Command(BaseCommand):
    help = 'Start the telemetry collection loop (runs every 5 seconds)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting telemetry collector...'))
        self.stdout.write(self.style.WARNING('Press Ctrl+C to stop'))
        
        # Handle graceful shutdown
        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING('\nStopping collector...'))
            collector.stop()
            self.stdout.write(self.style.SUCCESS('Collector stopped.'))
        
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            collector.start()
            # Keep main thread alive
            while collector.running:
                import time
                time.sleep(0.5)
        except KeyboardInterrupt:
            collector.stop()