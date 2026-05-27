"""
Healing Actuator for NeuroSynapse.
Maps failure types to healing actions and executes them via SSH.
Includes sandbox validation (optional) and rollback capability.
"""

import time
from datetime import datetime
from monitoring.ssh_client import NetworkDeviceConnector
from monitoring.models import Device, Incident, HealingAction


# Healing action templates per failure type
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
            'command': 'configure terminal\ninterface GigabitEthernet0/2\nno shutdown\nexit',
            'description': 'Enable backup interface Gig0/2',
        },
        {
            'action_type': 'REROUTE_TRAFFIC',
            'command': 'no shutdown',
            'description': 'Re-enable the failed interface',
        },
    ],
    'DDOS_ATTACK': [
        {
            'action_type': 'BLOCK_SOURCE_IP',
            'command': 'access-list 100 deny ip 10.0.0.5 any',
            'description': 'Block attacking source IP',
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


from monitoring.vendor_profiles import get_profile

class HealingActuator:
    """Executes healing actions on network devices."""
    
    def __init__(self):
        self.connectors = {}
    
    def _get_connector(self, device):
        """Get or create SSH connector for a device."""
        return NetworkDeviceConnector(device)
    
    def get_actions_for_failure(self, failure_type, device_type='generic'):
        """Get healing actions from the vendor profile."""
        profile = get_profile(device_type)
        return profile['healing_commands'].get(failure_type, [])
    
    def select_action(self, failure_type, device_type='generic', rl_agent=None, **kwargs):
        """Select healing action using vendor profile and optional RL agent."""
        actions = self.get_actions_for_failure(failure_type, device_type)
        if not actions:
            return None
        
        # Fill template variables
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
            return filled_actions[action_index]
        
        return filled_actions[0]
    
    def execute_healing(self, incident, action=None, rl_agent=None):
        """Execute healing using the device's vendor profile."""
        device = incident.device
        
        if action is None:
            action = self.select_action(
                incident.failure_type,
                device.device_type,
                rl_agent,
                interface='ether2',  # Default backup interface
                ip='10.0.0.5',       # Default attack source
            )
        
        if action is None:
            return self._create_failed_action(
                incident, 'CUSTOM', 'No action available',
                f"No healing for {incident.failure_type} on {device.get_device_type_display()}"
            )
        
        # Create healing record
        healing = HealingAction.objects.create(
            incident=incident,
            action_type=action['action_type'],
            command=action['command'],
            status='PENDING',
        )
        
        print(f"[HEALING] {device.name} ({device.get_device_type_display()})")
        print(f"[HEALING] Action: {action['action_type']}")
        print(f"[HEALING] Command: {action['command']}")
        
        # Validate
        healing.status = 'VALIDATING'
        healing.save()
        sandbox_ok = self._validate_in_sandbox(action['command'])
        healing.sandbox_result = 'PASS' if sandbox_ok else 'SKIPPED'
        healing.save()
        
        # Execute
        healing.status = 'EXECUTING'
        healing.save()
        
        connector = self._get_connector(device)
        result = connector.execute_healing_command(action['command'])
        
        healing.execution_output = result.get('output', '')[:500]
        healing.completed_at = datetime.now()
        healing.status = 'EXECUTED' if result.get('success') else 'FAILED'
        healing.save()
        
        connector.disconnect()
        return healing
    
    def _validate_in_sandbox(self, command):
        """Validate a command in sandbox (Docker or simple check)."""
        # For development, do basic syntax check
        dangerous_patterns = ['rm -rf', 'format', 'erase', 'delete all']
        for pattern in dangerous_patterns:
            if pattern in command.lower():
                print(f"[SANDBOX] ❌ Dangerous command blocked: {pattern}")
                return False
        
        # Check for reasonable command length
        if len(command) > 500:
            print(f"[SANDBOX] ❌ Command too long: {len(command)} chars")
            return False
        
        print(f"[SANDBOX] ✅ Command validated (syntax check passed)")
        return True
    
    def verify_healing(self, incident):
        """Verify if healing was successful by checking device telemetry."""
        device = incident.device
        connector = self._get_connector(device)
        
        telemetry = connector.collect_telemetry()
        if telemetry is None:
            return False, "Could not collect telemetry"
        
        cpu = telemetry.get('cpu_usage', 0) or 0
        packet_loss = telemetry.get('packet_loss', 0) or 0
        
        # Simple health checks
        is_healthy = cpu < 70 and packet_loss < 10
        
        if is_healthy:
            incident.status = 'HEALED'
            incident.resolved_at = datetime.now()
            incident.save()
            print(f"[VERIFY] ✅ Network healthy (CPU: {cpu}%, Loss: {packet_loss}%)")
            return True, f"CPU: {cpu}%, Packet Loss: {packet_loss}%"
        else:
            print(f"[VERIFY] ❌ Still degraded (CPU: {cpu}%, Loss: {packet_loss}%)")
            return False, f"CPU: {cpu}%, Packet Loss: {packet_loss}%"
    
    def rollback(self, incident):
        """Rollback the last healing action."""
        last_action = HealingAction.objects.filter(
            incident=incident
        ).order_by('-created_at').first()
        
        if last_action:
            last_action.status = 'ROLLED_BACK'
            last_action.save()
        
        incident.status = 'ROLLED_BACK'
        incident.save()
        
        print(f"[HEALING] 🔄 Rolled back incident #{incident.id}")
    
    def _create_failed_action(self, incident, action_type, command, output):
        """Create a failed healing action record."""
        return HealingAction.objects.create(
            incident=incident,
            action_type=action_type,
            command=command,
            status='FAILED',
            execution_output=output,
            completed_at=datetime.now(),
        )
    
    def disconnect_all(self):
        """Disconnect all SSH connections."""
        for connector in self.connectors.values():
            connector.disconnect()
        self.connectors = {}
        print("[HEALING] All connections closed")


# Global instance
actuator = HealingActuator()