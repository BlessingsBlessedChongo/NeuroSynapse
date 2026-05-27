# NeuroSynapse: AI-Powered Self-Healing Network Intelligence System

## Complete Technical Documentation

---

**Author:** Blessings B Chongo (SIN: 22105357)  
**Supervisor:** Dr Ntalasha  
**Institution:** The Copperbelt University  
**School:** Information and Communication Technology  
**Department:** Computer Science  
**Program:** Bachelor of Science in Computer Science  
**Date:** May 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Installation Guide](#4-installation-guide)
5. [Project Structure](#5-project-structure)
6. [Database Schema](#6-database-schema)
7. [API Reference](#7-api-reference)
8. [Management Commands](#8-management-commands)
9. [Vendor Profiles (Multi-Router Support)](#9-vendor-profiles)
10. [ML Models](#10-ml-models)
11. [Reinforcement Learning Agent](#11-reinforcement-learning-agent)
12. [Explainable AI (XAI)](#12-explainable-ai)
13. [Testing and Validation](#13-testing-and-validation)
14. [Deployment Guide](#14-deployment-guide)
15. [User Manual](#15-user-manual)
16. [Troubleshooting](#16-troubleshooting)
17. [Future Enhancements](#17-future-enhancements)

---

## 1. Project Overview

### 1.1 Problem Statement

Modern computer networks form the backbone of organizational operations, yet they remain vulnerable to frequent failures, security breaches, and performance degradation. Traditional network management systems are largely reactive, relying on manual intervention, which results in extended downtime, increased operational costs, and heightened security risks.

### 1.2 Solution

NeuroSynapse is an AI-powered self-healing network intelligence system that autonomously detects, diagnoses, and remediates network failures in real-time. Inspired by biological neural networks, the system implements the MAPE-K (Monitor-Analyze-Plan-Execute over Knowledge) autonomic computing framework.

### 1.3 Core Capabilities

| Capability | Description |
|------------|-------------|
| **Real-time Monitoring** | Collects network telemetry every 5 seconds |
| **Anomaly Detection** | Ensemble ML detects deviations >90% accuracy |
| **Failure Classification** | Identifies SERVICE_CRASH, LINK_FAILURE, DDOS_ATTACK |
| **Autonomous Healing** | Executes remediation within 30 seconds |
| **Continuous Learning** | RL agent improves healing success by >15% |
| **Explainable AI** | Plain-English explanations for all decisions |
| **Vendor-Agnostic** | Supports Cisco, MikroTik, Juniper, Huawei |

### 1.4 Objectives Achievement

| Objective | Target | Achieved |
|-----------|--------|----------|
| 1. Real-time Anomaly Detection | >90% accuracy | ✅ |
| 2. Automatic Failure Diagnosis | Classify 3 failure types | ✅ |
| 3. Autonomous Healing | <30 seconds execution | ✅ |
| 4. Interactive Dashboard | Real-time visualization | ✅ |
| 5. RL Feedback Loop | >15% improvement | ✅ |

---

## 2. System Architecture

### 2.1 MAPE-K Loop
┌─────────────────────────────────────────────────────────────┐
│ MAPE-K LOOP │
├─────────────────────────────────────────────────────────────┤
│ │
│ MONITOR ◄──────────────────────────────────────────────┐ │
│ │ │ │
│ │ Every 5 seconds: │ │
│ │ • SSH to network devices │ │
│ │ • Collect CPU, memory, interfaces │ │
│ │ • Save to SQLite database │ │
│ │ │ │
│ ▼ │ │
│ ANALYZE │ │
│ │ │ │
│ │ • Isolation Forest: anomaly detection │ │
│ │ • Random Forest: failure classification │ │
│ │ • Calculate confidence scores │ │
│ │ │ │
│ ▼ │ │
│ PLAN │ │
│ │ │ │
│ │ • RL Agent selects best healing action │ │
│ │ • Consults Q-table for learned experience │ │
│ │ • Epsilon-greedy policy │ │
│ │ │ │
│ ▼ │ │
│ EXECUTE │ │
│ │ │ │
│ │ • Sandbox validation (safety check) │ │
│ │ • SSH healing command to device │ │
│ │ • Verify network health post-healing │ │
│ │ │ │
│ ▼ │ │
│ KNOWLEDGE ───────────────────────────────────────────────┘ │
│ │ │
│ │ • Record reward (+1 success, -1 failure) │
│ │ • Update Q-table │
│ │ • Save policy to database │
│ │ • Return to MONITOR │
│ └─────────────────────────────────────────────────────────│
└─────────────────────────────────────────────────────────────┘

text

### 2.2 4-Tier Architecture

| Tier | Name | Technology | Purpose |
|------|------|------------|---------|
| 1 | Presentation | HTML/CSS/JavaScript | Dashboard, XAI, Alerts |
| 2 | Application | Django/Python | AI Engine, RL Agent, Orchestrator |
| 3 | Data | SQLite/Django ORM | Telemetry, Incidents, Rewards |
| 4 | Execution | SSH/Netmiko | Device communication, Healing |

### 2.3 Component Diagram
┌─────────────────────────────────────────────────────────────────┐
│ NEUROSYNAPSE │
├─────────────────────────────────────────────────────────────────┤
│ │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ Dashboard │ │ AI Engine │ │ RL Agent │ │
│ │ (HTML/CSS) │◄──►│ (ML Models) │ │ (Q-Learning)│ │
│ └──────────────┘ └──────┬───────┘ └──────┬───────┘ │
│ │ │ │
│ ┌──────┴────────────────────┴──────┐ │
│ │ ORCHESTRATOR │ │
│ │ (MAPE-K Controller) │ │
│ └──────┬───────────────────────────┘ │
│ │ │
│ ┌──────────────┼──────────────┐ │
│ │ │ │ │
│ ┌────┴────┐ ┌────┴────┐ ┌─────┴─────┐ │
│ │ Collector│ │ Healing │ │ XAI │ │
│ │ (5s loop)│ │ Actuator│ │ Engine │ │
│ └────┬─────┘ └────┬────┘ └───────────┘ │
│ │ │ │
│ ┌────┴──────────────┴────┐ │
│ │ SSH Client Layer │ │
│ │ (Vendor-Agnostic) │ │
│ └──────────┬──────────────┘ │
│ │ │
│ ┌──────────────┼──────────────┐ │
│ │ │ │ │
│ ┌──┴──┐ ┌───┴───┐ ┌───┴───┐ │
│ │Cisco│ │MikroTik│ │Juniper│ │
│ │ IOS │ │RouterOS│ │ JunOS │ │
│ └─────┘ └───────┘ └───────┘ │
│ │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ SQLite Database │ │
│ │ Devices | Telemetry | Incidents | HealingActions │ │
│ │ RLRewards | RLPolicies │ │
│ └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

text

---

## 3. Technology Stack

### 3.1 Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.10+ | Primary language |
| Django | 4.2+ | Web framework, ORM |
| Django REST Framework | 3.14+ | API endpoints |
| Netmiko | 4.3+ | SSH to network devices |
| AsyncSSH | 2.14+ | Mock SSH server |
| Scapy | 2.5+ | Packet manipulation |

### 3.2 Machine Learning

| Technology | Purpose |
|------------|---------|
| Scikit-learn | Isolation Forest, Random Forest |
| PyOD | Outlier detection algorithms |
| PyTorch | Deep learning (RL policy networks) |
| NumPy | Numerical computation |
| Pandas | Data manipulation |

### 3.3 Frontend

| Technology | Purpose |
|------------|---------|
| HTML5/CSS3 | Dashboard structure and styling |
| JavaScript (Vanilla) | Real-time updates |
| Chart.js (optional) | Data visualization |

### 3.4 Infrastructure

| Technology | Purpose |
|------------|---------|
| SQLite | Local database |
| Docker | Sandbox validation (optional) |
| Git | Version control |

---

## 4. Installation Guide

### 4.1 Prerequisites

- **Operating System:** Windows 10/11, Ubuntu 22.04+, or macOS
- **Python:** 3.10 or higher
- **RAM:** 4GB minimum, 8GB recommended
- **Disk:** 2GB free space
- **Network:** SSH access to managed devices (port 22)

### 4.2 Step-by-Step Installation

#### Step 1: Clone or Extract the Project

```bash
cd C:\Users\Blessings\Documents\
mkdir NeuroSynapse
cd NeuroSynapse
Step 2: Create Virtual Environment
bash
python -m venv venv
Step 3: Activate Virtual Environment
Windows:

bash
venv\Scripts\activate
Linux/macOS:

bash
source venv/bin/activate
Step 4: Install Dependencies
bash
pip install django djangorestframework netmiko paramiko asyncssh scapy
pip install scikit-learn numpy pandas pyod joblib
pip install python-dotenv bcrypt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
Step 5: Initialize Database
bash
cd backend
python manage.py makemigrations
python manage.py migrate
Step 6: Train ML Models
bash
cd ..
python training\generate_training_data.py
python training\train_models.py
Step 7: Start the System
Open three terminal windows:

Terminal 1 - Mock SSH Server:

bash
cd simulation
python mock_ssh_server.py
Terminal 2 - Django Server:

bash
cd backend
python manage.py runserver
Terminal 3 - Telemetry Collector:

bash
cd backend
python manage.py start_collector
Step 8: Access the Dashboard
Open browser: http://localhost:8000/

5. Project Structure
text
NeuroSynapse/
│
├── backend/                          # Django project root
│   ├── manage.py                     # Django management script
│   ├── core/                         # Project settings
│   │   ├── settings.py               # Django configuration
│   │   ├── urls.py                   # Root URL routing
│   │   └── wsgi.py                   # WSGI entry point
│   │
│   ├── monitoring/                   # Monitoring app
│   │   ├── models.py                 # Database models
│   │   ├── ssh_client.py             # Vendor-agnostic SSH client
│   │   ├── scheduler.py              # Telemetry collection loop
│   │   ├── vendor_profiles.py        # Router vendor configurations
│   │   ├── views.py                  # API views
│   │   ├── urls.py                   # API routes
│   │   └── management/
│   │       └── commands/
│   │           ├── start_collector.py
│   │           ├── test_ssh.py
│   │           ├── inject_failure.py
│   │           └── add_device.py
│   │
│   ├── ai_engine/                    # AI/ML app
│   │   ├── inference.py              # ML inference engine
│   │   ├── orchestrator.py           # MAPE-K loop controller
│   │   ├── rl_agent.py              # RL Q-learning agent
│   │   ├── xai.py                    # Explainable AI engine
│   │   └── management/
│   │       └── commands/
│   │           ├── start_orchestrator.py
│   │           ├── test_ai.py
│   │           ├── train_rl.py
│   │           └── validate_rl.py
│   │
│   ├── healing/                      # Healing app
│   │   └── actuator.py               # Healing action executor
│   │
│   ├── dashboard/                    # Dashboard app
│   │   ├── views.py                  # Dashboard views
│   │   └── urls.py                   # Dashboard routes
│   │
│   ├── templates/
│   │   └── dashboard.html            # Main dashboard
│   │
│   ├── static/                       # Static files
│   └── db.sqlite3                    # SQLite database
│
├── simulation/                       # Network simulation
│   └── mock_ssh_server.py           # Mock router SSH server
│
├── training/                         # ML training
│   ├── generate_training_data.py    # Synthetic data generator
│   └── train_models.py              # Model training script
│
├── models/                           # Trained ML models
│   ├── anomaly_detector.pkl          # Isolation Forest
│   ├── failure_classifier.pkl       # Random Forest classifier
│   ├── feature_columns.pkl          # Feature column names
│   └── model_metadata.pkl           # Training metadata
│
├── tests/                            # Testing suite
│   ├── test_all_objectives.py       # Complete validation
│   └── test_results/                 # Test output
│       └── validation_report.json
│
├── documentation/                    # Project documents
│   ├── Proposal.pdf
│   ├── Literature_Review.pdf
│   ├── Design_Specification.pdf
│   └── NeuroSynapse_Complete_Documentation.md
│
├── NeuroSynapse_Build_Plan.docx     # Development log
├── requirements.txt                  # Python dependencies
└── README.md                         # Quick start guide
6. Database Schema
6.1 Entity Relationship Diagram
text
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    DEVICE    │       │  TELEMETRY   │       │   INCIDENT   │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)      │──┐    │ id (PK)      │       │ id (PK)      │
│ name         │  │    │ device (FK)  │──┐    │ device (FK)  │
│ ip_address   │  │    │ timestamp    │  │    │ telemetry(FK)│
│ device_type  │  └───►│ cpu_usage    │  │    │ failure_type │
│ vendor       │       │ memory_usage │  │    │ confidence   │
│ status       │       │ packet_loss  │  │    │ status       │
│ ssh_port     │       │ latency_ms   │  │    │ description  │
│ username     │       │ bandwidth_util│ │    │ detected_at  │
│ password     │       │ interface_stats│   │ resolved_at  │
└──────────────┘       │ raw_output   │       └──────┬───────┘
                       └──────────────┘              │
                                                     │
                       ┌──────────────┐              │
                       │HEALING_ACTION│◄─────────────┘
                       ├──────────────┤
                       │ id (PK)      │
                       │ incident(FK) │
                       │ action_type  │
                       │ command      │
                       │ status       │
                       │ sandbox_result│
                       │ execution_output│
                       │ created_at   │
                       │ completed_at │
                       └──────┬───────┘
                              │
                     ┌────────┴────────┐
                     │                 │
              ┌──────┴──────┐   ┌──────┴──────┐
              │  RL_REWARD  │   │  RL_POLICY  │
              ├─────────────┤   ├─────────────┤
              │ id (PK)     │   │ id (PK)     │
              │ healing(FK) │   │ policy_name │
              │ reward_value│   │ policy_data │
              │ state_context│  │ performance │
              │ created_at  │   │ episodes    │
              └─────────────┘   │ updated_at  │
                                └─────────────┘
6.2 Table Descriptions
Device
Stores network device configurations (routers, switches).

Column	Type	Description
id	INTEGER (PK)	Auto-increment ID
name	VARCHAR(100)	Human-readable device name
ip_address	VARCHAR(39)	IP address (unique)
device_type	VARCHAR(50)	Vendor type (cisco_ios, mikrotik_routeros, etc.)
vendor	VARCHAR(50)	Vendor name (optional)
status	VARCHAR(20)	ONLINE, OFFLINE, DEGRADED
ssh_port	INTEGER	SSH port (default: 22)
username	VARCHAR(100)	SSH username
password	VARCHAR(255)	SSH password
created_at	DATETIME	Creation timestamp
Telemetry
Stores collected network metrics.

Column	Type	Description
id	INTEGER (PK)	Auto-increment ID
device	FK → Device	Source device
timestamp	DATETIME	Collection time
cpu_usage	FLOAT	CPU utilization (%)
memory_usage	FLOAT	Memory utilization (%)
latency_ms	FLOAT	Network latency (ms)
packet_loss	FLOAT	Packet loss (%)
bandwidth_util	FLOAT	Bandwidth utilization (%)
interface_status	JSON	Interface state details
raw_output	TEXT	Raw command output
Incident
Records detected network failures.

Column	Type	Description
id	INTEGER (PK)	Auto-increment ID
device	FK → Device	Affected device
telemetry_snapshot	FK → Telemetry	Triggering telemetry
failure_type	VARCHAR(50)	SERVICE_CRASH, LINK_FAILURE, DDOS_ATTACK
confidence_score	FLOAT	Classification confidence (0-1)
status	VARCHAR(20)	Incident lifecycle state
description	TEXT	Human-readable description
detected_at	DATETIME	Detection time
resolved_at	DATETIME	Resolution time
HealingAction
Records executed healing commands.

Column	Type	Description
id	INTEGER (PK)	Auto-increment ID
incident	FK → Incident	Parent incident
action_type	VARCHAR(30)	RESTART_SERVICE, REROUTE_TRAFFIC, etc.
command	TEXT	Executed command
status	VARCHAR(20)	Execution status
sandbox_result	VARCHAR(20)	Validation result
execution_output	TEXT	Command output
created_at	DATETIME	Start time
completed_at	DATETIME	Completion time
RLReward
Stores reinforcement learning feedback.

Column	Type	Description
id	INTEGER (PK)	Auto-increment ID
healing_action	FK → HealingAction	Associated action
reward_value	INTEGER	+1 (success) or -1 (failure)
state_context	JSON	Failure context
created_at	DATETIME	Reward time
RLPolicy
Stores learned Q-table policies.

Column	Type	Description
id	INTEGER (PK)	Auto-increment ID
policy_name	VARCHAR(100)	Unique policy name
policy_data	JSON	Q-table and parameters
performance_score	FLOAT	Recent success rate
training_episodes	INTEGER	Total episodes
updated_at	DATETIME	Last update
7. API Reference
7.1 Base URL
text
http://localhost:8000/api/
7.2 Endpoints
Health Check
text
GET /api/health/
Response:

json
{
    "status": "healthy",
    "system": "NeuroSynapse API",
    "version": "0.1.0"
}
System Status
text
GET /api/status/
Response:

json
{
    "devices": [
        {
            "id": 1,
            "name": "MockRouter01",
            "ip": "127.0.0.1",
            "status": "HEALTHY",
            "cpu": 25.0,
            "memory": 40.0,
            "packet_loss": 0.1,
            "last_seen": "2026-05-16T10:30:00"
        }
    ],
    "incident_count": 5,
    "open_incidents": 0,
    "healed_today": 3,
    "latest_incidents": [...],
    "recent_healings": [...]
}
Telemetry Data
text
GET /api/telemetry/
Response:

json
{
    "telemetry": [
        {
            "device": "MockRouter01",
            "records": [
                {
                    "timestamp": "2026-05-16T10:30:00",
                    "cpu": 25.0,
                    "memory": 40.0,
                    "packet_loss": 0.1
                }
            ]
        }
    ]
}
Incidents
text
GET /api/incidents/
Response:

json
{
    "incidents": [
        {
            "id": 1,
            "device": "MockRouter01",
            "type": "Service Crash",
            "confidence": 0.94,
            "status": "Healed",
            "detected_at": "2026-05-16T10:25:00",
            "resolved_at": "2026-05-16T10:25:08"
        }
    ]
}
RL Agent Stats
text
GET /api/rl-stats/
Response:

json
{
    "episode_count": 50,
    "epsilon": 0.156,
    "learning_rate": 0.1,
    "recent_performance": 0.9,
    "overall_performance": 0.78,
    "q_table_size": 9,
    "best_actions": {
        "SERVICE_CRASH": {"action_index": 0, "q_value": 0.729},
        "LINK_FAILURE": {"action_index": 0, "q_value": 0.673}
    }
}
XAI Diagnosis Explanation
text
GET /api/xai/diagnosis/{incident_id}/
Response:

json
{
    "failure_type": "SERVICE_CRASH",
    "confidence": 0.94,
    "confidence_level": "Very High",
    "summary": "The ML model detected a SERVICE CRASH with 94% confidence...",
    "key_evidence": [
        "CPU usage is at 95.0% (normal range: 20-45%)",
        "Memory usage is at 88.0% (normal range: 30-50%)"
    ],
    "what_this_means": "A service crash typically indicates...",
    "contributing_factors": [
        "High memory usage suggests a possible memory leak"
    ]
}
XAI Healing Explanation
text
GET /api/xai/healing/{healing_id}/
Response:

json
{
    "action_type": "Restart Service",
    "command": "restart service nginx",
    "success": true,
    "summary": "The Restart Service action was executed successfully...",
    "why_this_action": "Restarting the failed service is the most common...",
    "what_happened": "The command 'restart service nginx' was sent..."
}
8. Management Commands
8.1 Available Commands
Command	Purpose
start_collector	Start telemetry collection loop
start_orchestrator	Start MAPE-K orchestrator
test_ssh	Test SSH connection
test_ai	Test ML model predictions
train_rl	Train RL agent
validate_rl	Validate RL improvement (Objective 5)
inject_failure	Inject simulated failure
add_device	Add/update network device
8.2 Usage Examples
bash
# Start the telemetry collector
python manage.py start_collector

# Start the orchestrator
python manage.py start_orchestrator

# Test SSH connection
python manage.py test_ssh

# Test AI predictions
python manage.py test_ai

# Train RL agent with 50 episodes
python manage.py train_rl --episodes 50

# Validate RL improvement
python manage.py validate_rl

# Inject a failure for testing
python manage.py inject_failure --type service_crash
python manage.py inject_failure --type link_failure
python manage.py inject_failure --type ddos

# Add a MikroTik router
python manage.py add_device \
    --name "EdgeRouter" \
    --ip 192.168.88.1 \
    --type mikrotik_routeros \
    --user admin \
    --pass neuro1234

# Add a Cisco router
python manage.py add_device \
    --name "CoreSwitch" \
    --ip 192.168.1.1 \
    --type cisco_ios \
    --user admin \
    --pass cisco123

# Add mock device (for development)
python manage.py add_device \
    --name "MockRouter" \
    --ip 127.0.0.1 \
    --type generic \
    --port 2222 \
    --user admin \
    --pass anything
9. Vendor Profiles
9.1 Supported Routers
NeuroSynapse uses a vendor-agnostic architecture. All device-specific commands and parsers are defined in vendor_profiles.py. The core system never changes.

Vendor	device_type	Status
Cisco IOS	cisco_ios	✅ Supported
MikroTik RouterOS	mikrotik_routeros	✅ Supported
Juniper JunOS	juniper_junos	✅ Supported
Huawei VRP	huawei_vrp	✅ Supported
Generic/Mock	generic	✅ Development
9.2 Command Mappings
Metric	Cisco	MikroTik	Juniper	Huawei
CPU	show processes cpu	system resource print	show system processes summary	display cpu-usage
Memory	show processes memory	system resource print	show system memory	display memory-usage
Interfaces	show interfaces	interface print detail	show interfaces terse	display interface
9.3 Healing Command Mappings
Action	Cisco	MikroTik
Service Restart	reload	system reboot
Enable Interface	interface Gi0/1
no shutdown	interface enable ether2
Block IP	access-list 100 deny ip
host {ip} any	ip firewall filter add
chain=input src-address={ip}
action=drop
9.4 Adding a New Vendor
To add support for a new router vendor, add a new profile to vendor_profiles.py:

python
'arista_eos': {
    'name': 'Arista EOS',
    'device_type': 'arista_eos',
    'parser': AristaParser(),
    'telemetry_commands': {
        'cpu': 'show processes top once',
        'memory': 'show memory',
        'interfaces': 'show interfaces',
        'packet_loss': 'show interfaces',
    },
    'healing_commands': {
        'SERVICE_CRASH': [
            {
                'action_type': 'RESTART_SERVICE',
                'command': 'reload',
                'description': 'Reload the Arista switch',
            },
        ],
        # ... more actions
    },
},
That's all. No other code changes needed.

10. ML Models
10.1 Training Data
Source: Synthetic data generator (generate_training_data.py)

Samples per class: 500

Total samples: 2,000

Features: 8 (cpu_usage, memory_usage, packet_loss, latency_ms, bandwidth_util, interface_up_count, ospf_neighbors, error_count)

Classes: NORMAL, SERVICE_CRASH, LINK_FAILURE, DDOS_ATTACK

10.2 Anomaly Detector
Algorithm: Isolation Forest

Training data: NORMAL samples only

Contamination: 0.1 (expected anomaly rate)

Output: -1 (anomaly) or 1 (normal)

File: models/anomaly_detector.pkl

10.3 Failure Classifier
Algorithm: Random Forest

Estimators: 100

Max depth: 10

Cross-validation: 5-fold

Output: Failure type with probability

File: models/failure_classifier.pkl

10.4 Feature Importance
Feature	Importance
packet_loss	~30%
cpu_usage	~25%
latency_ms	~15%
bandwidth_util	~12%
interface_up_count	~8%
memory_usage	~5%
ospf_neighbors	~3%
error_count	~2%
10.5 Retraining
bash
# Generate new training data
python training\generate_training_data.py

# Retrain models
python training\train_models.py

# Test new models
python manage.py test_ai
11. Reinforcement Learning Agent
11.1 Algorithm
Type: Q-Learning (tabular)

State: Failure type (SERVICE_CRASH, LINK_FAILURE, DDOS_ATTACK)

Action: Index into healing actions list

Reward: +1 (successful healing), -1 (failed healing)

11.2 Parameters
Parameter	Default	Description
learning_rate (α)	0.1	How fast Q-values update
discount_factor (γ)	0.9	Future reward importance
epsilon (ε)	0.2	Exploration rate (decays over time)
epsilon_decay	0.995	Decay per episode
min_epsilon	0.05	Minimum exploration
11.3 Epsilon-Greedy Policy
text
if random() < epsilon:
    action = random_action()   # Explore
else:
    action = argmax(Q[state])   # Exploit
11.4 Q-Update Formula
text
Q(s,a) = Q(s,a) + α × (reward - Q(s,a))
11.5 Training Command
bash
# Basic training
python manage.py train_rl --episodes 50

# Extended training for better results
python manage.py train_rl --episodes 100
11.6 Validation
bash
python manage.py validate_rl
Expected output shows:

Baseline success rate (random actions)

Post-learning success rate (trained agent)

Improvement percentage

Target: >15% improvement.

12. Explainable AI (XAI)
12.1 Purpose
The XAI engine provides plain-English explanations for:

Why a particular diagnosis was made

Why a specific healing action was chosen

What evidence supports the decision

What the diagnosis means in practical terms

12.2 Explanation Components
Component	Description
summary	One-paragraph overview
key_evidence	Bullet points of supporting metrics
what_this_means	Practical interpretation
contributing_factors	Additional context and suggestions
confidence_level	Very High (≥90%), High (≥75%), Moderate (≥60%), Low (≥40%), Very Low (<40%)
12.3 Example Explanation
text
The ML model detected a SERVICE CRASH with 94% confidence.
This diagnosis is based primarily on critically high CPU
usage (95.0%) combined with elevated memory usage (88.0%).

Key Evidence:
• CPU usage is at 95.0% (normal range: 20-45%)
• Memory usage is at 88.0% (normal range: 30-50%)
• Packet loss is 3.0% (moderate, suggesting service issue)

What This Means:
A service crash typically indicates that a critical
application process (like nginx or a database) has stopped
responding. The moderate packet loss rules out a physical
link failure—the network is still up, but the service
running on it has failed.

Contributing Factors:
• High memory usage suggests a possible memory leak
13. Testing and Validation
13.1 Running the Test Suite
bash
cd C:\Users\Blessings\Documents\NeuroSynapse
python tests\test_all_objectives.py
13.2 Test Coverage
Objective	Tests	Status
1. Anomaly Detection	Model loading, accuracy on 8 scenarios	✅
2. Failure Classification	3 failure types, confidence scores	✅
3. Healing Actions	Policy existence, selection, sandbox	✅
4. Dashboard & XAI	Explanations, confidence levels	✅
5. RL Learning	Initialization, Q-updates, rewards	✅
13.3 Output
Test results are saved to tests/test_results/validation_report.json:

json
{
    "timestamp": "2026-05-16T10:00:00",
    "passed": 18,
    "failed": 0,
    "total": 18,
    "all_passed": true,
    "results": [...]
}
13.4 Manual Testing Commands
bash
# Test SSH connection to mock router
python manage.py test_ssh

# Test AI predictions on known scenarios
python manage.py test_ai

# Inject failure and watch auto-healing
python manage.py inject_failure --type service_crash

# Validate RL improvement
python manage.py validate_rl
14. Deployment Guide
14.1 Development Mode (Mock Router)
bash
# Terminal 1: Mock SSH Server
cd simulation
python mock_ssh_server.py

# Terminal 2: Django Server
cd backend
python manage.py runserver

# Terminal 3: Telemetry Collector
cd backend
python manage.py start_collector

# Optional Terminal 4: Orchestrator
cd backend
python manage.py start_orchestrator
14.2 Production Mode (Real Router)
bash
# Step 1: Add your real router
python manage.py add_device \
    --name "ProductionRouter" \
    --ip 192.168.88.1 \
    --type mikrotik_routeros \
    --user admin \
    --pass your_password

# Step 2: Start services
python manage.py start_collector
python manage.py start_orchestrator
python manage.py runserver 0.0.0.0:8000
14.3 Multiple Routers
bash
# Add Cisco router
python manage.py add_device --name CoreSwitch --ip 192.168.1.1 --type cisco_ios --user admin --pass cisco123

# Add MikroTik router
python manage.py add_device --name EdgeRouter --ip 192.168.88.1 --type mikrotik_routeros --user admin --pass neuro1234

# Start collector (monitors all devices)
python manage.py start_collector
14.4 Running as a Service (Linux)
Create systemd service file:

ini
# /etc/systemd/system/neurosynapse.service
[Unit]
Description=NeuroSynapse Self-Healing Network System
After=network.target

[Service]
User=blessings
WorkingDirectory=/home/blessings/NeuroSynapse/backend
ExecStart=/home/blessings/NeuroSynapse/venv/bin/python manage.py start_orchestrator
Restart=always

[Install]
WantedBy=multi-user.target
15. User Manual
15.1 Dashboard Overview
The dashboard is accessible at http://localhost:8000/.

Status Indicators:

🟢 HEALTHY: All metrics within normal ranges

🟠 WARNING: Some metrics elevated

🔴 CRITICAL: Active incident detected

Dashboard Sections:

System Status Bar: Overall network health

Stats Cards: Device count, open incidents, healed count

Device List: Each device with status, CPU, memory, packet loss

Latest Incidents: Recent failures with type and confidence

Healing Actions: Recent automated responses

XAI Panel: Explanations for diagnoses and actions

15.2 Interpreting XAI Explanations
When an incident occurs, the XAI panel explains:

What the AI detected

Why it made that diagnosis

What evidence supports it

What the practical implications are

15.3 Manual Oversight
For low-confidence diagnoses (<70%):

Incident appears in "Manual Review" status

Administrator reviews the XAI explanation

Administrator approves or rejects the healing action

15.4 Healing History
All healing actions are logged with:

Timestamp

Failure type

Action taken

Result (success/failure)

Execution time

16. Troubleshooting
16.1 Common Issues
Django Server Won't Start
text
Error: Port 8000 already in use
Solution:

bash
# Kill existing process or use different port
python manage.py runserver 8001
Mock SSH Server Won't Start
text
Error: Address already in use
Solution:

bash
# Check if port 2222 is in use
netstat -an | findstr 2222
# Kill the process or change port in settings
Models Not Found
text
[AI ENGINE] Models not found
Solution:

bash
cd C:\Users\Blessings\Documents\NeuroSynapse
python training\generate_training_data.py
python training\train_models.py
Module Not Found
text
ModuleNotFoundError: No module named 'netmiko'
Solution:

bash
# Activate virtual environment first
venv\Scripts\activate
pip install netmiko
Database Errors
text
OperationalError: no such table
Solution:

bash
cd backend
python manage.py makemigrations
python manage.py migrate
SSH Connection Failed
text
[SSH] TIMEOUT: 192.168.88.1
Solutions:

Verify the router is powered on and connected

Check IP address is correct

Verify SSH is enabled on the router

Check firewall isn't blocking port 22

Try pinging the router: ping 192.168.88.1

16.2 Logging
Enable detailed logging in settings.py:

python
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'neurosynapse.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'DEBUG',
        },
    },
}
17. Future Enhancements
17.1 Short-Term Improvements
Enhancement	Description
Real-time charting	Add Chart.js for live metric graphs
Email/SMS alerts	Notify admins on critical incidents
Dark/Light theme	UI theme toggle
Export reports	PDF/CSV export of healing history
Docker sandbox	Actual Docker-based command validation
17.2 Medium-Term Improvements
Enhancement	Description
Deep RL	Replace Q-table with neural network
LSTM prediction	Predict failures before they occur
SNMP support	Add SNMPv3 telemetry collection
RESTCONF/NETCONF	Modern API-based device management
Multi-tenancy	Support multiple organizations
17.3 Long-Term Vision
Enhancement	Description
Distributed agents	Edge-based monitoring collectors
Federated learning	Privacy-preserving model training
WAN support	Extend beyond LAN to WAN environments
5G integration	Self-healing for 5G network slices
Autonomous networks	Zero-touch, fully autonomous operations
Appendix A: Quick Reference Card
Start System (Development)
bash
# Terminal 1
cd NeuroSynapse\simulation
python mock_ssh_server.py

# Terminal 2
cd NeuroSynapse\backend
python manage.py runserver

# Terminal 3
cd NeuroSynapse\backend
python manage.py start_collector
Common Commands
bash
python manage.py test_ai              # Test AI predictions
python manage.py test_ssh             # Test SSH connection
python manage.py inject_failure --type service_crash  # Test healing
python manage.py validate_rl          # Validate RL improvement
python tests\test_all_objectives.py   # Run full test suite
Add Router
bash
python manage.py add_device --name NAME --ip IP --type TYPE --user USER --pass PASS
Dashboard
text
http://localhost:8000/
Appendix B: Glossary
Term	Definition
MAPE-K	Monitor-Analyze-Plan-Execute over Knowledge
RL	Reinforcement Learning
ML	Machine Learning
XAI	Explainable Artificial Intelligence
SSH	Secure Shell
ORM	Object-Relational Mapping
Q-Learning	Model-free RL algorithm
Isolation Forest	Unsupervised anomaly detection
Random Forest	Supervised ensemble classifier
Epsilon-Greedy	Exploration-exploitation policy
Sandbox	Isolated environment for safe testing
Appendix C: References
Kephart, J. O., & Chess, D. M. (2003). The vision of autonomic computing. IEEE Computer, 36(1), 41-50.

Chandola, V., Banerjee, A., & Kumar, V. (2009). Anomaly detection: A survey. ACM Computing Surveys.

Zhang, Y., Li, X., & Wang, H. (2020). Reinforcement learning for network self-healing. IEEE ICC.

Sutton, R. S., & Barto, A. G. (2018). Reinforcement Learning: An Introduction. MIT Press.

Boutaba, R., et al. (2018). A comprehensive survey on machine learning for networking. Journal of Internet Services and Applications.

Document Version: 1.0
Last Updated: May 2026
Author: Blessings B Chongo
Supervisor: Dr Ntalasha

END OF DOCUMENTATION