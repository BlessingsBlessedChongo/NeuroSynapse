# NeuroSynapse

NeuroSynapse is an AI-powered self-healing network system implementing the MAPE-K loop: monitor telemetry, analyze anomalies, plan a remediation, execute it through a sandboxed actuator, verify recovery, and persist knowledge through the RL agent. The backend supports simulated devices, PythonRouter, and an Alpine FRR Docker target.

## Prerequisites

- Python 3.11+
- Docker and Docker Compose for FRR testing
- SQLite (included with Python)
- Node 18+ only when running the existing frontend

## Backend setup

Windows PowerShell:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py check
```

Linux/macOS:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py check
```

## Run the backend

Use three terminals from `backend/`:

```bash
python manage.py runserver
python manage.py start_collector
python manage.py start_orchestrator
```

The API health endpoint is `GET /api/health/` and reports `models_healthy` and `db_ok`.

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

## Failure injection

```bash
python manage.py inject_failure --device-type simulated --type service_crash --service-name nginx
python manage.py inject_failure --device-type simulated --type link_failure --interface ether1
python manage.py inject_failure --device-type simulated --type ddos --source-ip 10.0.0.99

python manage.py inject_failure --device-type python_router --type service_crash --service-name ospfd
python manage.py inject_failure --device-type python_router --type link_failure --interface eth0
python manage.py inject_failure --device-type python_router --type ddos --source-ip 10.0.0.99

python manage.py inject_failure --device-type frr --type service_crash --service-name frr
python manage.py inject_failure --device-type frr --type link_failure --interface eth1
python manage.py inject_failure --device-type frr --type ddos --source-ip 10.0.0.5
```

FRR `eth0` is the SSH management interface. Use `eth1` for link-failure tests.

## Verification

```bash
python training/test_known_failures.py
python tests/test_all_objectives.py
python manage.py validate_rl
```

Dedicated model predictions use named pandas feature columns and median fallback. Every completed incident can be downloaded as a plain-text audit log from `/api/incidents/<id>/log/` or `/api/dashboard/incidents/<id>/log/` after authentication.

## Honest limitations

- The link-failure classifier is effectively a single-feature bandwidth-counter model; its observed bandwidth importance is approximately 0.9998.
- Several canonical features are zero-filled for individual benchmark models because those sources do not expose the corresponding sensor.
- The trained artifacts use public CIC-IDS2017, UNSW-NB15, Cisco telemetry, and service-trace data rather than Copperbelt University DICT production telemetry. Live CBU accuracy may differ and should be recalibrated with local telemetry.
- An iptables DROP rule by itself does not create DDoS traffic. Live DDoS detection requires traffic generation or telemetry with the trained high-bandwidth signature.
- FRR Alpine `rc-service frr status` may print the known `status_of_proc` warning; process-level `zebra` verification is used instead.

## Logs

Per-incident logs are written to `backend/logs/healing/incident_<id>_<timestamp>.log`. Runtime logs are excluded from version control.
