"""
Network connectors for NeuroSynapse.

Supports:
    - Simulated devices (database-backed)
    - PythonRouter (in-memory realistic simulator)
    - FRR / Linux devices (via SSH, Alpine-aware)
    - Cisco IOS, MikroTik, Juniper, Huawei (via SSH)
"""

import re
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
)

from monitoring.simulated_device import SimulatedDevice, TELEMETRY_FEATURE_ORDER
from monitoring.python_router import PythonRouter
from monitoring.vendor_profiles import get_profile

# Explicitly expose feature order contract for the ML Inference Engine
__all__ = [
    "TELEMETRY_FEATURE_ORDER",
    "normalize_telemetry",
    "attach_metrics_to_interface_status",
    "persist_interface_status",
    "telemetry_to_feature_vector",
    "SimulatedConnector",
    "PythonRouterConnector",
    "RealNetworkConnector",
    "get_connector",
]


def normalize_telemetry(raw):
    """Convert raw telemetry into canonical 8-feature contract."""
    if raw is None:
        return None

    def _read(key, default=0.0):
        if hasattr(raw, key):
            value = getattr(raw, key)
        elif isinstance(raw, dict):
            value = raw.get(key, default)
        else:
            value = default

        if value is None:
            return default

        if key in ("interface_up_count", "ospf_neighbors", "error_count"):
            try:
                return int(value)
            except (TypeError, ValueError):
                return int(default)

        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    raw_interface_status = {}
    if hasattr(raw, "interface_status"):
        raw_interface_status = getattr(raw, "interface_status") or {}
    elif isinstance(raw, dict):
        raw_interface_status = raw.get("interface_status") or {}

    if not isinstance(raw_interface_status, dict):
        raw_interface_status = {}

    metrics = raw_interface_status.get("__metrics__", {}) or {}
    if not isinstance(metrics, dict):
        metrics = {}

    context = {}
    if isinstance(raw, dict):
        context = raw.get("__context__") or raw.get("context") or {}
    if not context and hasattr(raw, "__context__"):
        context = getattr(raw, "__context__") or {}
    if not context:
        context = raw_interface_status.get("__context__", {}) or {}
    if not isinstance(context, dict):
        context = {}

    cleaned_interface_status = {}
    total_interface_errors = 0

    for name, details in raw_interface_status.items():
        name_str = str(name)
        if name_str.startswith("__") and name_str.endswith("__"):
            continue

        if isinstance(details, dict):
            status_str = str(details.get("status", "")).lower()
            errors = details.get("errors", 0)
        else:
            status_str = str(details).lower()
            errors = 0

        try:
            total_interface_errors += int(errors)
        except (TypeError, ValueError):
            pass

        is_up = status_str in ("up", "unknown") or name_str == "lo"
        cleaned_interface_status[name_str] = {
            "status": "up" if is_up else "down",
            "errors": errors,
        }

    if not context.get("interface_name"):
        down_ifaces = [
            name for name, details in cleaned_interface_status.items()
            if name != "lo" and details.get("status") == "down"
        ]
        if down_ifaces:
            context = dict(context)
            context["interface_name"] = down_ifaces[0]

    # Resolve up count
    up_count = metrics.get("interface_up_count")
    if up_count is None and isinstance(raw, dict):
        up_count = raw.get("interface_up_count")
    if up_count is None and hasattr(raw, "interface_up_count"):
        up_count = getattr(raw, "interface_up_count", None)
    if up_count is None:
        up_count = sum(
            1 for details in cleaned_interface_status.values()
            if isinstance(details, dict) and details.get("status") == "up"
        )

    try:
        up_count = int(up_count)
    except (TypeError, ValueError):
        up_count = 0

    # Resolve OSPF neighbors
    ospf_neighbors = metrics.get("ospf_neighbors")
    if ospf_neighbors is None and isinstance(raw, dict):
        ospf_neighbors = raw.get("ospf_neighbors")
    if ospf_neighbors is None and hasattr(raw, "ospf_neighbors"):
        ospf_neighbors = getattr(raw, "ospf_neighbors", None)
    if ospf_neighbors is None:
        ospf_neighbors = 1

    try:
        ospf_neighbors = int(ospf_neighbors)
    except (TypeError, ValueError):
        ospf_neighbors = 0

    # Resolve error count
    error_count = metrics.get("error_count")
    if error_count is None and isinstance(raw, dict):
        error_count = raw.get("error_count")
    if error_count is None and hasattr(raw, "error_count"):
        error_count = getattr(raw, "error_count", None)
    if error_count is None:
        error_count = total_interface_errors

    try:
        error_count = int(error_count)
    except (TypeError, ValueError):
        error_count = 0

    normalized = {
        "cpu_usage": _read("cpu_usage", 0.0),
        "memory_usage": _read("memory_usage", 0.0),
        "packet_loss": _read("packet_loss", 0.0),
        "latency_ms": _read("latency_ms", 5.0),
        "bandwidth_util": _read("bandwidth_util", 30.0),
        "interface_up_count": up_count,
        "ospf_neighbors": ospf_neighbors,
        "error_count": error_count,
    }

    normalized["interface_status"] = cleaned_interface_status
    normalized["__context__"] = context
    normalized["context"] = context

    if isinstance(raw, dict):
        normalized["raw_output"] = raw.get("raw_output", "")
    elif hasattr(raw, "raw_output"):
        normalized["raw_output"] = getattr(raw, "raw_output", "") or ""
    else:
        normalized["raw_output"] = ""

    return normalized


def attach_metrics_to_interface_status(normalized):
    """Embed auxiliary metrics into interface_status JSON field for DB storage."""
    interface_status = dict(normalized.get("interface_status") or {})
    interface_status["__metrics__"] = {
        "interface_up_count": normalized["interface_up_count"],
        "ospf_neighbors": normalized["ospf_neighbors"],
        "error_count": normalized["error_count"],
    }
    context = normalized.get("__context__") or normalized.get("context") or {}
    interface_status["__context__"] = dict(context)
    return interface_status


persist_interface_status = attach_metrics_to_interface_status


def telemetry_to_feature_vector(raw):
    """Extract feature vector formatted specifically for InferenceEngine inputs."""
    normalized = normalize_telemetry(raw)
    if normalized is None:
        return [0.0] * len(TELEMETRY_FEATURE_ORDER)
    return [float(normalized.get(key, 0.0)) for key in TELEMETRY_FEATURE_ORDER]


class SimulatedConnector:
    """Connector for database-backed simulated devices."""

    _simulators = {}

    def __init__(self, device):
        self.device = device
        key = getattr(device, "pk", None)
        if key is None:
            key = getattr(device, "name", "default")

        if key not in self._simulators:
            self._simulators[key] = SimulatedDevice(device.name)

        self.sim = self._simulators[key]

    @classmethod
    def get_simulator(cls, device):
        key = getattr(device, "pk", None)
        if key is None:
            key = getattr(device, "name", "default")
        if key not in cls._simulators:
            cls._simulators[key] = SimulatedDevice(device.name)
        return cls._simulators[key]

    def connect(self):
        return True

    def disconnect(self):
        return None

    def collect_telemetry(self):
        raw = self.sim.get_telemetry()
        if raw is None:
            return None

        normalized = normalize_telemetry(raw)
        context = self.sim.get_incident_context() or {}
        normalized["__context__"] = dict(context)
        normalized["context"] = dict(context)
        return normalized

    def execute_healing_command(self, command, verify=True):
        if isinstance(command, list):
            command = " && ".join(command)

        command_lower = command.lower()

        if (
            "iptables -d" in command_lower
            or "tc qdisc del" in command_lower
            or "undo rule" in command_lower
            or "no access-list" in command_lower
            or "delete firewall" in command_lower
            or "filter remove" in command_lower
            or "ip route del blackhole" in command_lower
        ):
            action_type = "UNBLOCK_SOURCE_IP"
        elif (
            "iptables" in command_lower
            or "access-list" in command_lower
            or "firewall" in command_lower
            or "acl " in command_lower
            or "blackhole" in command_lower
        ):
            action_type = "BLOCK_SOURCE_IP"
        elif "ip link set" in command_lower and " up" in command_lower:
            action_type = "REROUTE_TRAFFIC"
        elif (
            "no shutdown" in command_lower
            or "undo shutdown" in command_lower
            or "interface enable" in command_lower
        ):
            action_type = "REROUTE_TRAFFIC"
        elif (
            "restart" in command_lower
            or "reboot" in command_lower
            or "reload" in command_lower
            or "start" in command_lower
        ):
            action_type = "RESTART_SERVICE"
        else:
            action_type = "HEAL"

        success, message = self.sim.heal(action_type)
        return {"success": success, "output": message, "post_telemetry": None}

    def run_readonly_command(self, command):
        return None

    def inject_failure(self, failure_type, **kwargs):
        return self.sim.inject_failure(failure_type, **kwargs)

    def get_incident_context(self):
        return self.sim.get_incident_context()

    def verify_recovery(self):
        telemetry = self.collect_telemetry()
        healthy = self.sim.is_healthy()
        return healthy, telemetry


class PythonRouterConnector:
    """Connector for the in-memory PythonRouter simulator."""

    _routers = {}

    def __init__(self, device):
        self.device = device
        key = getattr(device, "pk", None)
        if key is None:
            key = getattr(device, "name", "default")

        if key not in self._routers:
            hostname = getattr(device, "name", "py-rtr-01") or "py-rtr-01"
            self._routers[key] = PythonRouter(name=hostname, hostname=hostname)

        self.router = self._routers[key]

    @classmethod
    def get_router(cls, device):
        key = getattr(device, "pk", None)
        if key is None:
            key = getattr(device, "name", "default")
        if key not in cls._routers:
            hostname = getattr(device, "name", "py-rtr-01") or "py-rtr-01"
            cls._routers[key] = PythonRouter(name=hostname, hostname=hostname)
        return cls._routers[key]

    def connect(self):
        return True

    def disconnect(self):
        return None

    def collect_telemetry(self):
        raw = self.router.get_telemetry()
        if raw is None:
            return None

        normalized = normalize_telemetry(raw)
        context = self.router.get_incident_context() or {}
        normalized["__context__"] = dict(context)
        normalized["context"] = dict(context)
        return normalized

    def execute_healing_command(self, command, verify=True):
        if isinstance(command, list):
            command = " && ".join(command)

        command_lower = (command or "").lower()

        if (
            "iptables -d" in command_lower
            or "tc qdisc del" in command_lower
            or "undo rule" in command_lower
            or "no access-list" in command_lower
            or "delete firewall" in command_lower
            or "filter remove" in command_lower
            or "ip route del blackhole" in command_lower
        ):
            action_type = "UNBLOCK_SOURCE_IP"
        elif (
            "iptables" in command_lower
            or "access-list" in command_lower
            or "firewall" in command_lower
            or "acl " in command_lower
            or "blackhole" in command_lower
        ):
            action_type = "BLOCK_SOURCE_IP"
        elif "ip link set" in command_lower and " up" in command_lower:
            action_type = "REROUTE_TRAFFIC"
        elif (
            "no shutdown" in command_lower
            or "undo shutdown" in command_lower
            or "interface enable" in command_lower
        ):
            action_type = "REROUTE_TRAFFIC"
        elif (
            "restart" in command_lower
            or "reboot" in command_lower
            or "reload" in command_lower
            or "rc-service" in command_lower
            or "supervisorctl" in command_lower
        ):
            action_type = "RESTART_SERVICE"
        else:
            action_type = "HEAL"

        success, message = self.router.heal(action_type)
        post = None
        if verify:
            # Allow short recovery delay to elapse for unit tests / demos
            import time
            time.sleep(0.05)
            post = self.collect_telemetry()
        return {"success": success, "output": message, "post_telemetry": post}

    def run_readonly_command(self, command):
        if not command:
            return None
        cmd = command.lower()
        if "syslog" in cmd or "log" in cmd:
            return "\n".join(self.router.get_syslog())
        if "route" in cmd:
            state = self.router.get_state()
            return "\n".join(
                f"{r['network']} via {r['nexthop']} [{r['proto']}]"
                for r in state.get("routes", [])
            )
        if "ospf" in cmd:
            state = self.router.get_state()
            return "\n".join(
                f"{n['id']} {n['interface']} {n['state']}"
                for n in state.get("ospf_neighbors", [])
            )
        return None

    def inject_failure(self, failure_type, **kwargs):
        return self.router.inject_failure(failure_type, **kwargs)

    def get_incident_context(self):
        return self.router.get_incident_context()

    def verify_recovery(self):
        import time
        # Wait for realistic recovery timer
        for _ in range(20):
            if self.router.is_healthy():
                break
            time.sleep(0.25)
        telemetry = self.collect_telemetry()
        return self.router.is_healthy(), telemetry


class RealNetworkConnector:
    """SSH connector for real devices via Netmiko (Alpine FRR aware)."""

    NETMIKO_DEVICE_TYPE_MAP = {
        "cisco_ios": "cisco_ios",
        "mikrotik_routeros": "mikrotik_routeros",
        "juniper_junos": "juniper_junos",
        "huawei_vrp": "huawei",
        "frr": "linux",
        "generic": "linux",
    }

    CONFIG_MODE_DEVICE_TYPES = {
        "cisco_ios",
        "juniper_junos",
        "huawei_vrp",
    }

    # Linux/Alpine SSH sessions are often BusyBox ash; disable fast_cli
    # and allow longer banner/auth timeouts for Docker-mapped ports.
    LINUX_DEVICE_TYPES = {"frr", "generic"}

    def __init__(self, device):
        self.device = device
        self.connection = None
        self._alpine_probed = False

    # SimulatorState id reserved for FRR injected-failure overlay so
    # CLI inject_failure is visible to the collector in another process.
    FRR_OVERLAY_STATE_ID = 3

    def _get_frr_overlay(self):
        from monitoring.models import SimulatorState
        state, _ = SimulatorState.objects.get_or_create(id=self.FRR_OVERLAY_STATE_ID)
        return state

    def _set_frr_overlay(self, failure_type, context=None):
        state = self._get_frr_overlay()
        state.health = "CRITICAL"
        state.failure_type = failure_type
        state.context = dict(context or {})
        state.save(update_fields=["health", "failure_type", "context", "updated_at"])

    def _clear_frr_overlay(self):
        state = self._get_frr_overlay()
        state.health = "HEALTHY"
        state.failure_type = None
        state.context = {}
        state.save(update_fields=["health", "failure_type", "context", "updated_at"])

    def inject_failure(self, failure_type, **kwargs):
        """
        Inject a real failure on the FRR/Linux host and record an overlay so
        telemetry reliably matches the ML/rule signatures (esp. DDoS).
        """
        from monitoring.simulated_device import FAILURE_ALIASES, SUPPORTED_FAILURES

        key = str(failure_type or "").lower().strip()
        canonical = FAILURE_ALIASES.get(key, key.upper())
        if canonical not in SUPPORTED_FAILURES:
            return {"success": False, "output": f"Unknown failure type: {failure_type}"}

        interface = kwargs.get("interface_name", "eth1")
        service = kwargs.get("service_name", "frr")
        source_ip = kwargs.get("source_ip", "10.0.0.99")

        if canonical == "SERVICE_CRASH":
            cmd = (
                f"sudo -n sh -c '"
                f"command -v rc-service >/dev/null 2>&1 && rc-service {service} stop "
                f"|| (test -x /etc/init.d/{service} && /etc/init.d/{service} stop) "
                f"|| killall zebra 2>/dev/null || true'"
            )
            context = {"service_name": service}
        elif canonical == "LINK_FAILURE":
            cmd = f"sudo -n ip link set dev {interface} down"
            context = {"interface_name": interface}
        else:  # DDOS_ATTACK — do NOT add a DROP rule (that is the heal).
            # Prefer tc netem when available; otherwise leave host alone and
            # rely on the telemetry overlay for the DDoS signature.
            cmd = (
                f"if command -v tc >/dev/null 2>&1; then "
                f"sudo -n tc qdisc add dev {interface} root netem loss 30% delay 200ms 2>/dev/null || true; "
                f"fi; echo DDOS_INJECTED"
            )
            context = {
                "source_ip": source_ip,
                "destination_port": int(kwargs.get("destination_port", 443)),
                "traffic_volume": float(kwargs.get("traffic_volume", 85000)),
                "interface_name": interface,
            }

        self._set_frr_overlay(canonical, context)
        result = self.execute_healing_command(cmd, verify=False)
        result["overlay"] = canonical
        result["context"] = context
        return result

    def get_incident_context(self):
        state = self._get_frr_overlay()
        if state.health != "CRITICAL":
            return {}
        return {
            k: v for k, v in dict(state.context or {}).items()
            if not str(k).startswith("__")
        }

    def _apply_frr_overlay(self, parsed):
        """Blend injected-failure signatures into live FRR telemetry."""
        state = self._get_frr_overlay()
        context = dict(state.context or {})
        failure_type = state.failure_type

        # Live detection: zebra missing => SERVICE_CRASH even without overlay
        zebra_down = False
        try:
            out = self.run_readonly_command(
                "pgrep -x zebra >/dev/null 2>&1 && echo ZEBRA_UP || echo ZEBRA_DOWN"
            ) or ""
            zebra_down = "ZEBRA_DOWN" in out
        except Exception:
            zebra_down = False

        if zebra_down:
            failure_type = failure_type or "SERVICE_CRASH"
            parsed["cpu_usage"] = max(float(parsed.get("cpu_usage") or 0), 93.0)
            parsed["memory_usage"] = max(float(parsed.get("memory_usage") or 0), 86.0)
            parsed["packet_loss"] = max(float(parsed.get("packet_loss") or 0), 4.0)
            parsed["latency_ms"] = max(float(parsed.get("latency_ms") or 0), 55.0)
            parsed["bandwidth_util"] = float(parsed.get("bandwidth_util") or 60.0)
            parsed["ospf_neighbors"] = 0
            raw = parsed.get("raw_output") or {}
            if isinstance(raw, dict):
                raw["service"] = "FRR_DOWN"
                parsed["raw_output"] = raw

        if state.health == "CRITICAL" and failure_type == "DDOS_ATTACK":
            parsed["cpu_usage"] = 97.0
            parsed["memory_usage"] = 72.0
            parsed["packet_loss"] = 35.0
            parsed["latency_ms"] = 200.0
            parsed["bandwidth_util"] = 95.0
            parsed["error_count"] = 18

        if state.health == "CRITICAL" and failure_type == "LINK_FAILURE":
            iface = context.get("interface_name", "eth1")
            iface_status = parsed.get("interface_status") or {}
            if isinstance(iface_status, dict):
                # Ensure the failed interface is marked down for classification
                details = iface_status.get(iface)
                if isinstance(details, dict):
                    details["status"] = "down"
                else:
                    iface_status[iface] = {"status": "down"}
                parsed["interface_status"] = iface_status
            parsed["packet_loss"] = max(float(parsed.get("packet_loss") or 0), 75.0)
            parsed["latency_ms"] = max(float(parsed.get("latency_ms") or 0), 350.0)
            parsed["cpu_usage"] = min(float(parsed.get("cpu_usage") or 30), 40.0)

        if state.health == "CRITICAL" and failure_type == "SERVICE_CRASH" and not zebra_down:
            # Overlay while daemons are stopping / restarting
            parsed["cpu_usage"] = max(float(parsed.get("cpu_usage") or 0), 94.0)
            parsed["memory_usage"] = max(float(parsed.get("memory_usage") or 0), 88.0)
            parsed["packet_loss"] = max(float(parsed.get("packet_loss") or 0), 3.5)
            parsed["latency_ms"] = max(float(parsed.get("latency_ms") or 0), 50.0)
            raw = parsed.get("raw_output") or {}
            if isinstance(raw, dict):
                raw["service"] = "FRR_DOWN"
                parsed["raw_output"] = raw

        if context:
            parsed["__context__"] = {
                k: v for k, v in context.items() if not str(k).startswith("__")
            }
            parsed["context"] = dict(parsed["__context__"])

        return parsed

    def connect(self):
        if self.connection:
            return True

        try:
            internal_type = getattr(self.device, "device_type", "generic")
            netmiko_type = self.NETMIKO_DEVICE_TYPE_MAP.get(internal_type, "linux")
            is_linux = internal_type in self.LINUX_DEVICE_TYPES or netmiko_type == "linux"

            connect_kwargs = {
                "device_type": netmiko_type,
                "host": self.device.ip_address,
                "port": self.device.ssh_port,
                "username": self.device.username,
                "password": self.device.password,
                "timeout": 20,
                "conn_timeout": 20,
                "auth_timeout": 30,
                "banner_timeout": 30,
            }

            if is_linux:
                # Alpine ash / BusyBox: avoid enable-mode assumptions and
                # fast_cli timing that breaks short prompt sessions.
                connect_kwargs.update(
                    {
                        "fast_cli": False,
                        "global_delay_factor": 1.5,
                        "session_log": None,
                        "allow_agent": False,
                        "use_keys": False,
                    }
                )

            self.connection = ConnectHandler(**connect_kwargs)
            print(
                f"[INFO] Connected to {self.device.name} as {netmiko_type} "
                f"({self.device.ip_address}:{self.device.ssh_port})"
            )

            if is_linux and not self._alpine_probed:
                self._probe_alpine_environment()

            return True

        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            print(f"[ERROR] SSH connection failed for {self.device.name}: {exc}")
            self.connection = None
            return False
        except Exception as exc:
            print(f"[ERROR] Unexpected SSH error for {self.device.name}: {exc}")
            self.connection = None
            return False

    def _probe_alpine_environment(self):
        """Best-effort capability probe for Alpine FRR containers."""
        self._alpine_probed = True
        if not self.connection:
            return

        probes = {
            "os": "cat /etc/os-release 2>/dev/null | head -n 3 || uname -a",
            "ip": "command -v ip || echo MISSING_IP",
            "sudo": "command -v sudo || echo MISSING_SUDO",
            "sudo_n": "sudo -n true 2>&1 || echo SUDO_NEEDS_PASSWORD",
            "rc_service": "command -v rc-service || echo NO_RC_SERVICE",
            "frr": "pgrep -a zebra 2>/dev/null || ps aux 2>/dev/null | grep -E '[z]ebra|[f]rr' || echo FRR_NOT_RUNNING",
        }

        for name, cmd in probes.items():
            try:
                out = (
                    self.connection.send_command(
                        cmd, read_timeout=15, strip_prompt=True, strip_command=True
                    )
                    or ""
                ).strip()
                preview = " ".join(out.splitlines()[:2])[:160]
                if "MISSING" in out or "NEEDS_PASSWORD" in out or "NO_RC" in out:
                    print(f"[WARN] Alpine probe {name}: {preview}")
                else:
                    print(f"[INFO] Alpine probe {name}: {preview}")
            except Exception as exc:
                print(f"[WARN] Alpine probe {name} failed: {exc}")

    def disconnect(self):
        if self.connection:
            try:
                self.connection.disconnect()
            except Exception:
                pass
            finally:
                self.connection = None

    def collect_telemetry(self):
        if not self.connection and not self.connect():
            return None

        profile = get_profile(self.device.device_type)
        parser = profile.get("parser")
        commands = profile.get("telemetry_commands", {})
        raw_outputs = {}

        for key, command in commands.items():
            try:
                raw_outputs[key] = self.connection.send_command(
                    command,
                    read_timeout=30,
                    strip_prompt=True,
                    strip_command=True,
                ) or ""
            except Exception as exc:
                print(f"[ERROR] Telemetry command '{key}' failed: {exc}")
                raw_outputs[key] = f"ERROR: {exc}"

        parsed = {
            "cpu_usage": None,
            "memory_usage": None,
            "interface_status": {},
            "packet_loss": 0.0,
        }

        try:
            if parser:
                parsed["cpu_usage"] = parser.parse_cpu(raw_outputs.get("cpu", ""))
                parsed["memory_usage"] = parser.parse_memory(raw_outputs.get("memory", ""))
                parsed["interface_status"] = parser.parse_interfaces(
                    raw_outputs.get("interfaces", "")
                )
                if hasattr(parser, "parse_packet_loss"):
                    parsed["packet_loss"] = parser.parse_packet_loss(
                        raw_outputs.get("packet_loss", "")
                    )
                if hasattr(parser, "parse_ospf_neighbors"):
                    parsed["ospf_neighbors"] = parser.parse_ospf_neighbors(
                        raw_outputs.get("ospf", "")
                    )
        except Exception as exc:
            print(f"[ERROR] Telemetry parsing failed: {exc}")

        parsed["raw_output"] = raw_outputs

        # Apply FRR injected-failure overlay + live zebra-down detection
        if getattr(self.device, "device_type", "") in ("frr", "linux", "generic"):
            parsed = self._apply_frr_overlay(parsed)

        return normalize_telemetry(parsed)

    def execute_healing_command(self, command, verify=True):
        if not self.connection and not self.connect():
            return {"success": False, "output": "Not connected", "post_telemetry": None}

        device_type = getattr(self.device, "device_type", "generic")
        commands = command if isinstance(command, list) else [command]
        commands = [c.strip() for c in commands if c and c.strip()]

        if not commands:
            return {"success": False, "output": "No command", "post_telemetry": None}

        try:
            if device_type in self.CONFIG_MODE_DEVICE_TYPES:
                output = self.connection.send_config_set(commands)
                if device_type == "juniper_junos" and not any(
                    c.lower().startswith("commit") for c in commands
                ):
                    output += "\n" + self.connection.send_command("commit")
            else:
                outputs = []
                for cmd in commands:
                    # Service stop/restart and killall often disrupt the shell
                    # long enough that Netmiko's prompt expect times out with
                    # "Pattern not detected". Use timing-based send for those
                    # (and any FRR/Alpine mutating command) so we don't hang.
                    use_timing = self._should_use_timing_send(cmd, device_type)
                    try:
                        if use_timing and hasattr(self.connection, "send_command_timing"):
                            out = self.connection.send_command_timing(
                                cmd, read_timeout=25
                            )
                        else:
                            out = self.connection.send_command(
                                cmd,
                                read_timeout=45,
                                strip_prompt=True,
                                strip_command=True,
                            )
                        outputs.append(out or "")
                    except Exception as cmd_exc:
                        err = str(cmd_exc)
                        # Stopping FRR / bringing links down can drop the
                        # expect pattern even when the command already ran.
                        if "Pattern not detected" in err or "timed out" in err.lower():
                            print(
                                f"[WARN] Command expect timed out "
                                f"(treating as best-effort success): {err[:160]}"
                            )
                            outputs.append(err)
                            # Force reconnect on next operation
                            try:
                                self.disconnect()
                            except Exception:
                                pass
                        else:
                            raise
                output = "\n".join(outputs)

            result = {"success": True, "output": output, "post_telemetry": None}

            if verify:
                try:
                    if not self.connection:
                        self.connect()
                    result["post_telemetry"] = self.collect_telemetry()
                except Exception as exc:
                    print(f"[WARN] Post-healing telemetry refresh failed: {exc}")

            return result

        except Exception as exc:
            return {"success": False, "output": str(exc), "post_telemetry": None}

    @staticmethod
    def _should_use_timing_send(cmd, device_type):
        cl = (cmd or "").lower()
        if device_type in ("frr", "linux", "generic"):
            markers = (
                "rc-service",
                "/etc/init.d/",
                "systemctl",
                "killall",
                "pkill",
                "ip link set",
                "iptables",
                "tc qdisc",
                "ip route",
                "watchfrr",
                "zebra",
            )
            return any(m in cl for m in markers)
        return False

    def run_readonly_command(self, command):
        if not command:
            return None
        if not self.connection and not self.connect():
            return None
        try:
            return self.connection.send_command(
                command, read_timeout=30, strip_prompt=True, strip_command=True
            )
        except Exception as exc:
            # A service restart can close the SSH channel while the target
            # is recovering. Force a fresh connection on the next probe.
            self.disconnect()
            return f"ERROR: {exc}"

def get_connector(device):
    """Return appropriate connector based on device type."""
    device_type = getattr(device, "device_type", "") or ""
    if device_type == "simulated":
        return SimulatedConnector(device)
    if device_type == "python_router":
        return PythonRouterConnector(device)
    return RealNetworkConnector(device)