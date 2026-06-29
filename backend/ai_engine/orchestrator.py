"""
MAPE-K Orchestrator for NeuroSynapse.

Ironclad state machine:
  MONITOR -> ANALYZE -> PLAN -> EXECUTE -> KNOWLEDGE
"""

import time
import threading
from datetime import datetime

from monitoring.models import Device, Telemetry, Incident
from monitoring.connector import get_connector, normalize_telemetry, attach_metrics_to_interface_status
from ai_engine.inference import engine
from healing.actuator import actuator


OPEN_INCIDENT_STATUSES = [
    'DETECTED',
    'DIAGNOSING',
    'READY_FOR_ACTION',
    'HEALING',
    'MANUAL_REVIEW',
]

FALSE_POSITIVE_LABELS = {'NORMAL', 'UNKNOWN'}


class NeuroSynapseOrchestrator:
    CONFIDENCE_THRESHOLD = 0.70
    HEALING_VERIFY_DELAY_SEC = 2

    def __init__(self):
        self.running = False
        self.thread = None
        self.incident_check_interval = 5

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print("[ORCHESTRATOR] Started MAPE-K loop")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        actuator.disconnect_all()
        print("[ORCHESTRATOR] Stopped")

    def _log(self, message, logger=None):
        if logger:
            logger(message)
        else:
            print(message)

    def _get_latest_telemetry(self, device):
        return Telemetry.objects.filter(device=device).order_by('-timestamp').first()

    def _get_open_incident(self, device):
        return Incident.objects.filter(
            device=device,
            status__in=OPEN_INCIDENT_STATUSES,
        ).order_by('-detected_at').first()

    def _monitor(self, device, logger=None):
        self._log(f"[MONITOR] Collecting telemetry for {device.name}", logger)
        connector = get_connector(device)
        raw = connector.collect_telemetry()
        connector.disconnect()

        if not raw:
            self._log(f"[MONITOR] No telemetry received from {device.name}", logger)
            return None

        normalized = normalize_telemetry(raw)
        telemetry = Telemetry.objects.create(
            device=device,
            cpu_usage=normalized['cpu_usage'],
            memory_usage=normalized['memory_usage'],
            packet_loss=normalized['packet_loss'],
            latency_ms=normalized['latency_ms'],
            bandwidth_util=normalized['bandwidth_util'],
            interface_status=attach_metrics_to_interface_status(normalized),
            raw_output=normalized.get('raw_output', ''),
        )
        self._log(
            f"[MONITOR] Saved telemetry #{telemetry.id} "
            f"(features={normalized['cpu_usage']}, {normalized['packet_loss']}, "
            f"{normalized['interface_up_count']})",
            logger,
        )
        return telemetry

    def _analyze(self, telemetry, logger=None):
        self._log("[ANALYZE] Running inference engine", logger)
        diagnosis = engine.diagnose(telemetry)
        self._log(
            f"[ANALYZE] anomaly={diagnosis['is_anomaly']} "
            f"type={diagnosis['failure_type']} "
            f"confidence={diagnosis['classification_confidence']:.2%}",
            logger,
        )
        return diagnosis

    def _plan(self, device, telemetry, diagnosis, logger=None):
        self._log("[PLAN] Evaluating incident state", logger)

        if not diagnosis['is_anomaly']:
            self._log("[PLAN] No anomaly detected; no incident action required", logger)
            return None

        if diagnosis['failure_type'] in FALSE_POSITIVE_LABELS:
            self._log(
                f"[PLAN] False positive filtered ({diagnosis['failure_type']})",
                logger,
            )
            return None

        incident = self._get_open_incident(device)
        confidence = float(diagnosis['classification_confidence'])
        if diagnosis['is_anomaly'] and confidence <= 0.0:
            confidence = float(diagnosis.get('anomaly_confidence', 0.0))
        combined_confidence = max(
            float(diagnosis.get('anomaly_confidence', 0.0)),
            confidence,
        )

        if incident:
            incident.telemetry_snapshot = telemetry
            incident.failure_type = diagnosis['failure_type']
            incident.confidence_score = combined_confidence
            incident.description = f"Updated detection for {diagnosis['failure_type']}"
            incident.save()
            self._log(f"[PLAN] Updated open incident #{incident.id}", logger)
        else:
            incident = Incident.objects.create(
                device=device,
                telemetry_snapshot=telemetry,
                failure_type=diagnosis['failure_type'],
                confidence_score=confidence,
                status='DETECTED',
                description=f"Auto-detected {diagnosis['failure_type']}",
            )
            self._log(f"[PLAN] Created incident #{incident.id}", logger)

        if combined_confidence >= self.CONFIDENCE_THRESHOLD:
            incident.status = 'READY_FOR_ACTION'
            incident.save(update_fields=['status'])
            self._log(
                f"[PLAN] Confidence {combined_confidence:.0%} >= "
                f"{self.CONFIDENCE_THRESHOLD:.0%}; routing to auto-heal",
                logger,
            )
        else:
            incident.status = 'MANUAL_REVIEW'
            incident.save(update_fields=['status'])
            self._log(
                f"[PLAN] Confidence {combined_confidence:.0%} < "
                f"{self.CONFIDENCE_THRESHOLD:.0%}; routing to MANUAL_REVIEW",
                logger,
            )

        return incident

    def _execute(self, incident, logger=None):
        if incident.status == 'MANUAL_REVIEW':
            self._log(
                f"[EXECUTE] Incident #{incident.id} awaiting manual approval",
                logger,
            )
            return None

        if incident.status not in ('READY_FOR_ACTION', 'DETECTED'):
            if incident.status == 'HEALING':
                existing = HealingAction.objects.filter(incident=incident).order_by('-created_at').first()
                if existing and existing.status in ('EXECUTED', 'EXECUTING', 'VALIDATING'):
                    self._log(
                        f"[EXECUTE] Incident #{incident.id} healing already in progress/completed",
                        logger,
                    )
                    return existing
            self._log(
                f"[EXECUTE] Incident #{incident.id} in state {incident.status}; skipping",
                logger,
            )
            return None

        self._log(f"[EXECUTE] Dispatching remediation for {incident.failure_type}", logger)

        from ai_engine.rl_agent import rl_agent

        healing = actuator.execute_healing(incident, rl_agent=rl_agent)
        if not healing:
            self._log(f"[EXECUTE] No healing action created for incident #{incident.id}", logger)
            return None

        if healing.status != 'EXECUTED':
            incident.status = 'FAILED'
            incident.save(update_fields=['status'])
            rl_agent.record_reward(healing, success=False)
            self._log(f"[EXECUTE] Healing failed for incident #{incident.id}", logger)
            return healing

        time.sleep(self.HEALING_VERIFY_DELAY_SEC)
        is_healthy, verify_msg = actuator.verify_healing(incident)
        self._log(f"[EXECUTE] Verification: {verify_msg}", logger)

        if is_healthy:
            self._log(f"[EXECUTE] Incident #{incident.id} closed as HEALED", logger)
            rl_agent.record_reward(healing, success=True)
        else:
            actuator.rollback(incident)
            rl_agent.record_reward(healing, success=False)
            self._log(f"[EXECUTE] Incident #{incident.id} rolled back", logger)

        return healing

    def _knowledge(self, logger=None):
        from ai_engine.rl_agent import rl_agent

        stats = rl_agent.get_stats()
        self._log(
            f"[KNOWLEDGE] episodes={stats['episode_count']} "
            f"performance={stats['recent_performance']:.1%} "
            f"epsilon={stats['epsilon']}",
            logger,
        )
        return stats

    def run_cycle(self, device=None, logger=None, monitor=True):
        """
        Execute exactly one end-to-end MAPE-K iteration for a device.
        Returns a structured result dictionary for programmatic verification.
        """
        if device is None:
            device = Device.objects.filter(status__in=['ONLINE', 'DEGRADED']).first()
            if device is None:
                device, _ = Device.objects.get_or_create(
                    ip_address='0.0.0.0',
                    defaults={
                        'name': 'SimRouter',
                        'device_type': 'simulated',
                        'status': 'ONLINE',
                    },
                )

        result = {
            'device': device.name,
            'telemetry_id': None,
            'incident_id': None,
            'incident_status': None,
            'healing_status': None,
            'rl_stats': None,
        }

        telemetry = self._monitor(device, logger=logger) if monitor else self._get_latest_telemetry(device)
        if telemetry is None:
            return result

        result['telemetry_id'] = telemetry.id

        diagnosis = self._analyze(telemetry, logger=logger)
        incident = self._plan(device, telemetry, diagnosis, logger=logger)
        if incident is None:
            result['rl_stats'] = self._knowledge(logger=logger)
            return result

        result['incident_id'] = incident.id
        healing = self._execute(incident, logger=logger)
        incident.refresh_from_db()

        result['incident_status'] = incident.status
        result['healing_status'] = healing.status if healing else None
        result['rl_stats'] = self._knowledge(logger=logger)
        return result

    def _loop(self):
        while self.running:
            try:
                devices = Device.objects.filter(status__in=['ONLINE', 'DEGRADED'])
                for device in devices:
                    self.run_cycle(device, monitor=False)
            except Exception as e:
                print(f"[ORCHESTRATOR] Error: {e}")
                import traceback
                traceback.print_exc()
            time.sleep(self.incident_check_interval)

    def process_manual_approval(self, incident_id, approved):
        try:
            incident = Incident.objects.get(id=incident_id, status='MANUAL_REVIEW')
        except Incident.DoesNotExist:
            print(f"[ORCHESTRATOR] Incident #{incident_id} not found or not in review")
            return None

        if not approved:
            incident.status = 'DETECTED'
            incident.save(update_fields=['status'])
            return None

        incident.status = 'READY_FOR_ACTION'
        incident.save(update_fields=['status'])
        return self._execute(incident)


orchestrator = NeuroSynapseOrchestrator()
