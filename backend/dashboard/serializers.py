from rest_framework import serializers

from dashboard.models import HealingPolicyConfig


class HealingPolicyConfigSerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True)

    class Meta:
        model = HealingPolicyConfig
        fields = [
            'confidence_threshold', 'max_cpu_threshold', 'max_latency_threshold_ms',
            'max_packet_loss_threshold', 'healing_timeout_seconds',
            'telemetry_interval_seconds', 'rl_reward_success', 'rl_reward_failure',
            'updated_by_username', 'updated_at',
        ]
        read_only_fields = ['updated_by_username', 'updated_at']

    def validate_confidence_threshold(self, value):
        if not 0.0 <= value <= 1.0:
            raise serializers.ValidationError('confidence_threshold must be between 0.0 and 1.0')
        return value

    def validate_healing_timeout_seconds(self, value):
        if value <= 0:
            raise serializers.ValidationError('healing_timeout_seconds must be positive')
        return value

    def validate_telemetry_interval_seconds(self, value):
        if value <= 0:
            raise serializers.ValidationError('telemetry_interval_seconds must be positive')
        return value


class ManualApprovalSerializer(serializers.Serializer):
    approved = serializers.BooleanField(required=True)
