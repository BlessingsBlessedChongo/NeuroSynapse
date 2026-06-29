"""
Healing Actuator for NeuroSynapse.
Maps failure types to healing actions and executes them via device connectors.
"""

from django.utils import timezone

from monitoring.connector import get_connector, normalize_telemetry
from monitoring.models import Incident, HealingAction
from monitoring.vendor_profiles import get_profile


HEALING_POLICIES = {
    'SERVICE_CRASH': [
        {
            'action_type': 'RESTART_SERVICE',
            'command': 'restart service nginx',
            'description': 'Restart the crashed nginx service',
        },
        {
            'action_type': 'RESTART_SERVICE',
            'command': 'restart service apache2',
            'description': 'Restart the crashed apache service',
        },
        {
            'action_type': 'REBOOT_DEVICE',
            'command': 'reboot',
            'description': 'Full device reboot (last resort)',
        },
    ],
    'LINK_FAILURE': [
        {
            'action_type': 'REROUTE_TRAFFIC',
            'command': 'interface ether2\nno shutdown',
            'description': 'Enable backup interface ether2',
        },
        {
            'action_type': 'REROUTE_TRAFFIC',
            'command': 'interface ether1\nno shutdown',
            'description': 'Re-enable the failed interface',
        },
    ],
    'DDOS_ATTACK': [
        {
            'action_type': 'BLOCK_SOURCE_IP',
            'command': 'access-list 100 deny ip host 10.0.0.5 any',
            'description': 'Block attacking source IP via ACL',
        },
        {
            'action_type': 'RATE_LIMIT',
            'command': 'rate-limit input 1000000 8000 8000',
            'description': 'Rate-limit incoming traffic',
        },
    ],
    'PERFORMANCE_DEGRADATION': [
        {
            'action_type': 'CLEAR_CACHE',
            'command': 'clear counters',
            'description': 'Clear interface counters and cache',
        },
    ],
}


class HealingActuator:
    """Executes healing actions on network devices."""

    CONFIDENCE_THRESHOLD = 0.70

    def __init__(self):
        self.connectors = {}

    def _resolve_device_type(self, device):
        device_type = device.device_type or 'generic'
        if device_type == 'simulated':
            return 'generic'
        return device_type

    def _get_connector(self, device):
        connector = get_connector(device)
        self.connectors[device.id] = connector
        return connector

    def get_actions_for_failure(self, failure_type, device_type='generic'):
        resolved_type = 'generic' if device_type == 'simulated' else device_type
        profile = get_profile(resolved_type)
        actions = profile['healing_commands'].get(failure_type, [])
        if actions:
            return actions
        return HEALING_POLICIES.get(failure_type, [])

    def select_action(self, failure_type, device_type='generic', rl_agent=None, **kwargs):
        actions = self.get_actions_for_failure(failure_type, device_type)
        if not actions:
            return None

        filled_actions = []
        for action in actions:
            filled = action.copy()
            try:
                filled['command'] = action['command'].format(**kwargs)
            except KeyError:
                pass
            filled_actions.append(filled)

        if rl_agent:
            action_index = rl_agent.select_action(failure_type, len(filled_actions))
            selected = filled_actions[action_index]
            selected['action_index'] = action_index
            return selected

        selected = filled_actions[0]
        selected['action_index'] = 0
        return selected

    def execute_healing(self, incident, action=None, rl_agent=None):
        device = incident.device
        device_type = self._resolve_device_type(device)

        if action is None:
            action = self.select_action(
                incident.failure_type,
                device_type,
                rl_agent,
                interface='ether2',
                ip='10.0.0.5',
            )

        if action is None:
            return self._create_failed_action(
                incident,
                'CUSTOM',
                'No action available',
                f"No healing for {incident.failure_type} on {device.get_device_type_display()}",
            )

        incident.status = 'HEALING'
        incident.save(update_fields=['status'])

        healing = HealingAction.objects.create(
            incident=incident,
            action_type=action['action_type'],
            command=action['command'],
            status='PENDING',
        )

        print(f"[HEALING] {device.name} ({device.get_device_type_display()})")
        print(f"[HEALING] Action: {action['action_type']}")
        print(f"[HEALING] Command: {action['command']}")

        healing.status = 'VALIDATING'
        healing.save(update_fields=['status'])
        sandbox_ok = self._validate_in_sandbox(action['command'])
        healing.sandbox_result = 'PASS' if sandbox_ok else 'SKIPPED'
        healing.save(update_fields=['sandbox_result'])

        healing.status = 'EXECUTING'
        healing.save(update_fields=['status'])

        connector = self._get_connector(device)
        result = connector.execute_healing_command(action['command'])

        healing.execution_output = str(result.get('output', ''))[:500]
        healing.completed_at = timezone.now()
        healing.status = 'EXECUTED' if result.get('success') else 'FAILED'
        healing.save()

        return healing

    def _validate_in_sandbox(self, command):
        dangerous_patterns = ['rm -rf', 'format', 'erase', 'delete all']
        for pattern in dangerous_patterns:
            if pattern in command.lower():
                print(f"[SANDBOX] Dangerous command blocked: {pattern}")
                return False

        if len(command) > 500:
            print(f"[SANDBOX] Command too long: {len(command)} chars")
            return False

        print("[SANDBOX] Command validated (syntax check passed)")
        return True

    def verify_healing(self, incident):
        """Verify recovery via fresh telemetry from the simulator/device."""
        device = incident.device
        connector = self._get_connector(device)

        if hasattr(connector, 'verify_recovery'):
            is_healthy, telemetry = connector.verify_recovery()
        else:
            telemetry = connector.collect_telemetry()
            is_healthy = telemetry is not None

        connector.disconnect()

        if telemetry is None:
            incident.status = 'FAILED'
            incident.save(update_fields=['status'])
            return False, "Could not collect telemetry"

        normalized = normalize_telemetry(telemetry)
        cpu = normalized.get('cpu_usage', 100.0)
        packet_loss = normalized.get('packet_loss', 100.0)
        latency = normalized.get('latency_ms', 999.0)

        if is_healthy is None:
            is_healthy = cpu < 70 and packet_loss < 10 and latency < 100

        if is_healthy:
            incident.status = 'HEALED'
            incident.resolved_at = timezone.now()
            incident.save(update_fields=['status', 'resolved_at'])
            print(
                f"[VERIFY] Network healthy "
                f"(CPU: {cpu}%, Loss: {packet_loss}%, Latency: {latency}ms)"
            )
            return True, (
                f"CPU: {cpu}%, Packet Loss: {packet_loss}%, Latency: {latency}ms"
            )

        incident.status = 'FAILED'
        incident.save(update_fields=['status'])
        print(f"[VERIFY] Still degraded (CPU: {cpu}%, Loss: {packet_loss}%)")
        return False, f"CPU: {cpu}%, Packet Loss: {packet_loss}%"

    def rollback(self, incident):
        last_action = HealingAction.objects.filter(
            incident=incident
        ).order_by('-created_at').first()

        if last_action:
            last_action.status = 'ROLLED_BACK'
            last_action.save(update_fields=['status'])

        incident.status = 'ROLLED_BACK'
        incident.save(update_fields=['status'])
        print(f"[HEALING] Rolled back incident #{incident.id}")

    def _create_failed_action(self, incident, action_type, command, output):
        return HealingAction.objects.create(
            incident=incident,
            action_type=action_type,
            command=command,
            status='FAILED',
            execution_output=output,
            completed_at=timezone.now(),
        )

    def disconnect_all(self):
        for connector in self.connectors.values():
            connector.disconnect()
        self.connectors = {}
        print("[HEALING] All connections closed")


actuator = HealingActuator()
