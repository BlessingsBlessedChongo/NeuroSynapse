"""Write detailed, human-readable MAPE-K healing logs, one file per incident.

This is the audit trail an operator downloads from the dashboard to see
exactly what NeuroSynapse observed, diagnosed, decided, executed, verified,
and learned for a given incident -- every MAPE-K phase, with the real
numbers behind each decision, not just a status label.
"""

from datetime import datetime
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "healing"

RULE = "=" * 78
THIN_RULE = "-" * 78


def incident_log_path(incident):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = incident.detected_at.strftime("%Y%m%d_%H%M%S")
    return LOG_DIR / f"incident_{incident.id}_{timestamp}.log"


def _fmt_duration(seconds):
    if seconds is None:
        return "N/A"
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}m {secs:.1f}s"


def _section(title):
    return ["", RULE, f" {title}", RULE]


def _telemetry_block(telemetry):
    lines = []
    if telemetry is None:
        lines.append("  No telemetry snapshot attached to this incident.")
        return lines

    lines.append(f"  Telemetry ID      : #{telemetry.id}")
    lines.append(f"  Collected At      : {telemetry.timestamp.isoformat()}")
    lines.append("")
    lines.append("  Metric                    Value        Normal Range")
    lines.append("  " + "-" * 58)
    metric_rows = [
        ("CPU usage", telemetry.cpu_usage, "%", "20-45%"),
        ("Memory usage", telemetry.memory_usage, "%", "30-50%"),
        ("Packet loss", telemetry.packet_loss, "%", "<2%"),
        ("Latency", telemetry.latency_ms, "ms", "<10ms"),
        ("Bandwidth utilization", telemetry.bandwidth_util, "%", "20-50%"),
    ]
    for label, value, unit, normal in metric_rows:
        value_str = f"{value:.1f}{unit}" if value is not None else "N/A"
        lines.append(f"  {label:<26}{value_str:<13}{normal}")

    interface_status = telemetry.interface_status or {}
    real_interfaces = {
        name: details for name, details in interface_status.items()
        if isinstance(details, dict) and not str(name).startswith("__")
    }
    if real_interfaces:
        lines.append("")
        lines.append("  Interface status:")
        for name, details in sorted(real_interfaces.items()):
            iface_status = details.get("status", "unknown")
            marker = "UP  " if iface_status == "up" else "DOWN"
            lines.append(f"    [{marker}] {name}")

    metrics = interface_status.get("__metrics__", {}) if isinstance(interface_status, dict) else {}
    if metrics:
        lines.append("")
        lines.append(f"  OSPF neighbors    : {metrics.get('ospf_neighbors', 'N/A')}")
        lines.append(f"  Interface errors  : {metrics.get('error_count', 'N/A')}")

    return lines


def _xai_block(incident, telemetry):
    lines = []
    if telemetry is None:
        lines.append("  No telemetry available -- diagnosis could not be explained.")
        return lines

    try:
        from ai_engine.xai import xai_engine
        explanation = xai_engine.explain_diagnosis(
            telemetry, incident.failure_type, incident.confidence_score, incident=incident
        )
    except Exception as exc:
        lines.append(f"  XAI explanation unavailable ({exc}).")
        return lines

    lines.append(f"  Diagnosis         : {incident.get_failure_type_display()}")
    lines.append(f"  Confidence        : {incident.confidence_score:.2%} "
                 f"({explanation.get('confidence_level', 'N/A')})")
    if explanation.get("concrete_context"):
        lines.append(f"  Context           : {explanation['concrete_context']}")
    lines.append("")
    lines.append("  Summary:")
    lines.append(f"    {explanation.get('summary', 'N/A')}")
    lines.append("")
    lines.append("  Key evidence:")
    for item in explanation.get("key_evidence", []):
        lines.append(f"    - {item}")
    lines.append("")
    lines.append("  What this means:")
    lines.append(f"    {explanation.get('what_this_means', 'N/A')}")
    if explanation.get("contributing_factors"):
        lines.append("")
        lines.append("  Contributing factors:")
        for item in explanation["contributing_factors"]:
            lines.append(f"    - {item}")
    return lines


def _plan_block(incident):
    lines = []
    try:
        from dashboard.models import HealingPolicyConfig
        threshold = float(HealingPolicyConfig.get_solo().confidence_threshold)
    except Exception:
        threshold = 0.70

    confidence = incident.confidence_score
    lines.append(f"  Confidence threshold (policy) : {threshold:.0%}")
    lines.append(f"  Diagnosis confidence          : {confidence:.2%}")
    if confidence > threshold:
        lines.append(
            f"  Decision                      : AUTO-HEAL "
            f"({confidence:.0%} > {threshold:.0%} threshold -> READY_FOR_ACTION)"
        )
    else:
        lines.append(
            f"  Decision                      : ESCALATE TO HUMAN "
            f"({confidence:.0%} <= {threshold:.0%} threshold -> MANUAL_REVIEW)"
        )
    return lines


def _rl_block(healing_action):
    lines = []
    reward = getattr(healing_action, "reward", None)
    if reward is None:
        lines.append("  No RL reward recorded for this action yet.")
        return lines

    ctx = reward.state_context or {}
    outcome = "SUCCESS" if reward.reward_value > 0 else "FAILURE"
    lines.append(f"  Outcome recorded      : {outcome} (reward {reward.reward_value:+d})")
    if "q_value_before" in ctx and "q_value_after" in ctx:
        delta = ctx["q_value_after"] - ctx["q_value_before"]
        lines.append(
            f"  Q-value update        : {ctx['q_value_before']:.4f} -> "
            f"{ctx['q_value_after']:.4f} ({delta:+.4f})"
        )
    if "episode_count" in ctx:
        lines.append(
            f"  Agent state after     : episode {ctx['episode_count']}, "
            f"epsilon {ctx.get('epsilon', 'N/A')}, "
            f"recent performance {ctx.get('recent_performance', 0):.1%}, "
            f"optimization delta {ctx.get('optimization_delta', 0):+.1%}"
        )
    if ctx.get("timed_out"):
        lines.append("  Note                  : action timed out before verification")
    return lines


def _action_block(index, action):
    lines = [f"[STEP {index}] EXECUTE + VERIFY  (HealingAction #{action.id})"]
    lines.append(f"  Action type       : {action.get_action_type_display()}")
    lines.append(f"  Command dispatched: {action.command}")
    lines.append(f"  Sandbox result    : {action.sandbox_result or 'N/A'}")
    lines.append(f"  Final status      : {action.get_status_display()}")

    if action.created_at and action.completed_at:
        duration = (action.completed_at - action.created_at).total_seconds()
        lines.append(f"  Started           : {action.created_at.isoformat()}")
        lines.append(f"  Completed         : {action.completed_at.isoformat()}")
        lines.append(f"  Duration          : {_fmt_duration(duration)}")
    else:
        lines.append(f"  Started           : {action.created_at.isoformat() if action.created_at else 'N/A'}")
        lines.append("  Completed         : still in progress")

    if action.execution_output:
        lines.append("")
        lines.append("  Output:")
        for line in action.execution_output.strip().splitlines():
            lines.append(f"    {line}")

    lines.append("")
    lines.append("  Reinforcement learning update:")
    for line in _rl_block(action):
        lines.append(f"  {line}")

    return lines


def write_incident_log(incident, status=None):
    """Persist the current incident and all of its actions as a detailed,
    plain-text audit log covering every MAPE-K phase: Monitor, Analyze,
    Plan, Execute, Verify, and Knowledge (RL). Safe to call repeatedly --
    each call regenerates the file from the incident's current state, so
    it never goes stale after a retry, manual approval, or rollback.
    """
    path = incident_log_path(incident)
    actions = list(incident.healing_actions.select_related("reward").order_by("created_at"))
    telemetry = incident.telemetry_snapshot

    lines = [RULE, " NEUROSYNAPSE HEALING LOG -- MAPE-K AUDIT TRAIL", RULE]
    lines.append(f"  Incident ID       : #{incident.id}")
    lines.append(f"  Device            : {incident.device.name} ({incident.device.ip_address}, "
                 f"{incident.device.get_device_type_display() if hasattr(incident.device, 'get_device_type_display') else incident.device.device_type})")
    lines.append(f"  Failure type      : {incident.get_failure_type_display()}")
    lines.append(f"  Detected at       : {incident.detected_at.isoformat()}")
    if incident.resolved_at:
        total_seconds = (incident.resolved_at - incident.detected_at).total_seconds()
        lines.append(f"  Resolved at       : {incident.resolved_at.isoformat()}")
        lines.append(f"  Total time to heal: {_fmt_duration(total_seconds)}")
    else:
        lines.append("  Resolved at       : not yet resolved")
    lines.append(f"  Current status    : {incident.get_status_display()} ({status or incident.status})")
    lines.append(f"  Healing attempts  : {len(actions)}")

    lines += _section("STEP 1: MONITOR -- Telemetry Collection")
    lines += _telemetry_block(telemetry)

    lines += _section("STEP 2: ANALYZE -- AI Diagnosis (Explainable AI)")
    lines += _xai_block(incident, telemetry)

    lines += _section("STEP 3: PLAN -- Confidence Gate / HITL Decision")
    lines += _plan_block(incident)

    if actions:
        lines += _section("STEPS 4+: EXECUTE / VERIFY / LEARN")
        for index, action in enumerate(actions, start=4):
            lines += _action_block(index, action)
            lines.append(THIN_RULE)
    else:
        lines += _section("STEPS 4+: EXECUTE / VERIFY / LEARN")
        lines.append("  No healing action was dispatched (incident awaiting review, or")
        lines.append("  resolved independently before any action was taken).")

    lines += _section("FINAL OUTCOME")
    lines.append(f"  Status  : {status or incident.status}")
    if incident.status == 'HEALED':
        lines.append("  Result  : Device confirmed healthy by independent post-healing")
        lines.append("            telemetry check -- this is a verified recovery, not an")
        lines.append("            assumed one.")
    elif incident.status == 'MANUAL_REVIEW':
        lines.append("  Result  : Confidence below policy threshold -- awaiting a human")
        lines.append("            operator's approve/reject decision before any healing")
        lines.append("            action is dispatched.")
    elif incident.status == 'ROLLBACK':
        lines.append("  Result  : Healing action failed verification and was rolled back.")
        lines.append("            The incident will be re-evaluated on the next cycle (up")
        lines.append("            to the configured auto-retry limit) or escalated to")
        lines.append("            manual review.")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append(RULE)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
