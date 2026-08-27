from monitoring.simulated_device import SimulatedDevice, TELEMETRY_FEATURE_ORDER
from monitoring.vendor_profiles import get_profile
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException


def normalize_telemetry(raw):
    """Convert telemetry into the canonical 8-feature contract."""
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

    interface_status = {}
    if hasattr(raw, "interface_status"):
        interface_status = getattr(raw, "interface_status") or {}
    elif isinstance(raw, dict):
        interface_status = raw.get("interface_status") or {}

    if not isinstance(interface_status, dict):
        interface_status = {}

    metrics = interface_status.get("__metrics__", {}) or {}
    if not isinstance(metrics, dict):
        metrics = {}

    context = {}
    if isinstance(raw, dict):
        context = raw.get("__context__") or raw.get("context") or {}
    if not context and hasattr(raw, "__context__"):
        context = getattr(raw, "__context__") or {}
    if not context:
        context = interface_status.get("__context__", {}) or {}
    if not isinstance(context, dict):
        context = {}

    up_count = metrics.get("interface_up_count")
    if up_count is None and isinstance(raw, dict):
        up_count = raw.get("interface_up_count")
    if up_count is None and hasattr(raw, "interface_up_count"):
        up_count = getattr(raw, "interface_up_count", None)
    if up_count is None:
        up_count = sum(
            1 for name, details in interface_status.items()
            if not str(name).startswith("__")
            and isinstance(details, dict)
            and details.get("status") == "up"
        )

    try:
        up_count = int(up_count)
    except (TypeError, ValueError):
        up_count = 0

    ospf_neighbors = metrics.get("ospf_neighbors")
    if ospf_neighbors is None and isinstance(raw, dict):
        ospf_neighbors = raw.get("ospf_neighbors")
    if ospf_neighbors is None and hasattr(raw, "ospf_neighbors"):
        ospf_neighbors = getattr(raw, "ospf_neighbors", None)
    if ospf_neighbors is None:
        ospf_neighbors = 2

    try:
        ospf_neighbors = int(ospf_neighbors)
    except (TypeError, ValueError):
        ospf_neighbors = 0

    error_count = metrics.get("error_count")
    if error_count is None and isinstance(raw, dict):
        error_count = raw.get("error_count")
    if error_count is None and hasattr(raw, "error_count"):
        error_count = getattr(raw, "error_count", None)
    if error_count is None:
        error_count = 0

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

    normalized["interface_status"] = interface_status
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
    """Store derived ML features and incident context inside interface_status."""
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
    """Return the canonical 8-feature vector in model order."""
    normalized = normalize_telemetry(raw)
    if normalized is None:
        return [0.0] * len(TELEMETRY_FEATURE_ORDER)
    return [normalized[key] for key in TELEMETRY_FEATURE_ORDER]


class RealNetworkConnector:
    def __init__(self, device):
        self.device = device
        self.connection = None

    def connect(self):
        try:
            device_type_map = {
                "mikrotik_routeros": "mikrotik_routeros",
                "cisco_ios": "cisco_ios",
                "frr": "linux",
            }
            device_type = device_type_map.get(self.device.device_type, "cisco_ios")
            self.connection = ConnectHandler(
                device_type=device_type,
                host=self.device.ip_address,
                port=self.device.ssh_port,
                username=self.device.username,
                password=self.device.password,
                timeout=15,
            )
            return True
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            print(f"[REAL CONNECTOR] {exc}")
            return False

    def disconnect(self):
        if self.connection:
            try:
                self.connection.disconnect()
            finally:
                self.connection = None

    def collect_telemetry(self):
        if not self.connection and not self.connect():
            return None

        profile = get_profile(self.device.device_type)
        parser = profile.get("parser")
        telemetry_cmds = profile.get("telemetry_commands", {})
        raw_outputs = {}

        for key, command in telemetry_cmds.items():
            try:
                output = self.connection.send_command(command, expect_string=None)
            except Exception as exc:
                output = f"ERROR: {exc}"
            raw_outputs[key] = output

        parsed = {}
        try:
            if parser:
                parsed["cpu_usage"] = parser.parse_cpu(raw_outputs.get("cpu", "") or "")
                parsed["memory_usage"] = parser.parse_memory(raw_outputs.get("memory", "") or "")
                interfaces_raw = raw_outputs.get("interfaces", "") or ""
                parsed["interface_status"] = parser.parse_interfaces(interfaces_raw)
                parsed["packet_loss"] = parser.parse_packet_loss(interfaces_raw)
        except Exception:
            parsed["cpu_usage"] = None
            parsed["memory_usage"] = None
            parsed["interface_status"] = {}
            parsed["packet_loss"] = 0.0

        parsed["raw_output"] = raw_outputs
        return normalize_telemetry(parsed)

    def execute_healing_command(self, command):
        if not self.connection and not self.connect():
            return {"success": False, "output": "Not connected"}
        try:
            output = self.connection.send_command(command)
            return {"success": True, "output": output}
        except Exception as exc:
            return {"success": False, "output": str(exc)}

    def get_incident_context(self):
        return {}


class SimulatedConnector:
    """Connector that shares the same SimulatedDevice instance."""

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
        pass

    def collect_telemetry(self):
        raw = self.sim.get_telemetry()
        if raw is None:
            return None

        normalized = normalize_telemetry(raw)
        context = self.sim.get_incident_context() or {}
        normalized["__context__"] = dict(context)
        normalized["context"] = dict(context)
        return normalized

    def execute_healing_command(self, command):
        command_lower = command.lower()
        if "restart" in command_lower or "reboot" in command_lower or "reload" in command_lower:
            action_type = "RESTART_SERVICE"
        elif "shutdown" in command_lower or "enable" in command_lower or "no shutdown" in command_lower:
            action_type = "REROUTE_TRAFFIC"
        elif "access-list" in command_lower or "block" in command_lower or "firewall" in command_lower:
            action_type = "BLOCK_SOURCE_IP"
        else:
            action_type = "HEAL"

        success, message = self.sim.heal(action_type)
        return {"success": success, "output": message}

    def inject_failure(self, failure_type, **kwargs):
        return self.sim.inject_failure(failure_type, **kwargs)

    def get_incident_context(self):
        return self.sim.get_incident_context()

    def verify_recovery(self):
        telemetry = self.collect_telemetry()
        healthy = self.sim.is_healthy()
        return healthy, telemetry


def get_connector(device):
    if getattr(device, "device_type", "") == "simulated":
        return SimulatedConnector(device)
    return RealNetworkConnector(device)