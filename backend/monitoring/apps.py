"""
Monitoring app configuration.
"""

import os

from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitoring'

    def ready(self):
        from django.conf import settings

        if not getattr(settings, 'NEUROSYNAPSE_AUTOSTART', False):
            return

        # Django's development autoreloader imports the app twice. Start the
        # background loops only in the serving process to avoid duplicates.
        if settings.DEBUG and os.environ.get('RUN_MAIN') == 'false':
            return

        from monitoring.scheduler import collector
        from ai_engine.orchestrator import orchestrator

        collector.start()
        orchestrator.start()