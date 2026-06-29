import random
from threading import Lock

# Canonical feature order consumed by ML models and the MAPE-K loop
TELEMETRY_FEATURE_ORDER = [
    'cpu_usage',
    'memory_usage',
    'packet_loss',
    'latency_ms',
    'bandwidth_util',
    'interface_up_count',
    'ospf_neighbors',
    'error_count',
]

FAILURE_ALIASES = {
    'service_crash': 'SERVICE_CRASH',
    'link_failure': 'LINK_FAILURE',
    'ddos': 'DDOS_ATTACK',
    'ddos_attack': 'DDOS_ATTACK',
}


class SimulatedDevice:
    """In-memory network device for development and E2E testing."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, name='SimRouter'):
        if self._initialized:
            return
        self.name = name
        self.lock = Lock()
        self._default_state()
        self._initialized = True

    def _default_state(self):
        self.cpu = 25.0
        self.memory = 40.0
        self.latency = 5.0
        self.bandwidth = 35.0
        self.packet_loss = 0.0
        self.interfaces = {
            'ether1': {'status': 'up'},
            'ether2': {'status': 'up'},
            'ether3': {'status': 'up'},
        }
        self.ospf_neighbors = 2
        self.error_count = 1
        self.health = 'HEALTHY'
        self.incident = None

    def _interface_up_count(self):
        return sum(1 for iface in self.interfaces.values() if iface.get('status') == 'up')

    def get_telemetry(self):
        """Return telemetry dict with all 8 canonical features."""
        with self.lock:
            if self.health == 'HEALTHY':
                self.cpu = max(5, min(45, 25 + random.uniform(-10, 15)))
                self.memory = max(20, min(60, 40 + random.uniform(-10, 15)))
                self.latency = max(2, min(12, 5 + random.uniform(-3, 5)))
                self.bandwidth = max(10, min(60, 35 + random.uniform(-15, 20)))
                self.packet_loss = max(0.0, min(0.5, random.uniform(0.0, 0.2)))
                self.ospf_neighbors = random.choice([1, 2, 3])
                self.error_count = max(0, random.randint(0, 3))
            up_count = self._interface_up_count()
            return {
                'cpu_usage': round(self.cpu, 2),
                'memory_usage': round(self.memory, 2),
                'packet_loss': round(self.packet_loss, 2),
                'latency_ms': round(self.latency, 2),
                'bandwidth_util': round(self.bandwidth, 2),
                'interface_up_count': up_count,
                'ospf_neighbors': int(self.ospf_neighbors),
                'error_count': int(self.error_count),
                'interface_status': {k: v.copy() for k, v in self.interfaces.items()},
                'raw_output': (
                    f"cpu:{self.cpu:.1f} mem:{self.memory:.1f} loss:{self.packet_loss:.1f} "
                    f"lat:{self.latency:.1f} bw:{self.bandwidth:.1f} up:{up_count} "
                    f"ospf:{self.ospf_neighbors} err:{self.error_count}"
                ),
            }

    def get_feature_vector(self):
        """Return the 8-feature vector in strict model order."""
        telemetry = self.get_telemetry()
        return [telemetry[key] for key in TELEMETRY_FEATURE_ORDER]

    def inject_failure(self, failure_type):
        """Inject SERVICE_CRASH, LINK_FAILURE, or DDOS_ATTACK telemetry profile."""
        with self.lock:
            key = failure_type.lower().strip()
            canonical = FAILURE_ALIASES.get(key)
            if not canonical:
                return f"Unknown failure: {failure_type}"

            if canonical == 'SERVICE_CRASH':
                self.cpu = 95.0
                self.memory = 88.0
                self.latency = 50.0
                self.bandwidth = 60.0
                self.packet_loss = 5.0
                self.interfaces = {k: {'status': 'up'} for k in self.interfaces}
                self.ospf_neighbors = 2
                self.error_count = 3
            elif canonical == 'LINK_FAILURE':
                self.cpu = 30.0
                self.memory = 44.0
                self.latency = 400.0
                self.bandwidth = 15.0
                self.packet_loss = 80.0
                self.interfaces = {
                    'ether1': {'status': 'down'},
                    'ether2': {'status': 'down'},
                    'ether3': {'status': 'down'},
                }
                self.ospf_neighbors = 0
                self.error_count = 55
            elif canonical == 'DDOS_ATTACK':
                self.cpu = 99.0
                self.memory = 70.0
                self.latency = 200.0
                self.bandwidth = 95.0
                self.packet_loss = 35.0
                self.interfaces = {k: {'status': 'up'} for k in self.interfaces}
                self.ospf_neighbors = 2
                self.error_count = 18

            self.health = 'CRITICAL'
            self.incident = canonical
        return f"INJECTED: {canonical}"

    def heal(self, action_type):
        """Reset device to healthy state after successful remediation."""
        with self.lock:
            self._default_state()
            return True, f"Healing successful via {action_type}"

    def is_healthy(self):
        with self.lock:
            return self.health == 'HEALTHY'
