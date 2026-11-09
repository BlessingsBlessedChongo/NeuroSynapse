# NeuroSynapse Backend

An AI-powered self-healing network intelligence system implementing the full MAPE-K
(Monitor-Analyze-Plan-Execute over a shared Knowledge base) autonomic control loop, with a
Django REST API, ensemble ML anomaly detection, a reinforcement-learning healing agent, and
Explainable AI (XAI) diagnosis.

Figure 3.2 state machine (preserved exactly):

```
MONITORING -> ANOMALY_DETECTED -> MANUAL_REVIEW / READY_FOR_ACTION
  -> SANDBOXING -> EXECUTION -> VERIFICATION -> HEALED / ROLLBACK
```

## Quick start

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py create_admin --username admin --password <your-password> --role SUPER_ADMIN
python manage.py runserver
```

Set `NEUROSYNAPSE_AUTOSTART=False` when running management commands / offline tests so the
background collector and orchestrator do not start.

## Device targets

| Device type | How it works | Default identity |
|---|---|---|
| `simulated` | DB-backed in-memory simulator (original) | `127.0.0.1` / SimRouter |
| `python_router` | Realistic in-process router (OSPF, multi-vendor ifaces, recovery delay) | `127.0.0.2` / PyRouter-01 |
| `frr` | Real FRRouting container over SSH (Alpine Linux) | `localhost:2222` admin/admin |

The simulated device is unchanged and remains the default autostart target.

## Live server startup

Run each service in its own terminal from `backend/`:

```bash
# Terminal 1: Django API
cd backend
python manage.py runserver 0.0.0.0:8000

# Terminal 2: telemetry collector
python manage.py start_collector

# Terminal 3: MAPE-K orchestrator
python manage.py start_orchestrator
```

Set `NEUROSYNAPSE_AUTOSTART=True` before starting Django to auto-start the
background services. Keep it `False` for management commands and offline tests.

## PythonRouter

PythonRouter mirrors a multi-vendor control-plane device without Docker:

```bash
# Auto-provisions Device(device_type=python_router, ip=127.0.0.2) if missing
python manage.py inject_failure --device-type python_router --type service_crash --service-name ospfd
python manage.py inject_failure --device-type python_router --type link_failure --interface eth0
python manage.py inject_failure --device-type python_router --type ddos_attack --source-ip 10.0.0.99 --destination-port 443 --traffic-volume 75000
```

Within one orchestrator cycle the incident transitions:

`ANOMALY_DETECTED -> READY_FOR_ACTION|MANUAL_REVIEW -> SANDBOXING -> EXECUTION -> VERIFICATION -> HEALED`

Verification waits for PythonRouter's realistic recovery timer (up to ~5s).

## FRR Docker (Alpine Linux)

`docker-compose.yml` runs the official `frrouting/frr` image as `neuro-frr` with **two** networks:

- `neurosynapse-net` -> container `eth0` (SSH / management — do **not** inject link_failure here)
- `frr-lab-net` -> container `eth1` (safe data-plane interface for failure demos)

```bash
cd backend
docker compose up -d
docker compose logs -f frr-router
# Expect: [OK] SSH daemon running on port 22

python manage.py setup_frr_device
ssh admin@localhost -p 2222   # password: admin
```

`frr/init.sh` installs on Alpine: `openssh`, `sudo`, `iproute2`, `iptables`, `openrc`, and
configures passwordless sudo for `admin` (`NOPASSWD:ALL` in `/etc/sudoers.d/admin`).

### Alpine healing / verification commands

NeuroSynapse never assumes systemd on FRR. Vendor profile + actuator use:

| Failure | Heal | Verify |
|---|---|---|
| SERVICE_CRASH | `rc-service frr restart` (fallback: `/etc/init.d/frr`, then `systemctl`) | `rc-service frr status` |
| LINK_FAILURE | `sudo -n ip link set dev eth1 up` | `ip -br link show eth1` |
| DDOS_ATTACK | `sudo -n iptables -A INPUT -s {ip} -j DROP` (fallback: blackhole route) | `iptables -C INPUT -s {ip} -j DROP` |

Sanity checks inside the container:

```bash
docker exec neuro-frr rc-service frr status
docker exec neuro-frr ip -br link
docker exec neuro-frr sudo -n true
docker exec neuro-frr which ip iptables rc-service
```

Inject against the lab NIC only:

```bash
python manage.py inject_failure --device-type frr --type link_failure --interface eth1
```

## Failure injection commands

### Simulated device

```bash
python manage.py inject_failure --device-type simulated --type service_crash --service-name nginx
python manage.py inject_failure --device-type simulated --type link_failure --interface ether1
python manage.py inject_failure --device-type simulated --type ddos --source-ip 10.0.0.99
```

### PythonRouter

```bash
python manage.py inject_failure --device-type python_router --type service_crash --service-name ospfd
python manage.py inject_failure --device-type python_router --type link_failure --interface eth0
python manage.py inject_failure --device-type python_router --type ddos --source-ip 10.0.0.99
```

### FRR Docker (Alpine Linux)

```bash
python manage.py inject_failure --device-type frr --type service_crash --service-name frr
python manage.py inject_failure --device-type frr --type link_failure --interface eth1
python manage.py inject_failure --device-type frr --type ddos --source-ip 10.0.0.5
```

The FRR management interface is `eth0`; use `eth1` for link-failure tests.

`--force-mgmt-interface` exists for advanced use; bringing `eth0` down severs SSH and the MAPE-K
loop cannot heal it automatically (`docker exec neuro-frr ip link set eth0 up` to recover).

## Real-dataset training (CICIDS 2017 + UNSW-NB15)

Models under `models/` (and mirrored under `backend/models/`, `backend/training/models/`) were
trained from CICIDS 2017 + UNSW-NB15 with labels mapped to NeuroSynapse failure types and features
projected onto the canonical 8-signal telemetry vector:

`cpu_usage, memory_usage, packet_loss, latency_ms, bandwidth_util, interface_up_count, ospf_neighbors, error_count`

Reported classifier accuracy: **91.56%** (macro F1 ~0.92, 5-fold CV mean ~0.912).

Retrain / cross-validate:

```bash
cd backend/training
python cicids2017/generate_training_data.py
python train_cross_dataset.py
python train_ensemble.py
# Copy resulting .pkl files into ../../models/ (project root) preferred by InferenceEngine
```

Inference loads from the first path that contains the full ensemble:

1. `<repo>/models/`
2. `<repo>/backend/models/`
3. `<repo>/backend/training/models/`

## HITL and confidence

Default confidence threshold is **0.70** (`HealingPolicyConfig.confidence_threshold` /
`NeuroSynapseOrchestrator.CONFIDENCE_THRESHOLD`).

- Classification confidence >= threshold -> `READY_FOR_ACTION` (auto-heal)
- Below threshold -> `MANUAL_REVIEW`
- Approve -> `READY_FOR_ACTION` then execution
- Reject -> `MONITORING`
- Manual rollback on `HEALED` -> `ROLLBACK` -> `MONITORING` (device state restored for simulators)

## RL agent

After successful / failed verification the RL agent records rewards and updates the Q-table.
Validate Objective 5 (>15% improvement) with a fresh (non-persisted) agent:

```bash
python manage.py validate_rl
```

## Objective test suite

```bash
set NEUROSYNAPSE_AUTOSTART=False   # Windows PowerShell: $env:NEUROSYNAPSE_AUTOSTART='False'
python tests/test_all_objectives.py
```

Expect `TEST SUMMARY: 28/28 passed` with the real-data models.

PythonRouter MAPE-K / HITL / XAI smoke test:

```bash
python test_verification_10items.py
```

## API overview

Authenticate, then pass the token:

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<your-password>"}'
```

| Endpoint | Purpose |
|---|---|
| `POST /api/auth/login/` | Token auth |
| `GET/POST /api/devices/` | Device management |
| `GET /api/dashboard/summary/` | Overview |
| `GET /api/dashboard/incidents/<id>/` | Incident + XAI (`concrete_context`) |
| `POST /api/dashboard/incidents/<id>/approve/` | HITL approve/reject |
| `POST /api/dashboard/incidents/<id>/rollback/` | Manual rollback |
| `GET /api/dashboard/rl-stats/` | RL statistics |
| `GET/PUT /api/dashboard/policy/` | Confidence / healing policy |

## Project structure

- `core/` - Django settings
- `authentication/` - token auth + RBAC
- `monitoring/` - devices, telemetry, connectors, PythonRouter, vendor profiles, inject_failure
- `ai_engine/` - inference, orchestrator, RL, XAI
- `healing/` - actuator (sandbox, execute, verify, rollback)
- `dashboard/` - REST API for the Vue frontend
- `training/` - CICIDS/UNSW pipelines and training scripts
- `frr/` - Alpine FRR container init + daemons config
- `tests/test_all_objectives.py` - objective validation suite

## Troubleshooting

| Symptom | Fix |
|---|---|
| Models not loaded / low accuracy | Ensure `isolation_forest.pkl`, `local_outlier_factor.pkl`, `failure_classifier.pkl`, `scaler.pkl`, `feature_columns.pkl` exist under `models/`. Prefer matching scikit-learn versions (train env vs runtime). |
| `InconsistentVersionWarning` on load | Align `scikit-learn` in `venv` with the version used to train (currently models pickled with 1.9.x). |
| inject_failure hits wrong python_router | Prefer `--ip 127.0.0.2` or delete extra rows; command now prefers canonical `127.0.0.2`. |
| FRR SSH connection refused on 2222 | Wait for init (`apk add` on first boot), check `docker compose logs frr-router`. |
| `sudo: a password is required` over SSH | Confirm init.sh wrote `/etc/sudoers.d/admin` and healing commands use `sudo -n`. |
| `systemctl: not found` | Expected on Alpine — use `rc-service` / OpenRC fallbacks already in vendor profiles. |
| `rc-service frr status` prints `status_of_proc: command not found` | Known FRR Alpine init quirk (Debian helper missing). NeuroSynapse verifies via `pgrep zebra` instead. |
| `ip: not found` | `iproute2` missing — init.sh should install it; rebuild container. |
| link_failure on eth0 never heals | You took down the management NIC. Recover with `docker exec neuro-frr ip link set eth0 up` and use `--interface eth1` next time. |
| Low confidence always MANUAL_REVIEW | Adjust `/api/dashboard/policy/` confidence_threshold (SUPER_ADMIN), or approve in the UI. |
| validate_rl below 15% | Ensure you run the updated command (fresh agent via `load_policy=False`). Do not compare against a hot Q-table loaded from DB. |
| Orchestrator interfering with tests | Export `NEUROSYNAPSE_AUTOSTART=False`. |

## Notes

1. FRR is optional. Collectors catch SSH failures per-device and never crash the loop.
2. Rollback-only actions (`UNBLOCK_*`, `CLEAR_*`) remain in vendor profiles for rollback lookup but are excluded from forward RL action selection.
3. Official FRR images are Alpine-based; all Linux healing paths prefer `rc-service` before `systemctl`.
