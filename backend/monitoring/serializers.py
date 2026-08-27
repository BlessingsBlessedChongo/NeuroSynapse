"""
DRF serializers for NeuroSynapse core data models.

These provide both (a) output serialization for the dashboard/API layer and
(b) input validation for telemetry ingestion, satisfying the Reliability
non-functional requirement: 'Django Serializers validate that telemetry
inputs fall within realistic bounds (e.g., Latency > 0)'.
"""

from rest_framework import serializers

from monitoring.models import Device, HealingAction, Incident, RLPolicy, RLReward, Telemetry


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = [
            'id', 'name', 'ip_address', 'device_type', 'vendor', 'status',
            'ssh_port', 'username', 'password', 'created_at',
        ]
        extra_kwargs = {
            'password': {'write_only': True},
        }


class TelemetrySerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)

    class Meta:
        model = Telemetry
        fields = [
            'id', 'device', 'device_name', 'timestamp', 'cpu_usage',
            'memory_usage', 'latency_ms', 'packet_loss', 'bandwidth_util',
            'interface_status', 'raw_output',
        ]
        read_only_fields = ['id', 'timestamp', 'device_name']


class TelemetryIngestSerializer(serializers.Serializer):
    """
    Validates a single inbound telemetry payload before persistence.
    Enforces realistic value bounds per the SDS Security/Reliability
    requirements (e.g. latency and packet loss cannot be negative).
    """

    device_ip = serializers.IPAddressField(required=False)
    ip_address = serializers.IPAddressField(required=False)
    name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    cpu_usage = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=100)
    memory_usage = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=100)
    packet_loss = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=100)
    latency_ms = serializers.FloatField(required=False, allow_null=True, min_value=0)
    bandwidth_util = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=100)
    interface_status = serializers.JSONField(required=False, allow_null=True)
    raw_output = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get('device_ip') and not attrs.get('ip_address'):
            raise serializers.ValidationError(
                'Either device_ip or ip_address must be supplied.'
            )
        return attrs


class HealingActionSerializer(serializers.ModelSerializer):
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    incident_id = serializers.IntegerField(source='incident.id', read_only=True)
    incident_failure_type = serializers.CharField(source='incident.failure_type', read_only=True)

    class Meta:
        model = HealingAction
        fields = [
            'id', 'incident', 'incident_id', 'incident_failure_type',
            'action_type', 'action_type_display', 'command', 'status',
            'status_display', 'sandbox_result', 'execution_output',
            'created_at', 'completed_at',
        ]
        read_only_fields = fields


class RLRewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = RLReward
        fields = ['id', 'healing_action', 'reward_value', 'state_context', 'created_at']
        read_only_fields = fields


class IncidentSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    device_type = serializers.CharField(source='device.device_type', read_only=True)
    healing_actions = HealingActionSerializer(many=True, read_only=True)
    failure_type_display = serializers.CharField(source='get_failure_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    telemetry_snapshot = TelemetrySerializer(read_only=True)

    class Meta:
        model = Incident
        fields = [
            'id', 'device', 'device_name', 'device_type', 'telemetry_snapshot',
            'failure_type', 'failure_type_display', 'confidence_score',
            'status', 'status_display', 'description',
            'source_ip', 'destination_ip', 'source_port', 'destination_port',
            'interface_name', 'service_name', 'process_id', 'traffic_volume',
            'detected_at', 'resolved_at', 'healing_actions',
        ]
        read_only_fields = fields


class IncidentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views (omits nested healing actions)."""

    device_name = serializers.CharField(source='device.name', read_only=True)
    failure_type_display = serializers.CharField(source='get_failure_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Incident
        fields = [
            'id', 'device', 'device_name', 'failure_type', 'failure_type_display',
            'confidence_score', 'status', 'status_display', 'description',
            'source_ip', 'destination_ip', 'source_port', 'destination_port',
            'interface_name', 'service_name', 'process_id', 'traffic_volume',
            'detected_at', 'resolved_at',
        ]
        read_only_fields = fields


class RLPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RLPolicy
        fields = ['id', 'policy_name', 'performance_score', 'training_episodes', 'updated_at']
        read_only_fields = fields