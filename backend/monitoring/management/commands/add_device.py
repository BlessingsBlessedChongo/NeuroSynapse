"""
Add a new network device to NeuroSynapse.
Usage: python manage.py add_device --name Router1 --ip 192.168.88.1 --type mikrotik_routeros --user admin --pass neuro1234
"""

from django.core.management.base import BaseCommand
from monitoring.models import Device
from monitoring.vendor_profiles import get_supported_vendors


class Command(BaseCommand):
    help = 'Add a network device to NeuroSynapse'

    def add_arguments(self, parser):
        parser.add_argument('--name', type=str, required=True, help='Device name')
        parser.add_argument('--ip', type=str, required=True, help='Device IP address')
        parser.add_argument('--type', type=str, default='generic',
                          choices=[v['device_type'] for v in get_supported_vendors()],
                          help='Device type (vendor)')
        parser.add_argument('--port', type=int, default=22, help='SSH port')
        parser.add_argument('--user', type=str, default='admin', help='SSH username')
        parser.add_argument('--pass', dest='password', type=str, default='admin', help='SSH password')

    def handle(self, *args, **options):
        device, created = Device.objects.update_or_create(
            ip_address=options['ip'],
            defaults={
                'name': options['name'],
                'device_type': options['type'],
                'ssh_port': options['port'],
                'username': options['user'],
                'password': options['password'],
                'status': 'ONLINE',
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Added device: {device.name}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Updated device: {device.name}'))
        
        self.stdout.write(f'  IP: {device.ip_address}')
        self.stdout.write(f'  Type: {device.get_device_type_display()}')
        self.stdout.write(f'  SSH Port: {device.ssh_port}')