"""
MAPE-K Orchestrator for NeuroSynapse.

Exact state machine from Figure 3.2:

MONITORING -> ANOMALY_DETECTED
                ├─► High Confidence ──► READY_FOR_ACTION
                └─► Low Confidence  ──► MANUAL_REVIEW
                                            ├─► Approve ──► READY_FOR_ACTION
                                            └─► Reject  ──► MONITORING

READY_FOR_ACTION -> SANDBOXING
                      ├─► Pass ──► EXECUTION -> VERIFICATION
                      │                        ├─► Success ──► HEALED -> MONITORING
                      │                        └─► Failure ──► ROLLBACK -> MONITORING
                      └─► Fail ──► MANUAL_REVIEW
"""

import time
import threading
import traceback

from monitoring.models import Device, Telemetry, Incident, HealingAction
from monitoring.connector import get_connector, normalize_telemetry, persist_interface_status
from ai_engine.inference import engine
from healing.actuator import actuator


# MONITORING is NOT open — it's a terminal state (system healthy)
OPEN_INCIDENT_STATUSES = [
    'ANOMALY_DETECTED',
    'MANUAL_REVIEW',
    'READY_FOR_ACTION',
    'SANDBOXING',
    'EXECUTION',
    'VERIFICATION',
]

FALSE_POSITIVE_LABELS = {'NORMAL', 'UNKNOWN'}


def timezone_now():
    from django.utils import timezone
    return timezone.now()


class NeuroSynapseOrchestrator:
    CONFIDENCE_THRESHOLD = 0.70
    HEALING_VERIFY_DELAY_SEC = 2
    INCIDENT_CHECK_INTERVAL = 5

    def __init__(self):
        self.running = False
        self.thread = None
        self.incident_check_interval = self.INCIDENT_CHECK_INTERVAL

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="NeuroSynapse-MAPE-K", daemon=True)
        self.thread.start()
        print("[ORCHESTRATOR] Started MAPE-K loop")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
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

    def _extract_context_from_telemetry(self, telemetry):
        if telemetry is None:
            return {}
        interface_status = telemetry.interface_status
        if not isinstance(interface_status, dict):
            return {}
        context = interface_status.get('__context__', {})
        if not isinstance(context, dict):
            return {}
        return context

    def _monitor(self, device, logger=None):
        self._log(f"[MONITOR] Collecting telemetry for {device.name}", logger)
        connector = get_connector(device)
        raw = connector.collect_telemetry()
        connector.disconnect()

        if raw is None:
            self._log(f"[MONITOR] No telemetry received from {device.name}", logger)
            return None

        normalized = normalize_telemetry(raw)
        if normalized is None:
            return None

        interface_status = persist_interface_status(normalized)

        telemetry = Telemetry.objects.create(
            device=device,
            cpu_usage=normalized['cpu_usage'],
            memory_usage=normalized['memory_usage'],
            packet_loss=normalized['packet_loss'],
            latency_ms=normalized['latency_ms'],
            bandwidth_util=normalized['bandwidth_util'],
            interface_status=interface_status,
            raw_output=normalized.get('raw_output', ''),
        )

        self._log(
            f"[MONITOR] Saved telemetry #{telemetry.id} "
            f"(CPU={normalized['cpu_usage']:.1f}, LOSS={normalized['packet_loss']:.1f})",
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

    def _get_confidence_threshold(self):
        try:
            from dashboard.models import HealingPolicyConfig
            return float(HealingPolicyConfig.get_solo().confidence_threshold)
        except Exception:
            return self.CONFIDENCE_THRESHOLD

    def _plan(self, device, telemetry, diagnosis, logger=None):
        self._log("[PLAN] Evaluating incident state", logger)
    
        if not diagnosis['is_anomaly']:
            self._log("[PLAN] No anomaly detected", logger)
            return None
    
        if diagnosis['failure_type'] in FALSE_POSITIVE_LABELS:
            self._log(f"[PLAN] Ignoring {diagnosis['failure_type']}", logger)
            return None
    
        failure_type = diagnosis['failure_type']
        
        # Use anomaly confidence for threshold (realistic)
        combined_confidence = float(diagnosis.get('anomaly_confidence', 0.0))
        
        # Keep classification confidence for display
        classification_confidence = float(diagnosis.get('classification_confidence', 0.0))
    
        incident_context = self._extract_context_from_telemetry(telemetry)
    
        incident = self._get_open_incident(device)
    
        if incident:
            incident.telemetry_snapshot = telemetry
            incident.failure_type = failure_type
            incident.confidence_score = combined_confidence
            incident.description = f"Updated detection for {failure_type}"
            incident.save()
            self._log(f"[PLAN] Updated existing incident #{incident.id}", logger)
        else:
            incident = Incident.objects.create(
                device=device,
                telemetry_snapshot=telemetry,
                failure_type=failure_type,
                confidence_score=combined_confidence,
                status='ANOMALY_DETECTED',
                description=f"Auto-detected {failure_type}",
                source_ip=incident_context.get('source_ip'),
                source_port=incident_context.get('source_port'),
                interface_name=incident_context.get('interface_name', ''),
                destination_ip=incident_context.get('destination_ip'),
                destination_port=incident_context.get('destination_port'),
                service_name=incident_context.get('service_name', ''),
                process_id=incident_context.get('process_id'),
                traffic_volume=incident_context.get('traffic_volume'),
            )
            self._log(f"[PLAN] Created incident #{incident.id} (ANOMALY_DETECTED)", logger)
    
        threshold = self._get_confidence_threshold()
    
        if combined_confidence >= threshold:
            incident.status = 'READY_FOR_ACTION'
            incident.save(update_fields=['status'])
            self._log(f"[PLAN] High confidence ({combined_confidence:.0%}) -> READY_FOR_ACTION", logger)
        else:
            incident.status = 'MANUAL_REVIEW'
            incident.save(update_fields=['status'])
            self._log(f"[PLAN] Low confidence ({combined_confidence:.0%}) -> MANUAL_REVIEW", logger)
    
        return incident

    def _execute(self, incident, logger=None):
        if incident.status == 'MANUAL_REVIEW':
            self._log(f"[EXECUTE] Incident #{incident.id} awaiting manual approval", logger)
            return None

        if incident.status != 'READY_FOR_ACTION':
            self._log(f"[EXECUTE] Incident #{incident.id} in state {incident.status}; skipping", logger)
            return None

        incident.status = 'SANDBOXING'
        incident.save(update_fields=['status'])
        self._log(f"[SANDBOXING] Validating remediation for {incident.failure_type}", logger)

        from ai_engine.rl_agent import rl_agent

        healing = actuator.execute_healing(incident, rl_agent=rl_agent)

        if not healing:
            incident.status = 'MANUAL_REVIEW'
            incident.save(update_fields=['status'])
            self._log(f"[SANDBOXING] Validation failed -> MANUAL_REVIEW", logger)
            return None

        incident.status = 'EXECUTION'
        incident.save(update_fields=['status'])
        self._log(f"[EXECUTION] Dispatching remediation for {incident.failure_type}", logger)

        if healing.status != 'EXECUTED':
            incident.status = 'ROLLBACK'
            incident.save(update_fields=['status'])
            rl_agent.record_reward(healing, success=False)
            self._log(f"[EXECUTION] Healing failed -> ROLLBACK", logger)
            self._perform_rollback(incident)
            return healing

        time.sleep(self.HEALING_VERIFY_DELAY_SEC)
        incident.status = 'VERIFICATION'
        incident.save(update_fields=['status'])
        self._log(f"[VERIFICATION] Verifying healing success", logger)

        is_healthy, verify_msg = actuator.verify_healing(incident)

        if is_healthy:
            incident.status = 'HEALED'
            incident.resolved_at = timezone_now()
            incident.save(update_fields=['status', 'resolved_at'])
            rl_agent.record_reward(healing, success=True)
            self._log(f"[VERIFICATION] Success -> HEALED", logger)
        else:
            incident.status = 'ROLLBACK'
            incident.save(update_fields=['status'])
            rl_agent.record_reward(healing, success=False)
            self._log(f"[VERIFICATION] Failure -> ROLLBACK", logger)
            self._perform_rollback(incident)

        return healing

    def _perform_rollback(self, incident):
        self._log(f"[ROLLBACK] Restoring previous state for incident #{incident.id}")

        last_action = HealingAction.objects.filter(
            incident=incident
        ).order_by('-created_at').first()

        if last_action:
            last_action.status = 'ROLLBACK'
            last_action.save()

        from monitoring.simulated_device import SimulatedDevice
        sim = SimulatedDevice()
        sim._default_state()

        incident.status = 'MONITORING'
        incident.save(update_fields=['status'])
        self._log(f"[ROLLBACK] Incident #{incident.id} -> MONITORING")

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
        if device is None:
            device = Device.objects.filter(status__in=['ONLINE', 'DEGRADED']).first()
            if device is None:
                device, _ = Device.objects.get_or_create(
                    ip_address='0.0.0.0',
                    defaults={'name': 'SimRouter', 'device_type': 'simulated', 'status': 'ONLINE'},
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
            result['rl_stats'] = self._knowledge(logger=logger)
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
                    self.run_cycle(device, monitor=True)
            except Exception as e:
                print(f"[ORCHESTRATOR] Error: {e}")
                traceback.print_exc()
            time.sleep(self.incident_check_interval)

    def process_manual_approval(self, incident_id, approved):
        try:
            incident = Incident.objects.get(id=incident_id, status='MANUAL_REVIEW')
        except Incident.DoesNotExist:
            print(f"[ORCHESTRATOR] Incident #{incident_id} not found or not in review")
            return None

        if not approved:
            incident.status = 'MONITORING'
            incident.save(update_fields=['status'])
            self._log(f"[MANUAL_REVIEW] Admin rejected -> MONITORING")
            return None

        incident.status = 'READY_FOR_ACTION'
        incident.save(update_fields=['status'])
        self._log(f"[MANUAL_REVIEW] Admin approved -> READY_FOR_ACTION")
        return self._execute(incident)


orchestrator = NeuroSynapseOrchestrator()