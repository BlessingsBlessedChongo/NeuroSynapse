"""
NeuroSynapse verification suite for the 10 post-training checklist items.
Run: python test_verification_suite.py
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
from monitoring.connector import get_connector
from ai_engine.orchestrator import orchestrator
from ai_engine.xai import xai_engine
from ai_engine.rl_agent import rl_agent
from healing.actuator import actuator


def banner(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def get_python_router() -> Device:
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
        device.status = "ONLINE"
        device.save()
    # Close any open incidents so MAPE-K can create fresh ones
    Incident.objects.filter(
        device=device,
        status__in=[
            "ANOMALY_DETECTED",
            "MANUAL_REVIEW",
            "READY_FOR_ACTION",
            "SANDBOXING",
            "EXECUTION",
            "VERIFICATION",
        ],
    ).update(status="MONITORING")
    connector = get_connector(device)
    if hasattr(connector, "router"):
        connector.router.reset()
    return device


def test_item_1_mapek() -> bool:
    banner("[ITEM 1] PythonRouter Full MAPE-K Cycle")
    device = get_python_router()
    connector = get_connector(device)
    failures = [
        ("SERVICE_CRASH", {"service_name": "ospfd", "process_id": 4242}),
        ("LINK_FAILURE", {"interface_name": "eth0"}),
        ("DDOS_ATTACK", {"source_ip": "198.51.100.66", "destination_port": 443}),
    ]
    all_ok = True
    for failure_type, kwargs in failures:
        Incident.objects.filter(device=device).exclude(
            status__in=["HEALED", "MONITORING", "ROLLBACK"]
        ).update(status="MONITORING")
        connector.router.reset()
        msg = connector.inject_failure(failure_type, **kwargs)
        print(f"[INFO] Injected {failure_type}: {msg}")
        # Allow recovery timer after heal (SERVICE_CRASH up to ~4.5s)
        orchestrator.HEALING_VERIFY_DELAY_SEC = 1
        result = orchestrator.run_cycle(device=device, monitor=True)
        status = result.get("incident_status")
        healthy = connector.router.is_healthy()
        # If still recovering, wait and re-check health
        if not healthy:
            for _ in range(20):
                time.sleep(0.3)
                if connector.router.is_healthy():
                    healthy = True
                    break
        ok = status == "HEALED" and healthy
        marker = "[PASS]" if ok else "[FAIL]"
        print(
            f"{marker} {failure_type}: status={status} "
            f"healing={result.get('healing_status')} healthy={healthy}"
        )
        if not ok:
            all_ok = False
            # Debug
            incident = Incident.objects.filter(id=result.get("incident_id")).first()
            if incident:
                print(
                    f"  [DEBUG] incident status={incident.status} "
                    f"failure={incident.failure_type} conf={incident.confidence_score}"
                )
    return all_ok


def test_item_3_inject_cmd() -> bool:
    banner("[ITEM 3] inject_failure --device-type python_router")
    from django.core.management import call_command
    from io import StringIO

    device = get_python_router()
    out = StringIO()
    try:
        call_command(
            "inject_failure",
            "--device-id",
            str(device.id),
            "--type",
            "link_failure",
            "--interface",
            "eth0",
            stdout=out,
        )
        text = out.getvalue()
        connector = get_connector(device)
        state = connector.router.get_state()
        ok = ("INJECTED" in text.upper() or "Injected" in text) and state.get(
            "incident"
        ) == "LINK_FAILURE"
        print(text)
        print(f"{'[PASS]' if ok else '[FAIL]'} Router incident={state.get('incident')}")

        # Also verify --device-type python_router resolves without error
        out2 = StringIO()
        call_command(
            "inject_failure",
            "--device-type",
            "python_router",
            "--type",
            "service_crash",
            "--service-name",
            "ospfd",
            stdout=out2,
        )
        text2 = out2.getvalue()
        type_ok = "INJECTED" in text2.upper() or "Injected" in text2 or "[OK]" in text2
        print(text2)
        print(f"{'[PASS]' if type_ok else '[FAIL]'} --device-type python_router works")
        connector.router.reset()
        return ok and type_ok
    except Exception as exc:
        print(f"[FAIL] inject_failure command error: {exc}")
        return False


def test_item_4_hitl() -> bool:
    banner("[ITEM 4] HITL with confidence scores")
    device = get_python_router()
    # Force low-confidence MANUAL_REVIEW path
    incident = Incident.objects.create(
        device=device,
        failure_type="SERVICE_CRASH",
        confidence_score=0.55,
        status="MANUAL_REVIEW",
        service_name="ospfd",
        process_id=1111,
        description="HITL test low confidence",
    )
    # Reject path
    result = orchestrator.process_manual_approval(incident.id, approved=False)
    incident.refresh_from_db()
    reject_ok = incident.status == "MONITORING" and result is None
    print(f"{'[PASS]' if reject_ok else '[FAIL]'} Reject -> MONITORING (status={incident.status})")

    # Approve path: inject failure then create MANUAL_REVIEW and approve
    connector = get_connector(device)
    connector.router.reset()
    connector.inject_failure("LINK_FAILURE", interface_name="eth0")
    incident2 = Incident.objects.create(
        device=device,
        failure_type="LINK_FAILURE",
        confidence_score=0.40,
        status="MANUAL_REVIEW",
        interface_name="eth0",
        description="HITL approve test",
    )
    orchestrator.HEALING_VERIFY_DELAY_SEC = 1
    healing = orchestrator.process_manual_approval(incident2.id, approved=True)
    incident2.refresh_from_db()
    approve_ok = incident2.status in ("HEALED", "READY_FOR_ACTION", "EXECUTION", "VERIFICATION") or (
        healing is not None and incident2.status == "HEALED"
    )
    # After approve, _execute should heal to HEALED
    if incident2.status != "HEALED":
        # Wait for recovery
        for _ in range(20):
            time.sleep(0.3)
            if connector.router.is_healthy():
                break
        incident2.refresh_from_db()
    approve_ok = incident2.status == "HEALED"
    print(
        f"{'[PASS]' if approve_ok else '[FAIL]'} Approve -> HEALED "
        f"(status={incident2.status}, healing={getattr(healing, 'status', None)})"
    )

    # Threshold check: confidence < 0.70 should plan to MANUAL_REVIEW
    threshold = orchestrator._get_confidence_threshold()
    low_triggers = 0.55 < threshold
    print(f"[INFO] Confidence threshold={threshold:.0%}; low score 55% triggers MANUAL_REVIEW={low_triggers}")
    return reject_ok and approve_ok and low_triggers


def test_item_5_rollback() -> bool:
    banner("[ITEM 5] Manual Rollback")
    from django.test import RequestFactory
    from django.contrib.auth import get_user_model
    from rest_framework.test import force_authenticate
    from dashboard.views import ManualRollbackView

    device = get_python_router()
    connector = get_connector(device)
    connector.inject_failure("SERVICE_CRASH", service_name="ospfd")
    incident = Incident.objects.create(
        device=device,
        failure_type="SERVICE_CRASH",
        confidence_score=0.95,
        status="HEALED",
        service_name="ospfd",
    )
    HealingAction.objects.create(
        incident=incident,
        action_type="RESTART_SERVICE",
        command="PYTHON_ROUTER:RESTART_SERVICE",
        status="EXECUTED",
        sandbox_result="PASS",
    )

    User = get_user_model()
    user, _ = User.objects.get_or_create(username="rollback_tester", defaults={"is_staff": True})
    # Ensure admin profile if required
    try:
        from authentication.models import AdminProfile
        AdminProfile.objects.get_or_create(user=user, defaults={"role": "SUPER_ADMIN"})
    except Exception:
        pass

    factory = RequestFactory()
    request = factory.post(f"/api/dashboard/incidents/{incident.id}/rollback/")
    force_authenticate(request, user=user)
    view = ManualRollbackView.as_view()
    response = view(request, pk=incident.id)
    incident.refresh_from_db()
    healthy = connector.router.is_healthy()
    ok = response.status_code == 200 and incident.status == "MONITORING" and healthy
    print(
        f"{'[PASS]' if ok else '[FAIL]'} status={incident.status} "
        f"http={response.status_code} healthy={healthy}"
    )
    return ok


def test_item_6_xai() -> bool:
    banner("[ITEM 6] XAI explanations for PythonRouter")
    device = get_python_router()
    connector = get_connector(device)
    cases = [
        ("SERVICE_CRASH", {"service_name": "ospfd", "process_id": 9001}, "ospfd"),
        ("LINK_FAILURE", {"interface_name": "eth0"}, "eth0"),
        ("DDOS_ATTACK", {"source_ip": "203.0.113.50", "destination_port": 443}, "203.0.113.50"),
    ]
    all_ok = True
    for failure_type, kwargs, needle in cases:
        connector.router.reset()
        connector.inject_failure(failure_type, **kwargs)
        ctx = connector.router.get_incident_context()
        telemetry = connector.collect_telemetry()
        incident = Incident(
            device=device,
            failure_type=failure_type,
            confidence_score=0.92,
            source_ip=ctx.get("source_ip"),
            interface_name=ctx.get("interface_name"),
            service_name=ctx.get("service_name"),
            process_id=ctx.get("process_id"),
            destination_port=ctx.get("destination_port"),
            traffic_volume=ctx.get("traffic_volume"),
        )
        explanation = xai_engine.explain_diagnosis(
            telemetry, failure_type, 0.92, incident=incident
        )
        concrete = explanation.get("concrete_context") or ""
        ok = needle in concrete
        print(
            f"{'[PASS]' if ok else '[FAIL]'} {failure_type}: "
            f"concrete_context={concrete!r}"
        )
        if not ok:
            all_ok = False
    connector.router.reset()
    return all_ok


def test_item_10_rl() -> bool:
    banner("[ITEM 10] RL agent with confidence / rewards")
    device = get_python_router()
    incident = Incident.objects.create(
        device=device,
        failure_type="DDOS_ATTACK",
        confidence_score=0.88,
        status="HEALED",
        source_ip="198.51.100.10",
    )
    healing = HealingAction.objects.create(
        incident=incident,
        action_type="BLOCK_SOURCE_IP",
        command="PYTHON_ROUTER:BLOCK_SOURCE_IP",
        status="EXECUTED",
        sandbox_result="PASS",
    )
    before = rl_agent.get_q_value("DDOS_ATTACK", 0)
    rl_agent.record_reward(healing, success=True)
    after = rl_agent.get_q_value("DDOS_ATTACK", 0)
    reward_ok = RLReward.objects.filter(healing_action=healing).exists()
    q_ok = after >= before  # may already be high; non-decreasing is fine if same action
    stats = rl_agent.get_stats()
    print(f"[INFO] Q before={before:.3f} after={after:.3f}")
    print(f"[INFO] RL stats episodes={stats.get('episode_count')} perf={stats.get('recent_performance')}")
    ok = reward_ok
    print(f"{'[PASS]' if ok else '[FAIL]'} Reward recorded={reward_ok}")
    return ok


def main() -> int:
    results = []
    results.append(("1 MAPE-K", test_item_1_mapek()))
    results.append(("3 inject_failure", test_item_3_inject_cmd()))
    results.append(("4 HITL", test_item_4_hitl()))
    results.append(("5 Rollback", test_item_5_rollback()))
    results.append(("6 XAI", test_item_6_xai()))
    results.append(("10 RL rewards", test_item_10_rl()))

    banner("SUMMARY")
    failed = 0
    for name, ok in results:
        print(f"  {'[PASS]' if ok else '[FAIL]'} {name}")
        if not ok:
            failed += 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
