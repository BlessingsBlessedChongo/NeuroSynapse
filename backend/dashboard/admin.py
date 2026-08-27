from django.contrib import admin

from dashboard.models import HealingPolicyConfig


@admin.register(HealingPolicyConfig)
class HealingPolicyConfigAdmin(admin.ModelAdmin):
    list_display = (
        'confidence_threshold', 'max_cpu_threshold', 'max_latency_threshold_ms',
        'max_packet_loss_threshold', 'healing_timeout_seconds', 'updated_at',
    )

    def has_add_permission(self, request):
        # Singleton table: only one row (pk=1) may ever exist.
        return not HealingPolicyConfig.objects.exists()
