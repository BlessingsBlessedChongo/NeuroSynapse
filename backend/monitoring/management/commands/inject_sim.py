from django.core.management.base import BaseCommand
from monitoring.models import Device
from monitoring.connector import get_connector


class Command(BaseCommand):
    help = 'Inject a simulated failure into the in-memory device'

    def add_arguments(self, parser):
        parser.add_argument('--type', type=str, required=True,
                            choices=['service_crash', 'link_failure', 'ddos', 'ddos_attack'])
        parser.add_argument('--source-ip', type=str, dest='source_ip')
        parser.add_argument('--source-port', type=int, dest='source_port')
        parser.add_argument('--destination-ip', type=str, dest='destination_ip')
        parser.add_argument('--destination-port', type=int, dest='destination_port')
        parser.add_argument('--interface', type=str, dest='interface_name')
        parser.add_argument('--service-name', type=str, dest='service_name')
        parser.add_argument('--process-id', type=int, dest='process_id')
        parser.add_argument('--traffic-volume', type=float, dest='traffic_volume')

    def handle(self, *args, **options):
        device = Device.objects.filter(device_type='simulated').first()
        if not device:
            device, _ = Device.objects.get_or_create(
                ip_address='0.0.0.0',
                defaults={
                    'name': 'SimRouter',
                    'device_type': 'simulated',
                    'status': 'ONLINE',
                },
            )

        connector = get_connector(device)

        kwargs = {
            'source_ip': options.get('source_ip'),
            'source_port': options.get('source_port'),
            'destination_ip': options.get('destination_ip'),
            'destination_port': options.get('destination_port'),
            'interface_name': options.get('interface_name'),
            'service_name': options.get('service_name'),
            'process_id': options.get('process_id'),
            'traffic_volume': options.get('traffic_volume'),
        }

        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        result = connector.inject_failure(options['type'], **kwargs)

        self.stdout.write(self.style.WARNING(result))
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Device '{device.name}' ready for MAPE-K analysis"
        ))