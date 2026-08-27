from django.contrib import admin
from monitoring.models import Device, Telemetry, Incident, HealingAction, RLReward, RLPolicy, SimulatorState


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['name', 'ip_address', 'device_type', 'vendor', 'status', 'ssh_port', 'created_at']
    list_filter = ['status', 'device_type', 'vendor']
    search_fields = ['name', 'ip_address', 'vendor']
    list_editable = ['status', 'ssh_port']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Device Information', {
            'fields': ('name', 'ip_address', 'device_type', 'vendor', 'status')
        }),
        ('SSH Credentials', {
            'fields': ('ssh_port', 'username', 'password'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Telemetry)
class TelemetryAdmin(admin.ModelAdmin):
    list_display = ['device', 'timestamp', 'cpu_usage', 'memory_usage', 'packet_loss', 'latency_ms']
    list_filter = ['device', 'timestamp']
    search_fields = ['device__name', 'device__ip_address']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ['id', 'device', 'failure_type', 'confidence_score', 'status', 'detected_at', 'resolved_at']
    list_filter = ['status', 'failure_type', 'device']
    search_fields = ['device__name', 'description', 'source_ip', 'interface_name', 'service_name']
    readonly_fields = ['detected_at', 'resolved_at']
    date_hierarchy = 'detected_at'


@admin.register(HealingAction)
class HealingActionAdmin(admin.ModelAdmin):
    list_display = ['id', 'incident', 'action_type', 'status', 'created_at', 'completed_at']
    list_filter = ['status', 'action_type']
    search_fields = ['command', 'execution_output']
    readonly_fields = ['created_at', 'completed_at']
    date_hierarchy = 'created_at'


@admin.register(RLReward)
class RLRewardAdmin(admin.ModelAdmin):
    list_display = ['id', 'healing_action', 'reward_value', 'created_at']
    list_filter = ['reward_value']
    readonly_fields = ['created_at']


@admin.register(RLPolicy)
class RLPolicyAdmin(admin.ModelAdmin):
    list_display = ['policy_name', 'performance_score', 'training_episodes', 'updated_at']
    search_fields = ['policy_name']
    readonly_fields = ['updated_at']


@admin.register(SimulatorState)
class SimulatorStateAdmin(admin.ModelAdmin):
    list_display = ['health', 'failure_type', 'updated_at']
    readonly_fields = ['updated_at']