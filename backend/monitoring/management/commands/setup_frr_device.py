"""
Create a local FRR device pointing at the Docker FRR container.
Usage: python manage.py setup_frr_device
"""

from django.core.management.base import BaseCommand
from monitoring.models import Device


class Command(BaseCommand):
    help = 'Create a FRR device pointing to local FRR Docker container (127.0.0.1:2222)'

    def handle(self, *args, **options):
        device, created = Device.objects.update_or_create(
            ip_address='127.0.0.1',
            defaults={
                'name': 'FRR Docker Router',
                'device_type': 'frr',
                'ssh_port': 2222,
                'username': 'admin',
                'password': 'admin',
                'status': 'ONLINE',
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created FRR device: {device}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Updated FRR device: {device}'))
