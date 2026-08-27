from django.conf import settings
from django.db import models


class HealingPolicyConfig(models.Model):
    """
    Realizes UC-01 'Configure Healing Policies' from the SDS Use Case model:
    'The Administrator defines the operational thresholds (e.g., maximum
    latency, CPU limits) and Reward parameters for the RL agent.'

    Implemented as a single-row (singleton) configuration table so the
    Autonomous Core always has exactly one active policy to read from.
    """

    confidence_threshold = models.FloatField(
        default=0.70,
        help_text='Minimum classification confidence required to auto-heal '
                   'without human approval (Objective 2 / FR4).',
    )
    max_cpu_threshold = models.FloatField(
        default=85.0, help_text='CPU utilization (%) considered critical.'
    )
    max_latency_threshold_ms = models.FloatField(
        default=100.0, help_text='Latency (ms) considered critical.'
    )
    max_packet_loss_threshold = models.FloatField(
        default=10.0, help_text='Packet loss (%) considered critical.'
    )
    healing_timeout_seconds = models.IntegerField(
        default=30,
        help_text='Maximum time allowed for a healing action to complete '
                   '(Objective 3: within 30 seconds of detection).',
    )
    telemetry_interval_seconds = models.IntegerField(
        default=5, help_text='Telemetry polling interval in seconds.'
    )
    rl_reward_success = models.FloatField(default=1.0)
    rl_reward_failure = models.FloatField(default=-1.0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Healing Policy Configuration'
        verbose_name_plural = 'Healing Policy Configuration'

    def __str__(self):
        return f"Policy (confidence>={self.confidence_threshold}, updated {self.updated_at})"

    def save(self, *args, **kwargs):
        # Enforce singleton: always overwrite row with pk=1.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
