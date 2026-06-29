"""
Test the AI engine with simulated telemetry.
Usage: python manage.py test_ai
"""

from django.core.management.base import BaseCommand
from ai_engine.inference import engine
from monitoring.models import Telemetry, Device


class Command(BaseCommand):
    help = 'Test the AI engine with sample telemetry data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing AI Engine...'))
        
        if not engine.loaded:
            self.stdout.write(self.style.ERROR(
                'Models not loaded. Run: python manage.py shell < ../backend/training/train_models.py OR python backend/training/train_models.py'
            ))
            return
        
        # Get or create test device
        device, _ = Device.objects.get_or_create(
            ip_address='127.0.0.1',
            defaults={'name': 'TestDevice', 'ssh_port': 2222}
        )
        
        # Test scenarios
        test_scenarios = [
            {
                'name': 'Normal Operation',
                'cpu': 28.0, 'memory': 38.0, 'packet_loss': 0.1,
                'latency': 5.0, 'bandwidth': 30.0,
                'interfaces': {
                    'Gig0/1': {'status': 'up', 'errors': 0},
                    'Gig0/2': {'status': 'up', 'errors': 0},
                    'Gig0/3': {'status': 'down', 'errors': 0},
                },
                'expected': 'NORMAL'
            },
            {
                'name': 'Service Crash',
                'cpu': 95.0, 'memory': 88.0, 'packet_loss': 3.0,
                'latency': 55.0, 'bandwidth': 65.0,
                'interfaces': {
                    'Gig0/1': {'status': 'up', 'errors': 0},
                    'Gig0/2': {'status': 'up', 'errors': 2},
                    'Gig0/3': {'status': 'down', 'errors': 0},
                },
                'expected': 'SERVICE_CRASH'
            },
            {
                'name': 'Link Failure',
                'cpu': 32.0, 'memory': 44.0, 'packet_loss': 80.0,
                'latency': 420.0, 'bandwidth': 18.0,
                'interfaces': {
                    'Gig0/1': {'status': 'down', 'errors': 55},
                    'Gig0/2': {'status': 'down', 'errors': 60},
                },
                'expected': 'LINK_FAILURE'
            },
            {
                'name': 'DDoS Attack',
                'cpu': 98.0, 'memory': 72.0, 'packet_loss': 38.0,
                'latency': 220.0, 'bandwidth': 96.0,
                'interfaces': {
                    'Gig0/1': {'status': 'up', 'errors': 15},
                    'Gig0/2': {'status': 'up', 'errors': 18},
                    'Gig0/3': {'status': 'down', 'errors': 0},
                },
                'expected': 'DDOS_ATTACK'
            },
        ]
        
        self.stdout.write('')
        correct = 0
        total = 0
        
        for scenario in test_scenarios:
            # Create test telemetry record
            telemetry = Telemetry(
                device=device,
                cpu_usage=scenario['cpu'],
                memory_usage=scenario['memory'],
                packet_loss=scenario['packet_loss'],
                latency_ms=scenario['latency'],
                bandwidth_util=scenario['bandwidth'],
                interface_status=scenario['interfaces'],
            )
            
            # Run diagnosis
            result = engine.diagnose(telemetry)
            
            is_correct = result['failure_type'] == scenario['expected']
            if is_correct:
                correct += 1
            total += 1
            
            # Display result
            icon = '✅' if is_correct else '❌'
            self.stdout.write(f"{icon} {scenario['name']}:")
            self.stdout.write(f"   Anomaly: {result['is_anomaly']} (conf: {result['anomaly_confidence']:.2%})")
            self.stdout.write(f"   Classified: {result['failure_type']} (conf: {result['classification_confidence']:.2%})")
            self.stdout.write(f"   Expected: {scenario['expected']}")
            self.stdout.write('')
        
        accuracy = correct / total * 100
        self.stdout.write(self.style.SUCCESS(f'Accuracy: {correct}/{total} ({accuracy:.0f}%)'))
        
        if accuracy >= 90:
            self.stdout.write(self.style.SUCCESS('✅ MEETS OBJECTIVE 1 (>90% accuracy)'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️ Below 90% target. Current: {accuracy:.0f}%'))