from monitoring.simulated_device import SimulatedDevice, TELEMETRY_FEATURE_ORDER
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException


def normalize_telemetry(raw):
    """
    Normalize raw telemetry (dict or Django model) into the canonical 8-feature contract.
    Returns a dict with keys in TELEMETRY_FEATURE_ORDER plus optional metadata fields.
    """
    if raw is None:
        return None

    def _get(key, default=0.0):
        if hasattr(raw, key):
            value = getattr(raw, key)
        elif isinstance(raw, dict):
            value = raw.get(key, default)
        else:
            value = default
        if value is None:
            return default
        if key in ('interface_up_count', 'ospf_neighbors', 'error_count'):
            return int(value)
        return float(value)

    interface_status = None
    if hasattr(raw, 'interface_status'):
        interface_status = raw.interface_status
    elif isinstance(raw, dict):
        interface_status = raw.get('interface_status', {})

    if not interface_status:
        interface_status = {}

    metrics = {}
    if isinstance(interface_status, dict) and '__metrics__' in interface_status:
        metrics = interface_status.get('__metrics__', {}) or {}

    up_count = None
    if metrics.get('interface_up_count') is not None:
        up_count = int(metrics['interface_up_count'])
    elif isinstance(raw, dict) and 'interface_up_count' in raw:
        up_count = int(raw['interface_up_count'])
    elif hasattr(raw, 'interface_up_count') and getattr(raw, 'interface_up_count', None) is not None:
        up_count = int(getattr(raw, 'interface_up_count'))

    if up_count is None:
        up_count = sum(
            1 for name, details in interface_status.items()
            if not str(name).startswith('__')
            and isinstance(details, dict)
            and details.get('status') == 'up'
        )

    ospf_neighbors = metrics.get('ospf_neighbors')
    if ospf_neighbors is None:
        if isinstance(raw, dict) and 'ospf_neighbors' in raw:
            ospf_neighbors = int(raw['ospf_neighbors'])
        elif hasattr(raw, 'ospf_neighbors') and getattr(raw, 'ospf_neighbors', None) is not None:
            ospf_neighbors = int(getattr(raw, 'ospf_neighbors'))
        else:
            ospf_neighbors = int(_get('ospf_neighbors', 2))

    error_count = metrics.get('error_count')
    if error_count is None:
        if isinstance(raw, dict) and 'error_count' in raw:
            error_count = int(raw['error_count'])
        elif hasattr(raw, 'error_count') and getattr(raw, 'error_count', None) is not None:
            error_count = int(getattr(raw, 'error_count'))
        else:
            error_count = int(_get('error_count', 0))

    normalized = {
        'cpu_usage': _get('cpu_usage', 0.0),
        'memory_usage': _get('memory_usage', 0.0),
        'packet_loss': _get('packet_loss', 0.0),
        'latency_ms': _get('latency_ms', 5.0),
        'bandwidth_util': _get('bandwidth_util', 30.0),
        'interface_up_count': up_count,
        'ospf_neighbors': int(ospf_neighbors),
        'error_count': int(error_count),
    }

    if isinstance(raw, dict):
        if 'interface_status' in raw:
            normalized['interface_status'] = raw['interface_status']
        if 'raw_output' in raw:
            normalized['raw_output'] = raw['raw_output']
    elif hasattr(raw, 'interface_status') and raw.interface_status:
        normalized['interface_status'] = raw.interface_status
    if hasattr(raw, 'raw_output'):
        normalized['raw_output'] = raw.raw_output or ''

    return normalized


def attach_metrics_to_interface_status(normalized):
    """Persist derived ML features alongside interface JSON for ORM round-trips."""
    interface_status = dict(normalized.get('interface_status') or {})
    interface_status['__metrics__'] = {
        'interface_up_count': normalized['interface_up_count'],
        'ospf_neighbors': normalized['ospf_neighbors'],
        'error_count': normalized['error_count'],
    }
    return interface_status


def telemetry_to_feature_vector(raw):
    """Return numpy-ready list of 8 features in strict training order."""
    normalized = normalize_telemetry(raw)
    if normalized is None:
        return [0.0] * len(TELEMETRY_FEATURE_ORDER)
    return [normalized[key] for key in TELEMETRY_FEATURE_ORDER]


class RealNetworkConnector:
    """Real SSH connector (used for physical/virtual routers)."""

    def __init__(self, device):
        self.device = device
        self.connection = None

    def connect(self):
        try:
            device_type_map = {
                'mikrotik_routeros': 'mikrotik_routeros',
                'cisco_ios': 'cisco_ios',
            }
            device_type = device_type_map.get(self.device.device_type, 'cisco_ios')
            self.connection = ConnectHandler(
                device_type=device_type,
                host=self.device.ip_address,
                port=self.device.ssh_port,
                username=self.device.username,
                password=self.device.password,
                timeout=15,
            )
            return True
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
            print(f"[REAL CONNECTOR] {e}")
            return False

    def disconnect(self):
        if self.connection:
            self.connection.disconnect()
            self.connection = None

    def collect_telemetry(self):
        if not self.connection and not self.connect():
            return None
        return None


class SimulatedConnector:
    """In-memory connector that wraps a SimulatedDevice."""

    def __init__(self, device):
        self.device = device
        self.sim = SimulatedDevice(device.name)

    def connect(self):
        return True

    def disconnect(self):
        pass

    def collect_telemetry(self):
        raw = self.sim.get_telemetry()
        return normalize_telemetry(raw)

    def execute_healing_command(self, command):
        command_lower = command.lower()
        if 'restart' in command_lower or 'reboot' in command_lower or 'reload' in command_lower:
            action_type = 'RESTART_SERVICE'
        elif 'shutdown' in command_lower or 'enable' in command_lower or 'no shutdown' in command_lower:
            action_type = 'REROUTE_TRAFFIC'
        elif 'access-list' in command_lower or 'block' in command_lower or 'firewall' in command_lower:
            action_type = 'BLOCK_SOURCE_IP'
        else:
            action_type = 'HEAL'
        success, msg = self.sim.heal(action_type)
        return {'success': success, 'output': msg}

    def inject_failure(self, failure_type):
        return self.sim.inject_failure(failure_type)

    def verify_recovery(self):
        telemetry = self.collect_telemetry()
        healthy = self.sim.is_healthy()
        return healthy, telemetry


def get_connector(device):
    if getattr(device, 'device_type', '') == 'simulated':
        return SimulatedConnector(device)
    return RealNetworkConnector(device)
