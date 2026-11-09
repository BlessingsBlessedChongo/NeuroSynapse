"""
Database-backed simulated network device for NeuroSynapse.

The simulator provides deterministic network-failure profiles for
MAPE-K end-to-end testing.

Supported failures:

    SERVICE_CRASH
    LINK_FAILURE
    DDOS_ATTACK

State is persisted in the SimulatorState Django model, so failure
injection from a separate management command (or API call) is visible
to the running server process.
"""

import random
from threading import Lock

from typing import Any, Dict, List, Optional, Tuple


# ==============================================================
# ML FEATURE CONTRACT
# ==============================================================

TELEMETRY_FEATURE_ORDER: List[str] = [
    "cpu_usage",
    "memory_usage",
    "packet_loss",
    "latency_ms",
    "bandwidth_util",
    "interface_up_count",
    "ospf_neighbors",
    "error_count",
]


# ==============================================================
# FAILURE ALIASES
# ==============================================================

FAILURE_ALIASES: Dict[str, str] = {
    "service_crash": "SERVICE_CRASH",
    "service-crash": "SERVICE_CRASH",
    "link_failure": "LINK_FAILURE",
    "link-failure": "LINK_FAILURE",
    "ddos": "DDOS_ATTACK",
    "ddos_attack": "DDOS_ATTACK",
    "ddos-attack": "DDOS_ATTACK",
}


SUPPORTED_FAILURES = {
    "SERVICE_CRASH",
    "LINK_FAILURE",
    "DDOS_ATTACK",
}


# Which failure type each healing action_type is meant to resolve.
# Used so heal() only "succeeds" when the action actually targets the
# failure that's currently active.
ACTION_TO_FAILURE: Dict[str, Optional[str]] = {
    "RESTART_SERVICE": "SERVICE_CRASH",
    "REBOOT_DEVICE": "SERVICE_CRASH",
    "REROUTE_TRAFFIC": "LINK_FAILURE",
    "BLOCK_SOURCE_IP": "DDOS_ATTACK",
    "UNBLOCK_SOURCE_IP": "DDOS_ATTACK",
    "CLEAR_TRAFFIC_SHAPING": "DDOS_ATTACK",
    "HEAL": None,  # generic action: allowed against any active failure
}


class SimulatedDevice:
    """Thread-safe simulated network device with database-backed state."""

    _lock = Lock()

    def __init__(self, name: str = "SimRouter"):
        self.name = name

    # ==========================================================
    # DATABASE STATE HELPERS
    # ==========================================================

    def _get_state(self):
        """Return the singleton SimulatorState row."""
        from monitoring.models import SimulatorState
        state, _ = SimulatorState.objects.get_or_create(id=1)
        return state

    def _default_state(self) -> None:
        """Reset the simulator to a completely healthy state."""
        state = self._get_state()
        state.health = "HEALTHY"
        state.failure_type = None
        state.context = {}
        state.save()

    # ==========================================================
    # STATE INSPECTION
    # ==========================================================

    def reset(self) -> None:
        """Explicitly reset the simulator to healthy."""
        with self._lock:
            self._default_state()

    def get_state(self) -> Dict[str, Any]:
        """Return a safe snapshot of simulator state."""
        state = self._get_state()
        return {
            "name": self.name,
            "health": state.health,
            "incident": state.failure_type,
            "incident_context": dict(state.context or {}),
        }

    def is_healthy(self) -> bool:
        """Return whether the simulated device is healthy."""
        state = self._get_state()
        return state.health == "HEALTHY"

    def is_critical(self) -> bool:
        """Return whether a failure is currently active."""
        state = self._get_state()
        return state.health == "CRITICAL"

    # ==========================================================
    # TELEMETRY
    # ==========================================================

    def get_telemetry(self) -> Dict[str, Any]:
        """Generate telemetry according to the current database state."""
        state = self._get_state()
        health = state.health
        failure_type = state.failure_type
        context = dict(state.context or {})

        with self._lock:
            if health == "HEALTHY":
                cpu = random.uniform(20.0, 45.0)
                memory = random.uniform(30.0, 60.0)
                packet_loss = round(random.uniform(0.0, 0.5), 2)
                latency = random.uniform(2.0, 12.0)
                bandwidth = random.uniform(20.0, 60.0)
                interfaces = {k: {"status": "up"} for k in ["ether1", "ether2", "ether3"]}
                if random.random() < 0.1:
                    chosen = random.choice(list(interfaces.keys()))
                    interfaces[chosen]["status"] = "down"
                ospf_neighbors = random.randint(1, 3)
                error_count = random.randint(0, 3)

            elif failure_type == "SERVICE_CRASH":
                cpu = random.uniform(92.0, 98.0)
                memory = random.uniform(85.0, 90.0)
                packet_loss = round(random.uniform(3.0, 5.0), 2)
                latency = random.uniform(40.0, 60.0)
                bandwidth = random.uniform(55.0, 65.0)
                interfaces = {k: {"status": "up"} for k in ["ether1", "ether2", "ether3"]}
                ospf_neighbors = 2
                error_count = random.randint(3, 5)

            elif failure_type == "LINK_FAILURE":
                cpu = random.uniform(25.0, 35.0)
                memory = random.uniform(40.0, 48.0)
                packet_loss = round(random.uniform(75.0, 85.0), 2)
                latency = random.uniform(350.0, 450.0)
                bandwidth = random.uniform(10.0, 20.0)
                failed_interface = context.get("interface_name", "ether1")
                if failed_interface not in ("ether1", "ether2", "ether3"):
                    failed_interface = "ether1"
                interfaces = {
                    k: {"status": "down" if k == failed_interface else "up"}
                    for k in ["ether1", "ether2", "ether3"]
                }
                ospf_neighbors = 0
                error_count = random.randint(50, 60)

            elif failure_type == "DDOS_ATTACK":
                cpu = random.uniform(97.0, 100.0)
                memory = random.uniform(65.0, 75.0)
                packet_loss = round(random.uniform(30.0, 40.0), 2)
                latency = random.uniform(180.0, 220.0)
                bandwidth = random.uniform(90.0, 98.0)
                interfaces = {k: {"status": "up"} for k in ["ether1", "ether2", "ether3"]}
                ospf_neighbors = 2
                error_count = random.randint(15, 20)

            else:
                cpu = 0.0
                memory = 0.0
                packet_loss = 0.0
                latency = 0.0
                bandwidth = 0.0
                interfaces = {k: {"status": "up"} for k in ["ether1", "ether2", "ether3"]}
                ospf_neighbors = 0
                error_count = 0

            interface_up_count = sum(1 for d in interfaces.values() if d.get("status") == "up")
            interface_status = {k: v.copy() for k, v in interfaces.items()}
            interface_status["__metrics__"] = {
                "interface_up_count": int(interface_up_count),
                "ospf_neighbors": int(ospf_neighbors),
                "error_count": int(error_count),
            }
            interface_status["__context__"] = dict(context)

            raw_output = (
                f"cpu:{cpu:.1f}% mem:{memory:.1f}% loss:{packet_loss:.2f}% "
                f"lat:{latency:.1f}ms bw:{bandwidth:.1f}% up:{interface_up_count} "
                f"ospf:{ospf_neighbors} err:{error_count}"
            )

            return {
                "cpu_usage": float(round(cpu, 2)),
                "memory_usage": float(round(memory, 2)),
                "packet_loss": float(packet_loss),
                "latency_ms": float(round(latency, 2)),
                "bandwidth_util": float(round(bandwidth, 2)),
                "interface_up_count": int(interface_up_count),
                "ospf_neighbors": int(ospf_neighbors),
                "error_count": int(error_count),
                "interface_status": interface_status,
                "raw_output": raw_output,
                "__context__": dict(context),
                "__state__": health,
                "__failure_type__": failure_type,
            }

    def get_feature_vector(self) -> List[float]:
        """Return exactly eight ML features in training order."""
        telemetry = self.get_telemetry()
        return [telemetry[feature] for feature in TELEMETRY_FEATURE_ORDER]

    # ==========================================================
    # FAILURE INJECTION
    # ==========================================================

    def inject_failure(self, failure_type: str, **kwargs) -> str:
        """Inject a failure and persist it in the database."""
        with self._lock:
            if not failure_type:
                return "[ERROR] Failure type is required."

            key = str(failure_type).lower().strip()
            canonical = FAILURE_ALIASES.get(key, key.upper())

            if canonical not in SUPPORTED_FAILURES:
                return f"[ERROR] Unknown failure type: {failure_type}"

            state = self._get_state()
            state.health = "CRITICAL"
            state.failure_type = canonical
            state.context = {}

            if canonical == "SERVICE_CRASH":
                state.context["service_name"] = kwargs.get("service_name", "nginx")
                process_id = kwargs.get("process_id")
                if process_id is None:
                    process_id = random.randint(1000, 9999)
                try:
                    process_id = int(process_id)
                except (TypeError, ValueError):
                    process_id = random.randint(1000, 9999)
                state.context["process_id"] = process_id
                if kwargs.get("destination_port") is not None:
                    state.context["destination_port"] = int(kwargs["destination_port"])

            elif canonical == "LINK_FAILURE":
                state.context["interface_name"] = kwargs.get("interface_name", "ether1")

            elif canonical == "DDOS_ATTACK":
                state.context["source_ip"] = kwargs.get(
                    "source_ip", f"198.51.100.{random.randint(2, 254)}"
                )
                if kwargs.get("source_port") is not None:
                    state.context["source_port"] = int(kwargs["source_port"])
                state.context["destination_ip"] = kwargs.get(
                    "destination_ip", "192.168.1.10"
                )
                state.context["destination_port"] = int(kwargs.get("destination_port", 443))
                state.context["traffic_volume"] = float(kwargs.get("traffic_volume", 75000))

            state.save()

            return f"[INFO] Injected failure: {canonical} with context: {dict(state.context)}"

    def get_incident_context(self) -> Dict[str, Any]:
        """Return the context associated with the active failure."""
        state = self._get_state()
        return dict(state.context or {})

    # ==========================================================
    # HEALING
    # ==========================================================

    def heal(self, action_type: str) -> Tuple[bool, str]:
        """
        Attempt to heal the active failure.

        Checks that the action actually targets the failure that's
        currently active before rolling a success/fail chance.
        """
        with self._lock:
            state = self._get_state()

            if state.health == "HEALTHY":
                return True, "[INFO] Device is already healthy."

            expected_failure = ACTION_TO_FAILURE.get(action_type)
            if expected_failure and expected_failure != state.failure_type:
                return False, (
                    f"[WARN] Action '{action_type}' does not address the active "
                    f"failure '{state.failure_type}'. No change made."
                )

            success = random.random() <= 0.85

            if not success:
                state.health = "CRITICAL"
                state.save()
                return False, (
                    f"[WARN] Healing failed via {action_type}. "
                    "Device remains in CRITICAL state."
                )

            self._default_state()
            return True, (
                f"[OK] Healing successful via {action_type}. "
                "Device restored to HEALTHY."
            )