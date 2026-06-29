
# NeuroSynapse – AI-Powered Self-Healing Network Intelligence System

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://djangoproject.com)
[![Vue](https://img.shields.io/badge/Vue-3.5-brightgreen.svg)](https://vuejs.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**NeuroSynapse** is a final-year research project that implements an autonomous **self-healing network** using the **MAPE-K (Monitor–Analyze–Plan–Execute–Knowledge)** control loop from autonomic computing.

The system detects, diagnoses, and remedies common network failures in real time without human intervention while continuously improving its healing decisions using reinforcement learning.

---

## Project Information

- **Author:** Blessings B Chongo
- **Supervisor:** Dr. Ntalasha
- **Institution:** The Copperbelt University
- **GitHub:** https://github.com/BlessingsBlessedChongo/NeuroSynapse

---

# Objectives (Proposal Requirements)

The project satisfies the following objectives:

1. **Real-time anomaly detection**
   - Achieves >90% detection accuracy using an ensemble of:
     - Isolation Forest
     - Local Outlier Factor (LOF)

2. **Automatic failure classification**
   - SERVICE_CRASH
   - LINK_FAILURE
   - DDOS_ATTACK

3. **Autonomous healing**
   - Restarts failed services
   - Reroutes traffic
   - Blocks malicious IPs
   - Completes healing within 30 seconds

4. **Interactive Dashboard**
   - Live telemetry charts
   - Incident monitoring
   - Explainable AI (XAI)
   - Manual override

5. **Reinforcement Learning**
   - Q-Learning continuously improves healing policies
   - Minimum improvement target: **15%**

All objectives have been validated end-to-end.

---

# Architecture (MAPE-K)

```text
           ┌──────────┐
           │ MONITOR  │
           └────┬─────┘
                │
                ▼
          ┌──────────┐
          │ ANALYZE  │
          └────┬─────┘
               │
               ▼
           ┌────────┐
           │ PLAN   │
           └────┬───┘
                │
                ▼
         ┌────────────┐
         │ EXECUTE    │
         └────┬───────┘
              │
              ▼
        ┌────────────┐
        │ KNOWLEDGE  │
        └────┬───────┘
             │
             └──────────────────────────┐
                                        │
                                        ▼
                                   (Feedback Loop)
```

### Monitor

Collects network telemetry every **5 seconds**.

### Analyze

Uses:

- Isolation Forest
- Local Outlier Factor
- Random Forest Classifier

to detect and classify anomalies.

### Plan

A Q-learning reinforcement learning agent selects the best healing strategy.

### Execute

Safely validates and executes remediation.

### Knowledge

Updates the RL policy using rewards:

- +1 Successful healing
- -1 Failed healing

---

## Vendor Support

NeuroSynapse is vendor-agnostic.

Supported vendors:

- Cisco IOS
- MikroTik RouterOS
- Juniper JunOS
- Huawei VRP

A lightweight in-memory simulator is included for testing without physical hardware.

---

# Technology Stack

| Layer | Technologies |
|--------|--------------|
| Backend | Python 3.10+, Django 4.2, Django REST Framework |
| Machine Learning | Scikit-learn, PyOD, PyTorch |
| Network | Netmiko, Paramiko |
| Simulator | Custom Python Device Simulator |
| Frontend | Vue 3, Vuetify 3, Pinia, Vue Router, Chart.js, Axios |
| Database | SQLite (default), PostgreSQL supported |
| Testing | Django Commands, Custom Validation Suite |

---

# Project Structure

```text
NeuroSynapse/
│
├── backend/
│   ├── manage.py
│   ├── core/
│   ├── monitoring/
│   │   ├── models.py
│   │   ├── connector.py
│   │   ├── scheduler.py
│   │   ├── simulated_device.py
│   │   ├── vendor_profiles.py
│   │   └── management/
│   │       └── commands/
│   │
│   ├── ai_engine/
│   │   ├── inference.py
│   │   ├── orchestrator.py
│   │   ├── rl_agent.py
│   │   ├── xai.py
│   │   └── management/
│   │       └── commands/
│   │
│   ├── healing/
│   │   └── actuator.py
│   │
│   ├── dashboard/
│   ├── templates/
│   └── static/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   ├── stores/
│   │   ├── services/
│   │   └── plugins/
│   ├── package.json
│   └── vite.config.js
│
├── models/
│   ├── anomaly_detector.pkl
│   ├── failure_classifier.pkl
│   └── feature_columns.pkl
│
├── training/
│   ├── generate_training_data.py
│   └── train_models.py
│
├── tests/
├── requirements.txt
├── .gitignore
└── README.md
```

---

# Quick Start

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm
- Git (optional)

---

## 1. Clone Repository

```bash
git clone https://github.com/BlessingsBlessedChongo/NeuroSynapse.git

cd NeuroSynapse
```

---

## 2. Backend Setup

Create a virtual environment.

### Linux / macOS

```bash
python -m venv venv

source venv/bin/activate
```

### Windows

```bash
python -m venv venv

venv\Scripts\activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

Navigate to Django.

```bash
cd backend
```

Apply migrations.

```bash
python manage.py migrate
```

Train machine learning models.

```bash
cd ..

python training/generate_training_data.py

python training/train_models.py
```

---

## 3. Frontend Setup

```bash
cd frontend

npm install
```

---

## 4. Start the System

Open **four terminals**.

### Terminal 1

```bash
python manage.py runserver
```

---

### Terminal 2

```bash
python manage.py start_collector
```

---

### Terminal 3

```bash
python manage.py start_orchestrator
```

---

### Terminal 4

```bash
cd frontend

npm run dev
```

Visit

```
http://localhost:3000
```

or

```
http://localhost:8000
```

The simulator automatically creates **SimRouter** and begins collecting telemetry.

---

# Configuring Real Routers

## Step 1

Prepare the router.

- Enable SSH
- Assign reachable IP
- Create SSH user

---

## Step 2

Add the device.

```bash
python manage.py add_device \
    --name "CoreSwitch" \
    --ip 192.168.1.1 \
    --type cisco_ios \
    --user admin \
    --pass your_password
```

Supported device types:

- cisco_ios
- mikrotik_routeros
- juniper_junos
- huawei_vrp
- generic

---

## Step 3

Update or Remove Device

```bash
python manage.py shell
```

```python
from monitoring.models import Device

d = Device.objects.get(ip_address="192.168.1.1")

d.status = "OFFLINE"

d.save()
```

---

# Injecting Failures

Service Crash

```bash
python manage.py inject_sim --type service_crash
```

Link Failure

```bash
python manage.py inject_sim --type link_failure
```

DDoS Attack

```bash
python manage.py inject_sim --type ddos
```

---

# Single MAPE-K Verification

```bash
python manage.py test_loop --type service_crash
```

Runs one complete Monitor → Analyze → Plan → Execute → Knowledge cycle.

---

# Dashboard Features

The dashboard provides:

- System Status Indicator
- Device Statistics
- Live Telemetry Charts
- Device Monitoring
- Incident List
- Healing History
- Explainable AI (XAI)
- Reinforcement Learning Statistics
- MAPE-K Progress Indicator
- Manual Override Panel

---

# REST API

| Endpoint | Method | Description |
|-----------|--------|-------------|
| `/api/health/` | GET | Health Check |
| `/api/status/` | GET | Overall System Status |
| `/api/telemetry/` | GET | Latest Telemetry |
| `/api/incidents/` | GET | Incident List |
| `/api/rl-stats/` | GET | RL Statistics |
| `/api/xai/diagnosis/<id>/` | GET | Diagnosis Explanation |
| `/api/xai/healing/<id>/` | GET | Healing Explanation |
| `/api/incidents/<id>/approve/` | POST | Approve Incident |
| `/api/incidents/<id>/reject/` | POST | Reject Incident |

---

# Testing

Run complete validation.

```bash
cd backend

python ../tests/test_all_objectives.py
```

---

## Validate Reinforcement Learning

```bash
python manage.py validate_rl
```

---

## SSH / AI Tests

```bash
python manage.py test_ssh
```

```bash
python manage.py test_ai
```

---

# Troubleshooting

| Problem | Solution |
|----------|----------|
| ModuleNotFoundError | Activate virtual environment and install dependencies |
| Models missing | Run training scripts |
| Dashboard shows 0 devices | Restart collector or add a device |
| Authentication errors | Use simulator or valid SSH credentials |
| Port already in use | `python manage.py runserver 8001` |
| CORS errors | Configure `django-cors-headers` correctly |

---

# Future Work

- Deep Q Networks (DQN)
- PPO Reinforcement Learning
- LSTM Failure Prediction
- Transformer-based Prediction
- Docker Sandbox
- PostgreSQL Deployment
- Gunicorn + Nginx
- Support for Arista
- Support for HPE
- SD-WAN Integration

---

# License

Released under the **MIT License**.

See the `LICENSE` file.

---

# Acknowledgements

Special thanks to:

- Dr. Ntalasha
- Copperbelt University Department of ICT (DICT)

This work builds upon research by:

- Kephart & Chess (Autonomic Computing)
- Chandola et al. (Anomaly Detection)
- Zhang et al. (Reinforcement Learning for Self-Healing Networks)

---

# Project Vision

> **NeuroSynapse  - shifting network management from human-dependent reaction to machine-led proactive intelligence.**
