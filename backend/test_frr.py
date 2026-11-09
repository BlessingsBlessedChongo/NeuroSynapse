"""
Test FRR device connection and telemetry collection.
Run: python test_frr.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from monitoring.models import Device
from monitoring.connector import get_connector


def test_frr_connection():
    """Test SSH connection to FRR router and collect telemetry."""
    print('=' * 60)
    print('FRR DEVICE CONNECTION TEST')
    print('=' * 60)

    # Find FRR device
    device = Device.objects.filter(device_type='frr').first()
    if not device:
        device = Device.objects.filter(name__icontains='frr').first()
    
    if not device:
        print('[FAIL] No FRR device found in database')
        print('Run: python add_frr.py first')
        return False

    print(f'\n[INFO] Testing device: {device.name}')
    print(f'[INFO] IP: {device.ip_address}')
    print(f'[INFO] Port: {device.ssh_port}')
    print(f'[INFO] Username: {device.username}')

    # Get connector
    connector = get_connector(device)

    # Test connection
    print('\n[TEST] Attempting SSH connection...')
    if not connector.connect():
        print('[FAIL] Could not connect to FRR router')
        print('Check:')
        print('  1. Azure VM SSH daemon is running')
        print('  2. SSH port is correct')
        print('  3. Username/password are correct')
        print('  4. Network/NSG port 22 is open')
        return False

    print('[PASS] Connected to FRR router')

    # Test telemetry collection
    print('\n[TEST] Collecting telemetry...')
    telemetry = connector.collect_telemetry()

    if telemetry:
        print('\n[PASS] Telemetry collected:')
        print('-' * 40)
        for key, value in telemetry.items():
            if isinstance(value, dict):
                print(f'  {key}:')
                for k2, v2 in value.items():
                    print(f'    {k2}: {v2}')
            else:
                print(f'  {key}: {value}')
        print('-' * 40)
    else:
        print('[WARN] Telemetry collection returned None')
        print('This may be because FRR uses different commands than expected.')

    # Test healing/CLI command execution (safe - vtysh show interface)
    print('\n[TEST] Testing command execution...')
    try:
        result = connector.execute_healing_command('show interface')
        if result.get('success'):
            print('[PASS] Command executed successfully')
            print(f'Output: {result.get("output", "")[:200]}...')
        else:
            print(f'[WARN] Command returned failure: {result.get("output", "")[:200]}')
    except Exception as e:
        print(f'[WARN] Command test failed: {e}')

    # Disconnect
    connector.disconnect()
    print('\n[INFO] Disconnected from FRR router')

    print('\n' + '=' * 60)
    print('FRR TEST COMPLETE')
    print('=' * 60)
    return True


if __name__ == '__main__':
    success = test_frr_connection()
    exit(0 if success else 1)