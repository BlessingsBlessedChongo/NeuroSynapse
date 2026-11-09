import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from monitoring.models import Device

# Clear existing FRR test devices
Device.objects.filter(device_type='frr').delete()

# Register Local FRR Container Device
device = Device.objects.create(
    name='FRR-Router',
    ip_address='127.0.0.1',
    device_type='frr',
    vendor='FRRouting',
    ssh_port=2222,
    username='admin',
    password='admin',
    status='ONLINE',
)

print(f"Device {device.name} successfully registered at {device.ip_address}:{device.ssh_port}")