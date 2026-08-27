"""
Management command to test SSH connection to the mock server.
Usage: python manage.py test_ssh
"""

from django.core.management.base import BaseCommand
from monitoring.ssh_client import test_connection


class Command(BaseCommand):
    help = 'Test SSH connection to the mock network device'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing SSH connection...'))
        test_connection()
        self.stdout.write(self.style.SUCCESS('Test complete.'))