# NeuroSynapse Architecture

## Four logical tiers

1. **Presentation**: Vue/Vuetify dashboard in `frontend/`. It displays telemetry, incidents, XAI explanations, HITL controls, healing history, and downloadable incident logs.
2. **Intelligence**: `backend/ai_engine/` contains ensemble inference, rule-based safety classification, orchestration, XAI, and tabular epsilon-greedy Q-learning.
3. **Data**: Django ORM models in `backend/monitoring/models.py`, SQLite persistence, telemetry snapshots, incidents, healing actions, RL rewards, and policy state.
4. **Execution**: `backend/healing/actuator.py` validates remediation scripts in a network-disabled Docker sandbox before dispatching commands through connectors to simulators, PythonRouter, or FRR.

## MAPE-K flow

```mermaid
flowchart LR
  M[Monitor: scheduler/orchestrator] --> A[Analyze: inference]
  A --> P[Plan: confidence gate + RL]
  P --> S[Sandbox: Docker syntax validation]
  S --> E[Execute: actuator/connectors]
  E --> V[Verify: post-action health]
  V --> K[Knowledge: rewards + policy]
  K --> M
```

## Incident state machine

```mermaid
stateDiagram-v2
  [*] --> MONITORING
  MONITORING --> ANOMALY_DETECTED: anomaly
  ANOMALY_DETECTED --> READY_FOR_ACTION: confidence > 0.70
  ANOMALY_DETECTED --> MANUAL_REVIEW: confidence <= 0.70
  MANUAL_REVIEW --> READY_FOR_ACTION: approve
  MANUAL_REVIEW --> MONITORING: reject
  READY_FOR_ACTION --> SANDBOXING
  SANDBOXING --> EXECUTION: sandbox PASS
  SANDBOXING --> MANUAL_REVIEW: sandbox FAIL
  EXECUTION --> VERIFICATION
  VERIFICATION --> HEALED: health restored
  VERIFICATION --> ROLLBACK: health failed
  HEALED --> MONITORING
  ROLLBACK --> MONITORING
```

The implementation retains the project state names from Figure 3.2 and records healing actions and RL rewards for auditability.
