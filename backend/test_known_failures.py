"""Run known-failure classification checks against the dedicated artifacts."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from ai_engine.model_loader import CANONICAL, model_loader


def vector(**values):
    return {key: values.get(key, 0.0) for key in CANONICAL}


KNOWN_FAILURES = [
    (
        "ddos_high_bw",
        vector(latency_ms=842.3, bandwidth_util=1264.6, error_count=0.48),
        "ddos",
    ),
    (
        "link_failure_low_bw",
        vector(bandwidth_util=1e9, error_count=0.0),
        "link_failure",
    ),
    (
        "service_crash_latency",
        vector(cpu_usage=0.7, memory_usage=2e8, latency_ms=400, bandwidth_util=1e6),
        "service_crash",
    ),
    ("unknown_syslog_issue", vector(), "unknown"),
]


def main():
    print("Scenario                     Expected       Got            Confidence  Pass?")
    passed = True
    for name, features, expected in KNOWN_FAILURES:
        result = model_loader.predict_all(features)
        got = result["fault_type"]
        expected_values = {expected} if expected != "unknown" else {"manual_review", "unknown"}
        ok = got in expected_values
        passed = passed and ok
        print(f"{name:<28} {expected:<14} {got:<14} {result['confidence']:<11.4f} {'YES' if ok else 'NO'}")

    logs_path = BACKEND_DIR / "logs.txt"
    if logs_path.exists():
        text = logs_path.read_text(encoding="utf-8", errors="replace")
        print(f"[INFO] Parsed CBU log: {len(text.splitlines())} lines; unmapped events -> manual_review")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())