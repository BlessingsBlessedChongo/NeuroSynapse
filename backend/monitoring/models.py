from django.db import models


class Device(models.Model):
    """Represents a managed network device."""
    DEVICE_TYPES = [
        ('cisco_ios', 'Cisco IOS'),
        ('mikrotik_routeros', 'MikroTik RouterOS'),
        ('juniper_junos', 'Juniper JunOS'),
        ('huawei_vrp', 'Huawei VRP'),
        ('generic', 'Generic/Mock Router'),
    ]
    
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(unique=True)
    device_type = models.CharField(max_length=50, choices=DEVICE_TYPES, default='generic')
    vendor = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('ONLINE', 'Online'),
            ('OFFLINE', 'Offline'),
            ('DEGRADED', 'Degraded'),
        ],
        default='ONLINE'
    )
    ssh_port = models.IntegerField(default=22)
    username = models.CharField(max_length=100, default='admin')
    password = models.CharField(max_length=255, default='password')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_device_type_display()})"

class Telemetry(models.Model):
    """Stores telemetry data collected from network devices"""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='telemetry')
    timestamp = models.DateTimeField(auto_now_add=True)
    cpu_usage = models.FloatField(null=True, blank=True)
    memory_usage = models.FloatField(null=True, blank=True)
    latency_ms = models.FloatField(null=True, blank=True)
    packet_loss = models.FloatField(null=True, blank=True)
    bandwidth_util = models.FloatField(null=True, blank=True)
    interface_status = models.JSONField(null=True, blank=True)
    raw_output = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['device', '-timestamp']),
        ]

    def __str__(self):
        return f"Telemetry from {self.device.name} at {self.timestamp}"


class Incident(models.Model):
    """Records detected network anomalies/failures"""
    FAILURE_TYPES = [
        ('SERVICE_CRASH', 'Service Crash'),
        ('LINK_FAILURE', 'Link Failure'),
        ('DDOS_ATTACK', 'DDoS Attack'),
        ('PERFORMANCE_DEGRADATION', 'Performance Degradation'),
        ('UNKNOWN', 'Unknown'),
    ]

    STATUS_CHOICES = [
        ('DETECTED', 'Detected'),
        ('DIAGNOSING', 'Diagnosing'),
        ('READY_FOR_ACTION', 'Ready for Action'),
        ('MANUAL_REVIEW', 'Manual Review'),
        ('HEALING', 'Healing'),
        ('HEALED', 'Healed'),
        ('FAILED', 'Failed'),
        ('ROLLED_BACK', 'Rolled Back'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='incidents')
    telemetry_snapshot = models.ForeignKey(Telemetry, on_delete=models.SET_NULL, null=True)
    failure_type = models.CharField(max_length=50, choices=FAILURE_TYPES, default='UNKNOWN')
    confidence_score = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DETECTED')
    description = models.TextField(blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-detected_at']

    def __str__(self):
        return f"{self.failure_type} on {self.device.name} ({self.confidence_score:.2f})"


class HealingAction(models.Model):
    """Records healing actions taken to resolve incidents"""
    ACTION_TYPES = [
        ('RESTART_SERVICE', 'Restart Service'),
        ('REROUTE_TRAFFIC', 'Reroute Traffic'),
        ('BLOCK_SOURCE_IP', 'Block Source IP'),
        ('REBOOT_DEVICE', 'Reboot Device'),
        ('CLEAR_CACHE', 'Clear Cache'),
        ('RATE_LIMIT', 'Rate Limit'),
        ('CUSTOM', 'Custom'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('VALIDATING', 'Validating in Sandbox'),
        ('EXECUTING', 'Executing'),
        ('EXECUTED', 'Executed'),
        ('FAILED', 'Failed'),
        ('ROLLED_BACK', 'Rolled Back'),
    ]

    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='healing_actions')
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    command = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    sandbox_result = models.CharField(max_length=20, blank=True)
    execution_output = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action_type} for {self.incident}"


class RLReward(models.Model):
    """Stores reinforcement learning rewards for healing actions"""
    healing_action = models.OneToOneField(HealingAction, on_delete=models.CASCADE, related_name='reward')
    reward_value = models.IntegerField(choices=[(1, 'Success'), (-1, 'Failure')])
    state_context = models.JSONField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reward {self.reward_value} for {self.healing_action}"


class RLPolicy(models.Model):
    """Stores the RL agent's learned policy"""
    policy_name = models.CharField(max_length=100, unique=True)
    policy_data = models.JSONField()
    performance_score = models.FloatField(default=0.0)
    training_episodes = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Policy {self.policy_name} (Score: {self.performance_score})"