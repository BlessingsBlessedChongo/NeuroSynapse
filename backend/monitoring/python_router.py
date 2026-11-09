"""
Realistic router simulator for NeuroSynapse.

PythonRouter behaves like a Cisco/Juniper/MikroTik-style device:
    - Multi-vendor interface naming (eth*, GigabitEthernet*)
    - Routing table + OSPF neighbor state machine (FULL/INIT/DOWN)
    - Sinusoidal healthy telemetry with jitter and rare spikes
    - Failure injection with realistic recovery delay on heal()
    - Syslog ring buffer

State is persisted in SimulatorState (id=2) so failure injection from a
separate management command is visible to the running server process —
same pattern as SimulatedDevice (id=1).

API mirrors SimulatedDevice:

    get_telemetry(), inject_failure(), heal(), is_healthy(),
    get_incident_context(), get_feature_vector()
"""

from __future__ import annotations

import math
import random
import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, List, Optional, Tuple

from monitoring.simulated_device import (
    ACTION_TO_FAILURE,
    FAILURE_ALIASES,
    SUPPORTED_FAILURES,
    TELEMETRY_FEATURE_ORDER,
)

# Dedicated SimulatorState primary key (id=1 is SimulatedDevice).
PYTHON_ROUTER_STATE_ID = 2


class PythonRouter:
    """Thread-safe router with database-backed failure state."""

    DEFAULT_INTERFACES = [
        "lo",
        "eth0",
        "eth1",
        "GigabitEthernet0/1",
        "GigabitEthernet0/2",
    ]

    DEFAULT_ROUTES = [
        {"network": "0.0.0.0/0", "nexthop": "10.0.0.1", "proto": "static", "metric": 1},
        {"network": "10.0.0.0/24", "nexthop": "connected", "proto": "connected", "metric": 0},
        {"network": "10.0.1.0/24", "nexthop": "10.0.0.2", "proto": "ospf", "metric": 20},
        {"network": "192.168.10.0/24", "nexthop": "10.0.0.3", "proto": "ospf", "metric": 30},
        {"network": "172.16.0.0/16", "nexthop": "10.0.1.1", "proto": "static", "metric": 5},
    ]

    DEFAULT_OSPF_NEIGHBORS = [
        {"id": "10.0.0.2", "interface": "eth0", "state": "FULL"},
        {"id": "10.0.0.3", "interface": "GigabitEthernet0/1", "state": "FULL"},
        {"id": "10.0.1.1", "interface": "eth1", "state": "FULL"},
    ]

    RECOVERY_DELAY_SEC = {
        "SERVICE_CRASH": (1.5, 3.0),
        "LINK_FAILURE": (0.8, 2.0),
        "DDOS_ATTACK": (0.6, 1.5),
    }

    def __init__(self, name: str = "PyRouter-01", hostname: str = "py-rtr-01"):
        self.name = name
        self.hostname = hostname
        self._lock = Lock()
        self._boot_ts = time.time()
        self._tick = 0
        self._syslog: Deque[str] = deque(maxlen=200)
        self._routes = [dict(r) for r in self.DEFAULT_ROUTES]
        self._ospf = [dict(n) for n in self.DEFAULT_OSPF_NEIGHBORS]
        self._interfaces: Dict[str, Dict[str, Any]] = {
            iface: {
                "status": "up",
                "admin": "up",
                "errors": 0,
                "rx_bps": 0.0,
                "tx_bps": 0.0,
            }
            for iface in self.DEFAULT_INTERFACES
        }
        self._blocked_ips: set = set()
        self._log("INFO", f"Router {self.hostname} initialized (DB-backed state id={PYTHON_ROUTER_STATE_ID})")

    # ------------------------------------------------------------------
    # Database state
    # ------------------------------------------------------------------

    def _get_state(self):
        from monitoring.models import SimulatorState
        state, _ = SimulatorState.objects.get_or_create(id=PYTHON_ROUTER_STATE_ID)
        return state

    def _read_db(self) -> Tuple[str, Optional[str], Dict[str, Any], Optional[float]]:
        state = self._get_state()
        context = dict(state.context or {})
        heal_at = context.pop("__heal_complete_at__", None)
        blocked = context.pop("__blocked_ips__", None)
        if isinstance(blocked, list):
            self._blocked_ips = set(blocked)
        return state.health, state.failure_type, context, heal_at

    def _write_db(
        self,
        health: str,
        failure_type: Optional[str],
        context: Dict[str, Any],
        heal_complete_at: Optional[float] = None,
    ) -> None:
        state = self._get_state()
        payload = dict(context or {})
        if heal_complete_at is not None:
            payload["__heal_complete_at__"] = float(heal_complete_at)
        if self._blocked_ips:
            payload["__blocked_ips__"] = sorted(self._blocked_ips)
        state.health = health
        state.failure_type = failure_type
        state.context = payload
        state.save()

    def _maybe_complete_recovery(self) -> Tuple[str, Optional[str], Dict[str, Any]]:
        health, failure_type, context, heal_at = self._read_db()
        if heal_at is None:
            self._apply_failure_side_effects(failure_type, context)
            return health, failure_type, context

        if time.time() < float(heal_at):
            self._apply_failure_side_effects(failure_type, context)
            return health, failure_type, context

        # Recovery timer elapsed — clear failure in DB
        self._blocked_ips = set(self._blocked_ips)  # keep ACL if DDoS was blocked
        for iface, details in self._interfaces.items():
            details["status"] = "up"
            details["admin"] = "up"
            details["errors"] = max(0, int(details.get("errors", 0) * 0.1))
        for nbr in self._ospf:
            nbr["state"] = "FULL"
        self._routes = [dict(r) for r in self.DEFAULT_ROUTES]
        self._write_db("HEALTHY", None, {}, heal_complete_at=None)
        self._log("INFO", "Recovery complete; all protocols converged")
        return "HEALTHY", None, {}

    def _apply_failure_side_effects(self, failure_type: Optional[str], context: Dict[str, Any]) -> None:
        """Mirror DB failure onto in-memory interface/OSPF views."""
        # Reset to healthy baseline then apply failure cosmetics
        for iface, details in self._interfaces.items():
            details["status"] = "up"
            details["admin"] = "up"
        for nbr in self._ospf:
            nbr["state"] = "FULL"

        if failure_type == "LINK_FAILURE":
            iface = context.get("interface_name", "eth0")
            if iface in self._interfaces and iface != "lo":
                self._interfaces[iface]["status"] = "down"
                self._interfaces[iface]["admin"] = "down"
                self._interfaces[iface]["errors"] = max(
                    int(self._interfaces[iface].get("errors", 0)), 40
                )
            for nbr in self._ospf:
                if nbr.get("interface") == iface:
                    nbr["state"] = "DOWN"
        elif failure_type == "SERVICE_CRASH":
            for nbr in self._ospf:
                if random.random() < 0.5:
                    nbr["state"] = "DOWN"
        elif failure_type == "DDOS_ATTACK":
            for name in ("eth0", "GigabitEthernet0/1"):
                if name in self._interfaces:
                    self._interfaces[name]["errors"] = max(
                        int(self._interfaces[name].get("errors", 0)), 10
                    )

    def _log(self, level: str, message: str) -> None:
        ts = time.strftime("%b %d %H:%M:%S", time.localtime())
        entry = f"{ts} {self.hostname} [{level}] {message}"
        self._syslog.appendleft(entry)

    def _elapsed(self) -> float:
        return time.time() - self._boot_ts

    def _wave(self, period_sec: float, amplitude: float, phase: float = 0.0) -> float:
        t = self._elapsed()
        return amplitude * math.sin((2.0 * math.pi * t / period_sec) + phase)

    def _healthy_metrics(self) -> Dict[str, float]:
        cpu = 32.0 + self._wave(90, 8.0, 0.2) + random.uniform(-2.0, 2.0)
        memory = 45.0 + self._wave(180, 6.0, 1.1) + random.uniform(-1.5, 1.5)
        packet_loss = max(0.0, 0.2 + self._wave(60, 0.15) + random.uniform(0.0, 0.3))
        latency = 6.0 + self._wave(45, 2.5, 0.7) + random.uniform(-1.0, 1.0)
        bandwidth = 40.0 + self._wave(120, 12.0, 2.0) + random.uniform(-3.0, 3.0)
        if random.random() < 0.04:
            cpu = min(78.0, cpu + random.uniform(8.0, 20.0))
        return {
            "cpu_usage": float(round(max(5.0, min(cpu, 79.0)), 2)),
            "memory_usage": float(round(max(10.0, min(memory, 85.0)), 2)),
            "packet_loss": float(round(min(packet_loss, 2.0), 2)),
            "latency_ms": float(round(max(1.0, latency), 2)),
            "bandwidth_util": float(round(max(5.0, min(bandwidth, 85.0)), 2)),
        }

    def _failure_metrics(self, failure_type: str) -> Dict[str, float]:
        if failure_type == "SERVICE_CRASH":
            return {
                "cpu_usage": round(random.uniform(92.0, 99.0), 2),
                "memory_usage": round(random.uniform(85.0, 94.0), 2),
                "packet_loss": round(random.uniform(2.5, 6.0), 2),
                "latency_ms": round(random.uniform(40.0, 75.0), 2),
                "bandwidth_util": round(random.uniform(50.0, 70.0), 2),
            }
        if failure_type == "LINK_FAILURE":
            return {
                "cpu_usage": round(random.uniform(22.0, 38.0), 2),
                "memory_usage": round(random.uniform(38.0, 52.0), 2),
                "packet_loss": round(random.uniform(70.0, 92.0), 2),
                "latency_ms": round(random.uniform(320.0, 480.0), 2),
                "bandwidth_util": round(random.uniform(8.0, 22.0), 2),
            }
        if failure_type == "DDOS_ATTACK":
            return {
                "cpu_usage": round(random.uniform(95.0, 100.0), 2),
                "memory_usage": round(random.uniform(62.0, 82.0), 2),
                "packet_loss": round(random.uniform(25.0, 45.0), 2),
                "latency_ms": round(random.uniform(160.0, 260.0), 2),
                "bandwidth_util": round(random.uniform(88.0, 99.0), 2),
            }
        return self._healthy_metrics()

    def _ospf_full_count(self) -> int:
        return sum(1 for n in self._ospf if n.get("state") == "FULL")

    def _interface_up_count(self) -> int:
        return sum(
            1
            for name, d in self._interfaces.items()
            if name != "lo" and d.get("status") == "up"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        with self._lock:
            self._blocked_ips.clear()
            for iface, details in self._interfaces.items():
                details["status"] = "up"
                details["admin"] = "up"
                details["errors"] = 0
            for nbr in self._ospf:
                nbr["state"] = "FULL"
            self._routes = [dict(r) for r in self.DEFAULT_ROUTES]
            self._write_db("HEALTHY", None, {}, heal_complete_at=None)
            self._log("INFO", "Manual reset to HEALTHY")

    def is_healthy(self) -> bool:
        with self._lock:
            health, failure_type, context = self._maybe_complete_recovery()
            _, _, _, heal_at = self._read_db()
            return health == "HEALTHY" and failure_type is None and heal_at is None

    def get_incident_context(self) -> Dict[str, Any]:
        with self._lock:
            _, _, context, _ = self._read_db()
            # Strip internal keys
            return {
                k: v for k, v in context.items()
                if not str(k).startswith("__")
            }

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            health, failure_type, context = self._maybe_complete_recovery()
            _, _, _, heal_at = self._read_db()
            return {
                "name": self.name,
                "hostname": self.hostname,
                "health": health,
                "incident": failure_type,
                "incident_context": {
                    k: v for k, v in context.items() if not str(k).startswith("__")
                },
                "recovering": heal_at is not None,
                "blocked_ips": sorted(self._blocked_ips),
                "routes": list(self._routes),
                "ospf_neighbors": list(self._ospf),
            }

    def get_syslog(self, limit: int = 20) -> List[str]:
        with self._lock:
            return list(self._syslog)[:limit]

    def get_telemetry(self) -> Dict[str, Any]:
        with self._lock:
            health, failure_type, context = self._maybe_complete_recovery()
            _, _, _, heal_at = self._read_db()
            self._tick += 1

            recovering = heal_at is not None
            if health == "HEALTHY" and not recovering and not failure_type:
                metrics = self._healthy_metrics()
                error_count = random.randint(0, 3)
            else:
                metrics = self._failure_metrics(failure_type or "SERVICE_CRASH")
                if failure_type == "LINK_FAILURE":
                    error_count = random.randint(40, 75)
                elif failure_type == "DDOS_ATTACK":
                    error_count = random.randint(12, 28)
                else:
                    error_count = random.randint(3, 10)

            for name, details in self._interfaces.items():
                if details["status"] == "up":
                    details["rx_bps"] = round(random.uniform(1e5, 8e6), 0)
                    details["tx_bps"] = round(random.uniform(1e5, 8e6), 0)
                else:
                    details["rx_bps"] = 0.0
                    details["tx_bps"] = 0.0

            clean_context = {
                k: v for k, v in context.items() if not str(k).startswith("__")
            }

            interface_status = {
                name: {
                    "status": details["status"],
                    "errors": int(details.get("errors", 0)),
                    "admin": details.get("admin", "up"),
                }
                for name, details in self._interfaces.items()
            }

            up_count = self._interface_up_count()
            feature_up_count = up_count + (
                1 if self._interfaces.get("lo", {}).get("status") == "up" else 0
            )
            ospf_neighbors = self._ospf_full_count()

            interface_status["__metrics__"] = {
                "interface_up_count": int(feature_up_count),
                "ospf_neighbors": int(ospf_neighbors),
                "error_count": int(error_count),
            }
            interface_status["__context__"] = dict(clean_context)

            raw_output = (
                f"{self.hostname} cpu:{metrics['cpu_usage']:.1f}% "
                f"mem:{metrics['memory_usage']:.1f}% loss:{metrics['packet_loss']:.2f}% "
                f"lat:{metrics['latency_ms']:.1f}ms bw:{metrics['bandwidth_util']:.1f}% "
                f"up:{feature_up_count} ospf:{ospf_neighbors} err:{error_count}"
            )

            return {
                "cpu_usage": float(metrics["cpu_usage"]),
                "memory_usage": float(metrics["memory_usage"]),
                "packet_loss": float(metrics["packet_loss"]),
                "latency_ms": float(metrics["latency_ms"]),
                "bandwidth_util": float(metrics["bandwidth_util"]),
                "interface_up_count": int(feature_up_count),
                "ospf_neighbors": int(ospf_neighbors),
                "error_count": int(error_count),
                "interface_status": interface_status,
                "routing_table": list(self._routes),
                "ospf_neighbor_table": list(self._ospf),
                "syslog": list(self._syslog)[:5],
                "raw_output": raw_output,
                "__context__": dict(clean_context),
                "__state__": health,
                "__failure_type__": failure_type,
            }

    def get_feature_vector(self) -> List[float]:
        telemetry = self.get_telemetry()
        return [float(telemetry[f]) for f in TELEMETRY_FEATURE_ORDER]

    def inject_failure(self, failure_type: str, **kwargs) -> str:
        with self._lock:
            if not failure_type:
                return "[ERROR] Failure type is required."

            key = str(failure_type).lower().strip()
            canonical = FAILURE_ALIASES.get(key, key.upper())
            if canonical not in SUPPORTED_FAILURES:
                return f"[ERROR] Unknown failure type: {failure_type}"

            context: Dict[str, Any] = {}

            if canonical == "SERVICE_CRASH":
                svc = kwargs.get("service_name", "ospfd")
                pid = kwargs.get("process_id", random.randint(1000, 9999))
                try:
                    pid = int(pid)
                except (TypeError, ValueError):
                    pid = random.randint(1000, 9999)
                context = {"service_name": svc, "process_id": pid}
                self._log("ERROR", f"Service crash detected: {svc} (pid={pid})")

            elif canonical == "LINK_FAILURE":
                iface = kwargs.get("interface_name") or kwargs.get("interface") or "eth0"
                if iface not in self._interfaces or iface == "lo":
                    iface = "eth0"
                context = {"interface_name": iface}
                self._log("CRIT", f"Interface {iface} line protocol down")

            elif canonical == "DDOS_ATTACK":
                src = kwargs.get("source_ip", f"198.51.100.{random.randint(2, 254)}")
                context = {
                    "source_ip": src,
                    "destination_ip": kwargs.get("destination_ip", "10.0.0.10"),
                    "destination_port": int(kwargs.get("destination_port", 443)),
                    "traffic_volume": float(kwargs.get("traffic_volume", 85000)),
                }
                self._log("CRIT", f"DDoS flood suspected from {src}")

            self._apply_failure_side_effects(canonical, context)
            self._write_db("CRITICAL", canonical, context, heal_complete_at=None)
            return f"[INFO] Injected failure: {canonical} with context: {context}"

    def heal(self, action_type: str) -> Tuple[bool, str]:
        with self._lock:
            health, failure_type, context = self._maybe_complete_recovery()
            _, _, _, heal_at = self._read_db()

            if health == "HEALTHY" and failure_type is None and heal_at is None:
                return True, "[INFO] Device is already healthy."

            expected = ACTION_TO_FAILURE.get(action_type)
            if expected and expected != failure_type:
                return False, (
                    f"[WARN] Action '{action_type}' does not address the active "
                    f"failure '{failure_type}'. No change made."
                )

            if action_type == "BLOCK_SOURCE_IP":
                src = context.get("source_ip")
                if src:
                    self._blocked_ips.add(src)
                    self._log("INFO", f"ACL installed: deny ip host {src} any")
            elif action_type == "UNBLOCK_SOURCE_IP":
                src = context.get("source_ip")
                if src and src in self._blocked_ips:
                    self._blocked_ips.discard(src)
                    self._log("INFO", f"ACL removed for {src}")
            elif action_type == "REROUTE_TRAFFIC":
                iface = context.get("interface_name", "eth0")
                if iface in self._interfaces:
                    self._interfaces[iface]["admin"] = "up"
                    self._interfaces[iface]["status"] = "up"
                    self._log("INFO", f"Interface {iface} no shutdown")
            elif action_type in ("RESTART_SERVICE", "REBOOT_DEVICE"):
                svc = context.get("service_name", "ospfd")
                self._log("INFO", f"Restarting service {svc}")
                for nbr in self._ospf:
                    nbr["state"] = "INIT"

            delay_range = self.RECOVERY_DELAY_SEC.get(
                failure_type or "SERVICE_CRASH", (1.0, 3.0)
            )
            delay = random.uniform(*delay_range)
            heal_complete_at = time.time() + delay
            # Keep failure_type until recovery completes so telemetry stays bad
            # during the recovery window (verification waits for is_healthy).
            self._write_db(
                "CRITICAL",
                failure_type,
                context,
                heal_complete_at=heal_complete_at,
            )
            self._log(
                "INFO",
                f"Healing action {action_type} accepted; recovery ETA {delay:.1f}s",
            )
            return True, (
                f"[INFO] Healing '{action_type}' started; "
                f"protocols will reconverge in ~{delay:.1f}s"
            )
