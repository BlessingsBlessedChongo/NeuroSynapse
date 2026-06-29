"""
Management command to start the telemetry collector.
Usage: python manage.py start_collector

NOTE: The mock SSH server must be running on localhost:2222
      Start it in a separate terminal: python simulation/mock_ssh_server.py
"""

import signal
import sys
from django.core.management.base import BaseCommand
from monitoring.scheduler import collector


class Command(BaseCommand):
    help = 'Start the telemetry collection loop (requires mock SSH server running on port 2222)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting telemetry collector...'))
        self.stdout.write(self.style.WARNING('\n⚠️  PREREQUISITE: Mock SSH server must be running on port 2222'))
        self.stdout.write(self.style.WARNING('   → Open another terminal and run: python simulation/mock_ssh_server.py\n'))
        self.stdout.write(self.style.WARNING('Press Ctrl+C to stop'))
        
        # Handle graceful shutdown
        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING('\n\nShutting down collector...'))
            collector.stop()
            self.stdout.write(self.style.SUCCESS('Collector stopped gracefully.'))
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            collector.start()
            # Keep main thread alive while collector runs
            while collector.running:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            collector.stop()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nFatal error: {e}'))
            collector.stop()
            sys.exit(1)