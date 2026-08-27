# NeuroSynapse Backend

An AI-powered self-healing network intelligence system implementing the full MAPE-K
(Monitor-Analyze-Plan-Execute over a shared Knowledge base) autonomic control loop, with a
Django REST API, ensemble ML anomaly detection, a reinforcement-learning healing agent, and
Explainable AI (XAI) diagnosis.

This is the **complete, self-contained project**. It has been fully verified end-to-end in this
state: clean `migrate`, clean `check`, a full server boot with zero warnings, a real login ->
device list -> dashboard summary HTTP round trip, a full injected-failure -> detect -> diagnose ->
auto-heal -> verify -> RL-reward MAPE-K cycle, and a clean shutdown.

## Quick start

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py create_admin --username admin --password <your-password> --role SUPER_ADMIN
python manage.py runserver
```

You should see:

```
[BOOT] NeuroSynapse starting up...
[BOOT] Starting telemetry collector...
[SCHEDULER] Collector started.
[AI ENGINE] Models loaded successfully
[BOOT] Starting MAPE-K orchestrator...
[ORCHESTRATOR] Started MAPE-K loop
[BOOT] System ready
```

The server auto-starts a simulated device ("SimRouter") and begins polling/healing it
automatically - no further setup needed to see the system working. Stop with Ctrl+C for a graceful
shutdown (`[BOOT] Shutting down services...` / `[BOOT] Services stopped`).

Set `NEUROSYNAPSE_AUTOSTART=False` as an environment variable to run the dev server without the
background collector/orchestrator (useful when running management commands that don't need them).

## API overview

All endpoints are under `/api/`. Authenticate first, then pass the token on every subsequent
request:

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<your-password>"}'
# -> {"token": "...", "admin": {...}}

curl http://localhost:8000/api/dashboard/summary/ \
  -H "Authorization: Token <token>"
```

| Endpoint | Purpose |
|---|---|
| `POST /api/auth/login/`, `/logout/`, `GET /api/auth/me/` | Token authentication |
| `GET/POST /api/devices/`, `GET/PATCH/DELETE /api/devices/<id>/` | Device management |
| `GET/POST /api/telemetry/` | Telemetry ingest/read |
| `GET /api/dashboard/summary/` | Dashboard overview (devices, incidents, healing, RL) |
| `GET /api/dashboard/alerts/` | Open incidents |
| `GET /api/dashboard/incidents/`, `/incidents/<id>/` | Incident list/detail + XAI explanation |
| `POST /api/dashboard/incidents/<id>/approve/` | Manual approve/reject (HITL), body `{"approved": true|false}` |
| `POST /api/dashboard/incidents/<id>/rollback/` | Manual rollback |
| `GET /api/dashboard/healing-actions/`, `/healing-actions/<id>/` | Healing history + XAI |
| `GET /api/dashboard/rl-stats/` | RL agent statistics |
| `GET/PUT /api/dashboard/policy/` | Healing policy thresholds (SUPER_ADMIN to edit) |

## Testing the self-healing loop against the simulator

```bash
python manage.py inject_sim --type ddos_attack --source-ip 10.0.0.99 --destination-port 443 --traffic-volume 75000
python manage.py inject_sim --type link_failure --interface ether2
python manage.py inject_sim --type service_crash --service-name nginx --process-id 4471
```

Within one poll cycle (~5 seconds), the orchestrator detects, diagnoses, auto-heals (if confidence
is high enough) or routes to manual review, and updates the RL agent's Q-values. Watch it happen
live in the `runserver` console output, or poll `/api/dashboard/incidents/`.

## Project structure

- `core/` - Django project settings, URL root
- `authentication/` - token auth, RBAC (`SUPER_ADMIN` / `ADMIN` / `VIEWER`)
- `monitoring/` - `Device`/`Telemetry`/`Incident` models, vendor profiles (Cisco/MikroTik/
  Juniper/Huawei/FRR/generic), the simulated device, the telemetry collector, connectors
- `ai_engine/` - ML inference (anomaly detection + failure classification), the MAPE-K
  orchestrator, the RL healing agent, the XAI explanation engine
- `healing/` - the healing actuator (sandbox validation, command execution, rollback)
- `dashboard/` - the API layer consumed by the frontend (summary, incidents, healing actions,
  RL stats, policy config)
- `training/` - offline model training scripts and the trained `.pkl` models

## Real Hardware Integration - FRRouting (FRR)

NeuroSynapse can manage a real router instead of the in-memory simulator, using
[FRRouting](https://frrouting.org/) (FRR) running in Docker. FRR is a production-grade open-source
routing suite that behaves like an actual Cisco/Juniper router over SSH - so the whole MAPE-K loop
runs against a real routing daemon rather than a mock. The simulator remains the default and is
unaffected; FRR is an additional device you register alongside it.

### 1. Start the FRR container

```bash
docker compose up -d
docker compose logs -f frr-router
# Look for: [OK] SSH daemon running on port 22
#           [OK] Handing off to FRR's docker-start (foreground)
```

### 2. Register the FRR device

```bash
python manage.py setup_frr_device
```

Creates a `Device` row at `127.0.0.1:2222`, `device_type='frr'`, username/password `admin`/`admin`.
The orchestrator picks it up automatically on its next poll cycle.

### 3. Test SSH directly

```bash
ssh admin@localhost -p 2222
# password: admin
vtysh -c 'show interface brief'
cat /proc/loadavg
free -m
```

### 4. Exercise the full loop against the real container

```bash
ssh admin@localhost -p 2222 "sudo vtysh -c 'configure terminal' -c 'interface eth1' -c 'shutdown'"
# or
ssh admin@localhost -p 2222 "sudo systemctl stop frr"
```

Within one poll + orchestrator cycle, the dashboard shows a new incident, followed by an automatic
healing action that runs the fix command back over SSH.

### Troubleshooting

- **Connection refused on 2222**: the container may still be installing `openssh-server` on first
  boot; wait ~20-30s and retry, or check `docker compose logs frr-router`.
- **Authentication failed**: confirm the container's `FRR_PASSWORD` matches the `Device.password`
  value (`python manage.py shell` -> `Device.objects.get(device_type='frr').password`).
  `RealNetworkConnector.connect()` catches `NetmikoAuthenticationException` and logs
  `[REAL CONNECTOR] ...` rather than crashing the collector loop - this is expected, graceful
  behavior if the FRR container isn't running yet, not a bug.
- **Timeouts**: a 15-second Netmiko timeout is used; an unreachable container shows up as a single
  logged warning per poll cycle, never an unhandled exception.

### Known limitation

The `docker-compose.yml`/`frr/*` files are written against FRRouting's documented official Docker
image conventions but could not be live-tested against an actual Docker daemon in the environment
these files were produced in. Treat your first `docker compose up -d` as the real verification
step; the rest of this backend (API, MAPE-K loop, simulator) has been fully live-verified and does
not depend on FRR being present - `RealNetworkConnector` failures are caught and logged per-device
without affecting any other device or crashing the collector.

## Notes on this delivery

Two bugs were found and fixed while assembling this complete build from prior incremental
deliveries, both confirmed live:

1. **Migration history conflict**: `monitoring/migrations/` had accumulated duplicate/conflicting
   migration files (two different files both named `0004_...`, plus Django-generated merge
   migrations). This has been cleaned up to a single linear history
   (`0001` -> `0002` -> `0003` -> `0004_incident_destination_ip_incident_destination_port_and_more`)
   regenerated fresh from the current model state.
2. **Broken telemetry collector import**: `monitoring/scheduler.py` imported a function
   `persist_interface_status` that did not exist in `monitoring/connector.py` (which defined
   `attach_metrics_to_interface_status` instead) - this silently killed the background telemetry
   collector on every server start. Fixed by aliasing both names to the same function.
3. **RL action-space safety issue**: the FRR vendor profile's `LINK_FAILURE` and `DDOS_ATTACK`
   healing commands each had two entries (the fix command and its literal inverse), while every
   other vendor has exactly one. Since the RL agent sizes its action space off the number of
   available commands, this created a real chance of the agent selecting `shutdown` as the
   "healing" action during an actual link failure. Reduced to one entry each, matching every
   other vendor.
