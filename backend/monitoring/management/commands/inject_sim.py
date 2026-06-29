from django.core.management.base import BaseCommand

from monitoring.models import Device
from monitoring.connector import get_connector


class Command(BaseCommand):
    help = 'Inject a simulated failure into the in-memory device'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            required=True,
            choices=['service_crash', 'link_failure', 'ddos', 'ddos_attack'],
            help='Failure type to inject (SERVICE_CRASH, LINK_FAILURE, DDOS_ATTACK)',
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

        device, _ = Device.objects.get_or_create(
            ip_address='0.0.0.0',
            defaults={
                'name': device_name,
                'device_type': 'simulated',
                'status': 'ONLINE',
            },
        )

        connector = get_connector(device)
        result = connector.inject_failure(failure_type)
        connector.disconnect()

        self.stdout.write(self.style.WARNING(result))
        self.stdout.write(
            self.style.SUCCESS(
                f"Device '{device.name}' ready for MAPE-K analysis "
                f"({failure_type.upper()})"
            )
        )
