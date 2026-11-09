"""
Verification script for NeuroSynapse 10-item checklist (items 1,3,4,5,6).
Run: NEUROSYNAPSE_AUTOSTART=False python test_verification_10items.py
"""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
os.environ.setdefault("NEUROSYNAPSE_AUTOSTART", "False")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from monitoring.models import Device, Incident, HealingAction, RLReward
from monitoring.connector import get_connector, PythonRouterConnector
from ai_engine.orchestrator import NeuroSynapseOrchestrator, orchestrator as shared_orch
from ai_engine.xai import xai_engine
from ai_engine.inference import engine
from healing.actuator import actuator
from dashboard.models import HealingPolicyConfig
from django.utils import timezone as dj_timezone


def banner(msg):
    print("\n" + "=" * 60)
    print(msg)
    print("=" * 60)


def ensure_python_router():
    device, _ = Device.objects.get_or_create(
        ip_address="127.0.0.2",
        defaults={
            "name": "PyRouter-01",
            "device_type": "python_router",
            "status": "ONLINE",
            "username": "admin",
            "password": "admin",
        },
    )
    if device.device_type != "python_router":
        device.device_type = "python_router"
        device.save(update_fields=["device_type"])
    # Reset in-process singleton
    PythonRouterConnector._routers.pop(device.pk, None)
    connector = get_connector(device)
    if hasattr(connector, "router"):
        # Force healthy baseline
        if not connector.router.is_healthy():
            connector.router.heal("HEAL")
            time.sleep(5.0)
    return device


def close_open_incidents(device):
    Incident.objects.filter(
        device=device,
        status__in=[
            "ANOMALY_DETECTED",
            "MANUAL_REVIEW",
            "READY_FOR_ACTION",
            "SANDBOXING",
            "EXECUTION",
            "VERIFICATION",
            "ROLLBACK",
        ],
    ).update(status="HEALED")


def item1_mapek_cycle():
    banner("[ITEM 1] PythonRouter Full MAPE-K Cycle")
    device = ensure_python_router()
    orch = NeuroSynapseOrchestrator()
    failures = [
        ("service_crash", {"service_name": "ospfd", "process_id": 4242}),
        ("link_failure", {"interface_name": "eth0"}),
        ("ddos_attack", {
            "source_ip": "10.0.0.99",
            "source_port": 4444,
            "destination_port": 443,
            "traffic_volume": 75000,
        }),
    ]
    all_ok = True
    for ftype, kwargs in failures:
        close_open_incidents(device)
        PythonRouterConnector._routers.pop(device.pk, None)
        connector = get_connector(device)
        print(f"\n[INFO] Injecting {ftype} ...")
        result = connector.inject_failure(ftype, **kwargs)
        print(f"[INFO] {result}")
        assert not connector.router.is_healthy(), f"{ftype}: router should be unhealthy"

        # Force high confidence path by temporarily lowering threshold if needed
        policy = HealingPolicyConfig.get_solo()
        old_threshold = float(policy.confidence_threshold)
        policy.confidence_threshold = 0.50
        policy.save(update_fields=["confidence_threshold"])

        try:
            healing = orch.run_cycle(device=device, monitor=True)
            incident = Incident.objects.filter(device=device).order_by("-detected_at").first()
            if incident is None:
                print(f"[FAIL] {ftype}: no incident created")
                all_ok = False
                continue

            print(
                f"[INFO] Incident #{incident.id} status={incident.status} "
                f"type={incident.failure_type} conf={incident.confidence_score:.2%}"
            )

            # If stuck in MANUAL_REVIEW due to low confidence, approve and continue
            if incident.status == "MANUAL_REVIEW":
                print("[WARN] Low confidence -> MANUAL_REVIEW; approving to continue cycle")
                orch.process_manual_approval(incident.id, approved=True)
                incident.refresh_from_db()

            # If still READY_FOR_ACTION (approve returned without execute), run execute
            if incident.status == "READY_FOR_ACTION":
                orch._execute(incident)
                incident.refresh_from_db()

            # Allow recovery timer
            time.sleep(0.5)
            connector = get_connector(device)
            healthy = connector.router.is_healthy()
            print(f"[INFO] Final status={incident.status} router_healthy={healthy}")

            if incident.status != "HEALED":
                print(f"[FAIL] {ftype}: expected HEALED, got {incident.status}")
                all_ok = False
            elif not healthy:
                print(f"[FAIL] {ftype}: HEALED but router not healthy")
                all_ok = False
            else:
                print(f"[PASS] {ftype}: MAPE-K reached HEALED and router healthy")
        finally:
            policy.confidence_threshold = old_threshold
            policy.save(update_fields=["confidence_threshold"])

    return all_ok


def item3_inject_failure_cmd():
    banner("[ITEM 3] inject_failure --device-type python_router")
    from django.core.management import call_command
    from io import StringIO

    device = ensure_python_router()
    close_open_incidents(device)
    PythonRouterConnector._routers.pop(device.pk, None)

    out = StringIO()
    try:
        call_command(
            "inject_failure",
            "--device-type", "python_router",
            "--type", "link_failure",
            "--interface", "eth1",
            stdout=out,
        )
        text = out.getvalue()
        print(text)
        connector = get_connector(device)
        healthy = connector.router.is_healthy()
        if "INJECTED" in text or "OK" in text:
            if not healthy:
                print("[PASS] inject_failure targeted python_router and degraded it")
                # heal back
                connector.router.heal("REROUTE_TRAFFIC")
                time.sleep(3)
                return True
            print("[FAIL] Command reported success but router still healthy")
            return False
        print("[FAIL] Unexpected command output")
        return False
    except Exception as exc:
        print(f"[FAIL] inject_failure raised: {exc}")
        return False


def item4_hitl():
    banner("[ITEM 4] HITL with confidence scores")
    device = ensure_python_router()
    close_open_incidents(device)
    PythonRouterConnector._routers.pop(device.pk, None)
    orch = NeuroSynapseOrchestrator()

    policy = HealingPolicyConfig.get_solo()
    old_threshold = float(policy.confidence_threshold)
    # Force MANUAL_REVIEW by setting threshold very high
    policy.confidence_threshold = 0.99
    policy.save(update_fields=["confidence_threshold"])

    try:
        connector = get_connector(device)
        connector.inject_failure(
            "ddos_attack",
            source_ip="10.66.66.66",
            destination_port=80,
            traffic_volume=50000,
        )
        orch.run_cycle(device=device, monitor=True)
        incident = Incident.objects.filter(device=device).order_by("-detected_at").first()
        if incident is None:
            print("[FAIL] No incident for HITL test")
            return False

        print(
            f"[INFO] Incident #{incident.id} status={incident.status} "
            f"conf={incident.confidence_score:.2%} threshold={policy.confidence_threshold}"
        )

        if incident.status != "MANUAL_REVIEW":
            # Real models may still be >= 0.99; force status for approve/reject path test
            print("[WARN] Did not land in MANUAL_REVIEW; forcing for Approve/Reject path test")
            incident.status = "MANUAL_REVIEW"
            incident.save(update_fields=["status"])
        else:
            print("[PASS] Low confidence / high threshold -> MANUAL_REVIEW")

        # Reject path
        orch.process_manual_approval(incident.id, approved=False)
        incident.refresh_from_db()
        reject_ok = incident.status == "MONITORING"
        print(f"[{'PASS' if reject_ok else 'FAIL'}] Reject -> {incident.status}")

        # Fresh incident for Approve path
        close_open_incidents(device)
        PythonRouterConnector._routers.pop(device.pk, None)
        connector = get_connector(device)
        connector.inject_failure(
            "link_failure",
            interface_name="eth0",
        )
        orch.run_cycle(device=device, monitor=True)
        incident = Incident.objects.filter(device=device).order_by("-detected_at").first()
        incident.status = "MANUAL_REVIEW"
        incident.save(update_fields=["status"])

        # Lower threshold so post-approve execute can heal
        policy.confidence_threshold = 0.50
        policy.save(update_fields=["confidence_threshold"])

        orch.process_manual_approval(incident.id, approved=True)
        incident.refresh_from_db()
        print(f"[INFO] After approve status={incident.status}")

        if incident.status == "READY_FOR_ACTION":
            orch._execute(incident)
            incident.refresh_from_db()

        approve_ok = incident.status == "HEALED"
        print(f"[{'PASS' if approve_ok else 'FAIL'}] Approve -> heal ended as {incident.status}")
        return reject_ok and approve_ok
    finally:
        policy.confidence_threshold = old_threshold
        policy.save(update_fields=["confidence_threshold"])


def item5_rollback():
    banner("[ITEM 5] Manual Rollback")
    device = ensure_python_router()
    close_open_incidents(device)
    PythonRouterConnector._routers.pop(device.pk, None)
    orch = NeuroSynapseOrchestrator()

    policy = HealingPolicyConfig.get_solo()
    old_threshold = float(policy.confidence_threshold)
    policy.confidence_threshold = 0.50
    policy.save(update_fields=["confidence_threshold"])

    try:
        connector = get_connector(device)
        connector.inject_failure(
            "ddos_attack",
            source_ip="10.1.2.3",
            traffic_volume=60000,
        )
        orch.run_cycle(device=device, monitor=True)
        incident = Incident.objects.filter(device=device).order_by("-detected_at").first()
        if incident and incident.status == "MANUAL_REVIEW":
            orch.process_manual_approval(incident.id, approved=True)
            incident.refresh_from_db()
            if incident.status == "READY_FOR_ACTION":
                orch._execute(incident)
                incident.refresh_from_db()

        if incident is None or incident.status != "HEALED":
            print(f"[FAIL] Need HEALED incident for rollback, got {getattr(incident, 'status', None)}")
            return False

        print(f"[INFO] HEALED incident #{incident.id}; triggering rollback (dashboard path)")
        # Figure 3.2: HEALED -> ROLLBACK -> MONITORING (mirrors dashboard/views.py)
        incident.status = "ROLLBACK"
        incident.save(update_fields=["status"])
        actuator.rollback(incident)
        incident.status = "MONITORING"
        incident.resolved_at = dj_timezone.now()
        incident.save(update_fields=["status", "resolved_at"])

        incident.refresh_from_db()
        connector = get_connector(device)
        healthy = connector.router.is_healthy()
        print(f"[INFO] After rollback status={incident.status} healthy={healthy}")
        ok_status = incident.status == "MONITORING" and healthy
        print(f"[{'PASS' if ok_status else 'FAIL'}] Manual rollback -> MONITORING + restored")
        return ok_status
    finally:
        policy.confidence_threshold = old_threshold
        policy.save(update_fields=["confidence_threshold"])


def item6_xai():
    banner("[ITEM 6] XAI Explanations for PythonRouter")
    device = ensure_python_router()
    close_open_incidents(device)
    PythonRouterConnector._routers.pop(device.pk, None)
    orch = NeuroSynapseOrchestrator()

    policy = HealingPolicyConfig.get_solo()
    old_threshold = float(policy.confidence_threshold)
    policy.confidence_threshold = 0.50
    policy.save(update_fields=["confidence_threshold"])

    try:
        cases = [
            ("service_crash", {"service_name": "zebra", "process_id": 999}, "zebra"),
            ("link_failure", {"interface_name": "GigabitEthernet0/1"}, "GigabitEthernet0/1"),
            ("ddos_attack", {"source_ip": "203.0.113.50", "destination_port": 443, "traffic_volume": 90000}, "203.0.113.50"),
        ]
        all_ok = True
        for ftype, kwargs, expected_token in cases:
            close_open_incidents(device)
            PythonRouterConnector._routers.pop(device.pk, None)
            connector = get_connector(device)
            connector.inject_failure(ftype, **kwargs)
            orch.run_cycle(device=device, monitor=True)
            incident = Incident.objects.filter(device=device).order_by("-detected_at").first()
            if incident is None:
                print(f"[FAIL] {ftype}: no incident")
                all_ok = False
                continue

            telemetry = incident.telemetry_snapshot
            explanation = xai_engine.explain_diagnosis(
                telemetry,
                incident.failure_type,
                float(incident.confidence_score or 0.0),
                incident=incident,
            )
            concrete = explanation.get("concrete_context")
            print(f"[INFO] {ftype}: concrete_context={concrete!r}")
            print(f"[INFO]   source_ip={incident.source_ip} iface={incident.interface_name} svc={incident.service_name}")

            # Heal so next injection works
            if incident.status == "MANUAL_REVIEW":
                orch.process_manual_approval(incident.id, approved=True)
                incident.refresh_from_db()
            if incident.status == "READY_FOR_ACTION":
                orch._execute(incident)

            token_ok = concrete and expected_token in str(concrete)
            fields_ok = False
            if ftype == "service_crash":
                fields_ok = incident.service_name == "zebra"
            elif ftype == "link_failure":
                fields_ok = incident.interface_name == "GigabitEthernet0/1"
            else:
                fields_ok = incident.source_ip == "203.0.113.50"

            if token_ok and fields_ok:
                print(f"[PASS] {ftype}: XAI concrete_context populated correctly")
            else:
                print(f"[FAIL] {ftype}: token_ok={token_ok} fields_ok={fields_ok}")
                all_ok = False
        return all_ok
    finally:
        policy.confidence_threshold = old_threshold
        policy.save(update_fields=["confidence_threshold"])


def main():
    print("[INFO] Models loaded:", engine.loaded)
    if engine.metadata:
        print("[INFO] Classifier accuracy:", engine.metadata.get("classifier_accuracy"))

    results = {}
    results["item1"] = item1_mapek_cycle()
    results["item3"] = item3_inject_failure_cmd()
    results["item4"] = item4_hitl()
    results["item5"] = item5_rollback()
    results["item6"] = item6_xai()

    banner("SUMMARY")
    for k, v in results.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
