"""
Monitoring app configuration.

Realizes:
  - Task G: auto-start the telemetry collector and MAPE-K orchestrator when
    (and only when) the development server is actually running.
  - Task H: best-effort graceful shutdown of both services on process exit.
  - Task I: [BOOT]-prefixed log messages describing startup/shutdown.
"""

import atexit
import os
import signal
import sys

from django.apps import AppConfig
from django.conf import settings


class MonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitoring'

    # Guards against double-registration/double-shutdown if ready() or a
    # signal handler somehow fires more than once in the same process.
    _services_started = False
    _services_stopped = False

    def ready(self):
        """
        Django calls ready() for every management command (migrate,
        makemigrations, test, shell, createsuperuser, ...), not just
        runserver. We must only auto-start background services when this
        process is actually the long-running dev server.
        """
        if not self._is_runserver_command():
            return

        if not getattr(settings, 'NEUROSYNAPSE_AUTOSTART', True):
            print('[BOOT] NEUROSYNAPSE_AUTOSTART is disabled; skipping service auto-start.')
            return

        if not self._is_reloader_child_or_noreload():
            # This is the autoreloader's parent watcher process; the actual
            # child process (which sets RUN_MAIN=true) will start services.
            # Starting here too would run the collector/orchestrator twice.
            return

        self._start_services()

    # -------------------------------------------------------------------
    # Detection helpers
    # -------------------------------------------------------------------
    @staticmethod
    def _is_runserver_command():
        return len(sys.argv) > 1 and sys.argv[1] == 'runserver'

    @staticmethod
    def _is_reloader_child_or_noreload():
        """
        With Django's autoreloader enabled (the default), ready() runs once
        in the parent watcher process (RUN_MAIN unset) and once more in the
        actual reloaded child process (RUN_MAIN='true'). We only want to
        start services in the child. If --noreload is passed, there is no
        child process at all, so RUN_MAIN is never set and we must start
        unconditionally in that single process.
        """
        if '--noreload' in sys.argv:
            return True
        return os.environ.get('RUN_MAIN') == 'true'

    # -------------------------------------------------------------------
    # Service lifecycle
    # -------------------------------------------------------------------
    def _start_services(self):
        if MonitoringConfig._services_started:
            return
        MonitoringConfig._services_started = True

        print('[BOOT] NeuroSynapse starting up...')

        try:
            from monitoring.scheduler import collector
            print('[BOOT] Starting telemetry collector...')
            collector.start()
        except Exception as exc:
            print(f'[BOOT] WARNING: telemetry collector failed to start: {exc}')

        try:
            from ai_engine.orchestrator import orchestrator
            print('[BOOT] Starting MAPE-K orchestrator...')
            orchestrator.start()
        except Exception as exc:
            print(f'[BOOT] WARNING: MAPE-K orchestrator failed to start: {exc}')

        # Primary shutdown path: fires on normal interpreter exit (including
        # sys.exit() calls made by Django's own Ctrl+C/KeyboardInterrupt
        # handling in runserver).
        atexit.register(self._stop_services)

        # Defensive supplement: atexit is NOT guaranteed to run when a
        # process receives SIGTERM/SIGINT while blocked inside the WSGI dev
        # server's serve_forever() loop -- signal delivery to that blocking
        # call does not always unwind cleanly through Python's normal exit
        # path in every environment (notably some containerized/sandboxed
        # setups). Installing explicit handlers that call _stop_services()
        # and then re-raise the default disposition makes shutdown robust
        # regardless of how the process is asked to stop, while still
        # exiting via the platform's normal signal semantics.
        self._install_signal_handlers()

        print('[BOOT] System ready')

    def _install_signal_handlers(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._handle_shutdown_signal)
            except (ValueError, OSError):
                # signal.signal() only works on the main thread; if we're
                # ever imported from a non-main thread context, skip this
                # and rely on atexit alone.
                pass

    def _handle_shutdown_signal(self, signum, frame):
        self._stop_services()
        # Restore default handling and re-deliver so the process actually
        # terminates with the expected exit status.
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    @classmethod
    def _stop_services(cls):
        """
        Best-effort graceful shutdown. This is intentionally dev-only: we do
        NOT use Django's request_finished signal here, since that fires
        after every single HTTP request rather than on process exit -- it
        would stop the services after the first request instead of at
        shutdown.
        """
        if cls._services_stopped:
            return
        cls._services_stopped = True

        print('[BOOT] Shutting down services...')

        try:
            from monitoring.scheduler import collector
            collector.stop()
        except Exception as exc:
            print(f'[BOOT] WARNING: error stopping telemetry collector: {exc}')

        try:
            from ai_engine.orchestrator import orchestrator
            orchestrator.stop()
        except Exception as exc:
            print(f'[BOOT] WARNING: error stopping MAPE-K orchestrator: {exc}')

        print('[BOOT] Services stopped')
