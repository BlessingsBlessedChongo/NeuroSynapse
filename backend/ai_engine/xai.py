"""
Explainable AI (XAI) Engine for NeuroSynapse.
Generates plain-English explanations for AI decisions.
"""

from monitoring.models import Telemetry, HealingAction


class XAIEngine:
    """Generates human-readable explanations for AI diagnoses and healing actions."""
    
    def __init__(self):
        self.feature_descriptions = {
            'cpu_usage': 'CPU utilization',
            'memory_usage': 'memory usage',
            'packet_loss': 'packet loss percentage',
            'latency_ms': 'network latency in milliseconds',
            'bandwidth_util': 'bandwidth utilization',
            'interface_up_count': 'number of active interfaces',
            'ospf_neighbors': 'OSPF routing neighbors',
            'error_count': 'interface error count',
        }
    
    def explain_diagnosis(self, telemetry, failure_type, confidence):
        """Explain why the AI made a particular diagnosis.
        
        Args:
            telemetry: Telemetry object or dict with metric values
            failure_type: The diagnosed failure type
            confidence: Classification confidence (0-1)
        
        Returns:
            Dictionary with explanation components
        """
        # Extract values
        cpu = telemetry.cpu_usage if hasattr(telemetry, 'cpu_usage') else telemetry.get('cpu_usage', 0)
        memory = telemetry.memory_usage if hasattr(telemetry, 'memory_usage') else telemetry.get('memory_usage', 0)
        packet_loss = telemetry.packet_loss if hasattr(telemetry, 'packet_loss') else telemetry.get('packet_loss', 0)
        latency = telemetry.latency_ms if hasattr(telemetry, 'latency_ms') else telemetry.get('latency_ms', 0)
        bandwidth = telemetry.bandwidth_util if hasattr(telemetry, 'bandwidth_util') else telemetry.get('bandwidth_util', 30)
        
        # Get interface status if available
        interface_status = telemetry.interface_status if hasattr(telemetry, 'interface_status') else telemetry.get('interface_status', {})
        up_count = sum(1 for d in interface_status.values() if d.get('status') == 'up') if interface_status else 0
        
        explanation = {
            'failure_type': failure_type,
            'confidence': confidence,
            'confidence_level': self._confidence_level(confidence),
            'summary': '',
            'key_evidence': [],
            'what_this_means': '',
            'contributing_factors': [],
        }
        
        if failure_type == 'SERVICE_CRASH':
            explanation['summary'] = (
                f"The ML model detected a SERVICE CRASH with {confidence:.0%} confidence. "
                f"This diagnosis is based primarily on critically high CPU usage ({cpu:.1f}%) "
                f"combined with elevated memory usage ({memory:.1f}%)."
            )
            explanation['key_evidence'] = [
                f"CPU usage is at {cpu:.1f}% (normal range: 20-45%)",
                f"Memory usage is at {memory:.1f}% (normal range: 30-50%)",
                f"Packet loss is {packet_loss:.1f}% (moderate, suggesting service issue, not link failure)",
            ]
            explanation['what_this_means'] = (
                "A service crash typically indicates that a critical application process "
                "(like nginx or a database) has stopped responding. The high CPU suggests "
                "the process is stuck in a loop or consuming excessive resources. The moderate "
                "packet loss rules out a physical link failure—the network is still up, but "
                "the service running on it has failed."
            )
            if up_count >= 2:
                explanation['key_evidence'].append(
                    f"{up_count} interfaces are still up, confirming this is not a link failure"
                )
            if memory > 80:
                explanation['contributing_factors'].append(
                    "High memory usage suggests a possible memory leak in the application"
                )
        
        elif failure_type == 'LINK_FAILURE':
            explanation['summary'] = (
                f"The ML model detected a LINK FAILURE with {confidence:.0%} confidence. "
                f"This is characterized by severe packet loss ({packet_loss:.1f}%) and "
                f"extreme latency ({latency:.0f}ms) while CPU remains normal ({cpu:.1f}%)."
            )
            explanation['key_evidence'] = [
                f"Packet loss is {packet_loss:.1f}% (critical: >50% indicates physical issue)",
                f"Latency is {latency:.0f}ms (normal: <10ms, current is {latency/5:.0f}x normal)",
                f"CPU usage is {cpu:.1f}% (normal, ruling out device overload)",
            ]
            explanation['what_this_means'] = (
                "A link failure indicates a physical connectivity problem—a cable is "
                "disconnected, a port has failed, or there's a switch hardware issue. "
                "The normal CPU means the router/switch itself is healthy; the problem "
                "is in the connection between devices. This is why restarting a service "
                "won't help—we need to reroute traffic through a backup path."
            )
            if up_count <= 1:
                explanation['key_evidence'].append(
                    f"Only {up_count} interfaces are operational (expected: 3+)"
                )
            explanation['contributing_factors'].append(
                "Check physical cables, SFP modules, and switch port LEDs for signs of failure"
            )
        
        elif failure_type == 'DDOS_ATTACK':
            explanation['summary'] = (
                f"The ML model detected a DDoS ATTACK with {confidence:.0%} confidence. "
                f"The signature is near-maximum CPU usage ({cpu:.1f}%) with very high "
                f"bandwidth utilization ({bandwidth:.1f}%)."
            )
            explanation['key_evidence'] = [
                f"CPU usage is {cpu:.1f}% (near maximum, consistent with traffic flood)",
                f"Bandwidth utilization is {bandwidth:.1f}% (normal: 20-50%)",
                f"Packet loss is {packet_loss:.1f}% (moderate, caused by overload)",
                f"Latency is elevated at {latency:.0f}ms (traffic queue saturation)",
            ]
            explanation['what_this_means'] = (
                "A DDoS attack is flooding the network with malicious traffic. The attacker "
                "is overwhelming the device's CPU and bandwidth with requests. Unlike a "
                "service crash, multiple services may still be running but are unreachable "
                "due to network congestion. The attack source should be blocked, and traffic "
                "should be rate-limited."
            )
            if bandwidth > 90:
                explanation['contributing_factors'].append(
                    "Bandwidth is nearly saturated—consider upstream filtering with your ISP"
                )
            explanation['contributing_factors'].append(
                "Review access logs to identify the attacking IP addresses and attack vector"
            )
        
        elif failure_type == 'PERFORMANCE_DEGRADATION':
            explanation['summary'] = (
                f"The ML model detected PERFORMANCE DEGRADATION with {confidence:.0%} confidence. "
                f"Metrics show moderate elevation across multiple indicators."
            )
            explanation['key_evidence'] = [
                f"CPU usage is elevated at {cpu:.1f}%",
                f"Latency is increased at {latency:.0f}ms",
            ]
            explanation['what_this_means'] = (
                "Performance degradation is an early warning sign. The network is still "
                "functioning but operating below optimal levels. This could be caused by "
                "increasing load, a slow memory leak, or a partially failing component."
            )
        
        else:  # NORMAL
            explanation['summary'] = (
                "The ML model determined the network is operating NORMALLY. "
                "All monitored metrics are within expected ranges."
            )
            explanation['key_evidence'] = [
                f"CPU: {cpu:.1f}% (normal range: 20-45%)",
                f"Memory: {memory:.1f}% (normal range: 30-50%)",
                f"Packet Loss: {packet_loss:.1f}% (normal: <1%)",
                f"Latency: {latency:.0f}ms (normal: <10ms)",
            ]
            explanation['what_this_means'] = (
                "All systems are functioning correctly. No action is required."
            )
        
        return explanation
    
    def explain_healing_action(self, incident, healing_action, success):
        """Explain why a particular healing action was chosen and its outcome.
        
        Args:
            incident: Incident object
            healing_action: HealingAction object
            success: Boolean indicating if healing worked
        
        Returns:
            Dictionary with explanation components
        """
        explanation = {
            'action_type': healing_action.get_action_type_display(),
            'command': healing_action.command,
            'success': success,
            'summary': '',
            'why_this_action': '',
            'what_happened': '',
            'alternatives': [],
        }
        
        action_descriptions = {
            'RESTART_SERVICE': (
                "Restarting the failed service is the most common and effective response "
                "to a service crash. This clears any stuck processes and reinitializes "
                "the application in a clean state."
            ),
            'REROUTE_TRAFFIC': (
                "Rerouting traffic through a backup interface bypasses the failed link. "
                "The RL agent has learned this is the fastest way to restore connectivity "
                "when a physical link fails."
            ),
            'BLOCK_SOURCE_IP': (
                "Blocking the attacking source IP stops the flood of malicious traffic "
                "at the network edge. This is preferred over rate-limiting when a clear "
                "attack source can be identified."
            ),
            'RATE_LIMIT': (
                "Rate-limiting restricts traffic flow to prevent overload while still "
                "allowing legitimate traffic. This is used when blocking a specific IP "
                "might affect legitimate users."
            ),
            'REBOOT_DEVICE': (
                "A full device reboot is the most drastic action. The RL agent selects "
                "this only when simpler actions (like service restart) have failed "
                "previously for this failure pattern."
            ),
            'CLEAR_CACHE': (
                "Clearing counters and cache frees up resources and removes stale data. "
                "This can resolve performance degradation caused by memory fragmentation."
            ),
        }
        
        explanation['why_this_action'] = action_descriptions.get(
            healing_action.action_type,
            "This action was selected based on learned experience from previous incidents."
        )
        
        if success:
            explanation['summary'] = (
                f"The {healing_action.get_action_type_display()} action was executed "
                f"successfully. The network has returned to normal operation."
            )
            explanation['what_happened'] = (
                f"The command '{healing_action.command}' was sent to the device "
                f"and completed successfully. Post-healing verification confirmed "
                f"all metrics have returned to normal ranges."
            )
        else:
            explanation['summary'] = (
                f"The {healing_action.get_action_type_display()} action did not "
                f"resolve the issue. A rollback was performed and the incident "
                f"requires manual attention."
            )
            explanation['what_happened'] = (
                f"The command '{healing_action.command}' was executed but the network "
                f"did not return to a healthy state. The system has rolled back the "
                f"action and escalated for manual review."
            )
        
        # Add RL context if available
        try:
            reward = healing_action.reward
            if reward:
                explanation['rl_context'] = (
                    f"The RL agent received a {'positive' if reward.reward_value > 0 else 'negative'} "
                    f"reward ({reward.reward_value:+d}) for this action. "
                    f"This {'reinforces' if reward.reward_value > 0 else 'discourages'} "
                    f"using this action for similar failures in the future."
                )
        except:
            pass
        
        return explanation
    
    def _confidence_level(self, confidence):
        """Convert confidence score to a human-readable level."""
        if confidence >= 0.90:
            return "Very High"
        elif confidence >= 0.75:
            return "High"
        elif confidence >= 0.60:
            return "Moderate"
        elif confidence >= 0.40:
            return "Low"
        else:
            return "Very Low"


# Global instance
xai_engine = XAIEngine()