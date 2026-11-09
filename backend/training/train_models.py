"""
NeuroSynapse — Train the three RandomForest classifiers
========================================================
Targets : DDoS | Link Failure | Service Crash
Schema  : 8-canonical feature vector per model:
          [cpu_usage, memory_usage, latency_ms, packet_loss,
           interface_up_count, bandwidth_util, error_count, ospf_neighbors]

Outputs (saved to backend/training/models/):
  ddos_classifier.pkl            ddos_scaler.pkl
  link_failure_classifier.pkl    link_failure_scaler.pkl
  service_crash_classifier.pkl   service_crash_scaler.pkl

Read-only with respect to source data. Does NOT touch inference.py.
"""

import os
import sys
import gzip
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (precision_score, recall_score, f1_score,
                             roc_auc_score, confusion_matrix)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).resolve().parent          # backend/training
BACKEND_DIR = BASE_DIR.parent                          # backend
MODELS_DIR  = BASE_DIR / "models"

DDOS_CSV      = BASE_DIR / "cicids2017" / "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv"
BASELINE_GZ   = BACKEND_DIR / "baseline_no_anomaly.csv.gz"
ADMIN_DOWN    = BACKEND_DIR / "admin_down_20180724_45m.csv"
RE2OB_PKL     = BACKEND_DIR / "re2ob_pyg.pkl"

# 8-canonical feature order (must match inference.py)
CANONICAL = [
    "cpu_usage",
    "memory_usage",
    "latency_ms",
    "packet_loss",
    "interface_up_count",
    "bandwidth_util",
    "error_count",
    "ospf_neighbors",
]


def hr(char="=", w=90):
    print(char * w)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_ddos() -> tuple[pd.DataFrame, pd.Series]:
    hr("#"); print("LOAD: DDoS  (CIC-IDS2017 Friday afternoon)")
    hr("#")
    print(f"  file: {DDOS_CSV}")
    df = pd.read_csv(DDOS_CSV, low_memory=False)

    # CIC-IDS2017 headers have leading spaces — strip
    df.columns = [c.strip() for c in df.columns]

    print(f"  raw shape: {df.shape}")
    print(f"  Label value counts:")
    print(df["Label"].value_counts(dropna=False).to_string())

    y = (df["Label"].astype(str).str.strip().str.lower() == "ddos").astype(int)
    print(f"\n  binary label counts: {y.value_counts().to_dict()}")

    # Canonical feature construction
    out = pd.DataFrame(index=df.index)
    out["latency_ms"]        = pd.to_numeric(df["Flow IAT Mean"], errors="coerce") / 1000.0
    out["bandwidth_util"]    = pd.to_numeric(df["Flow Bytes/s"], errors="coerce")
    out["error_count"]       = (pd.to_numeric(df["RST Flag Count"], errors="coerce").fillna(0)
                                + pd.to_numeric(df["SYN Flag Count"], errors="coerce").fillna(0))
    # zero-filled canonical slots
    for c in ["cpu_usage", "memory_usage", "packet_loss",
              "interface_up_count", "ospf_neighbors"]:
        out[c] = 0.0

    # Replace inf/-inf/NaN with median
    out = out.replace([np.inf, -np.inf], np.nan)
    for c in out.columns:
        if out[c].isna().any():
            med = out[c].median()
            if pd.isna(med):
                med = 0.0
            out[c] = out[c].fillna(med)

    # Reorder to canonical order
    out = out[CANONICAL]
    print(f"  final feature shape: {out.shape}")
    print(f"  feature dtypes:\n{out.dtypes.to_string()}")
    return out, y


def _load_cisco_generic(path: Path, label: int) -> pd.DataFrame:
    """Load a Cisco telemetry file, keep only generic-counters rows,
    convert counters to per-interval deltas per (Producer, interface-name)."""
    print(f"  reading: {path}")
    df = pd.read_csv(path,
                     compression="gzip" if str(path).endswith(".gz") else None,
                     low_memory=False)
    df = df[df["name"].astype(str).str.contains("generic-counters", na=False)].copy()
    print(f"    generic-counters rows: {len(df):,}")

    keep = ["time", "Producer", "interface-name",
            "bytes-received", "bytes-sent", "crc-errors",
            "input-errors", "carrier-transitions"]
    missing = [c for c in keep if c not in df.columns]
    if missing:
        raise RuntimeError(f"missing required columns in {path.name}: {missing}")
    df = df[keep].copy()

    for c in ["time", "bytes-received", "bytes-sent", "crc-errors",
              "input-errors", "carrier-transitions"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["Producer"]       = df["Producer"].astype(str)
    df["interface-name"] = df["interface-name"].astype(str)

    df = df.sort_values(["Producer", "interface-name", "time"]).reset_index(drop=True)

    grp = df.groupby(["Producer", "interface-name"], sort=False)
    df["bytes-received-d"]      = grp["bytes-received"].diff()
    df["bytes-sent-d"]          = grp["bytes-sent"].diff()
    df["crc-errors-d"]          = grp["crc-errors"].diff()
    df["input-errors-d"]        = grp["input-errors"].diff()
    df["carrier-transitions-d"] = grp["carrier-transitions"].diff()

    # Drop first row of each group (NaN diffs)
    df = df.dropna(subset=["bytes-received-d", "crc-errors-d"]).copy()

    # Clip negative deltas (counter wraps) to 0
    for c in ["bytes-received-d", "bytes-sent-d", "crc-errors-d",
              "input-errors-d", "carrier-transitions-d"]:
        df[c] = df[c].clip(lower=0)

    out = pd.DataFrame(index=df.index)
    out["bandwidth_util"] = df["bytes-received-d"] + df["bytes-sent-d"]
    out["error_count"]    = (df["crc-errors-d"]
                             + df["input-errors-d"]
                             + df["carrier-transitions-d"])
    for c in ["cpu_usage", "memory_usage", "latency_ms", "packet_loss",
              "interface_up_count", "ospf_neighbors"]:
        out[c] = 0.0
    out = out[CANONICAL]
    out["__label__"] = label
    return out


def load_link_failure() -> tuple[pd.DataFrame, pd.Series]:
    hr("#"); print("LOAD: Link Failure  (Cisco XR generic-counters)")
    hr("#")
    neg = _load_cisco_generic(BASELINE_GZ, label=0)
    pos = _load_cisco_generic(ADMIN_DOWN,  label=1)
    print(f"    baseline (label=0) rows : {len(neg):,}")
    print(f"    admin_down (label=1) rows: {len(pos):,}")

    combined = pd.concat([neg, pos], ignore_index=True)
    combined = combined.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y = combined.pop("__label__").astype(int)
    print(f"  combined shape: {combined.shape}")
    print(f"  label distribution: {y.value_counts().to_dict()}")
    return combined, y


def load_service_crash() -> tuple[pd.DataFrame, pd.Series]:
    hr("#"); print("LOAD: Service Crash  (re2ob_pyg.pkl)")
    hr("#")
    with open(RE2OB_PKL, "rb") as f:
        obj = pickle.load(f)
    exps = obj["experiments"]
    print(f"  experiments: {len(exps)}")

    rows = []
    labels = []
    for e in exps:
        inject = float(e["inject_time_relative"])
        svc_frames = e["ts_features"]   # dict: service -> DataFrame
        # All services share the same 'time' column; use one to index
        any_svc = next(iter(svc_frames))
        times = svc_frames[any_svc]["time"].to_numpy()

        # Aggregate each metric across services at each timestep
        cpu_stack  = np.stack([svc_frames[s]["container_cpu_user_seconds_total"].to_numpy()
                               + svc_frames[s]["container_cpu_system_seconds_total"].to_numpy()
                               for s in svc_frames], axis=0)
        mem_stack  = np.stack([svc_frames[s]["container_memory_usage_bytes"].to_numpy()
                               for s in svc_frames], axis=0)
        lat_stack  = np.stack([svc_frames[s]["istio_latency_99"].to_numpy()
                               for s in svc_frames], axis=0)
        bw_stack   = np.stack([svc_frames[s]["container_network_receive_bytes_total"].to_numpy()
                               + svc_frames[s]["container_network_transmit_bytes_total"].to_numpy()
                               for s in svc_frames], axis=0)

        cpu = cpu_stack.mean(axis=0)
        mem = mem_stack.mean(axis=0)
        lat = lat_stack.mean(axis=0)
        bw  = bw_stack.mean(axis=0)

        for i, t in enumerate(times):
            rows.append({
                "cpu_usage":        float(cpu[i]),
                "memory_usage":     float(mem[i]),
                "latency_ms":       float(lat[i]) * 1000.0,   # seconds -> ms
                "bandwidth_util":   float(bw[i]),
                "packet_loss":      0.0,
                "interface_up_count": 1.0,
                "error_count":      0.0,
                "ospf_neighbors":   0.0,
            })
            labels.append(1 if t >= inject else 0)

    out = pd.DataFrame(rows)[CANONICAL]
    y = pd.Series(labels, name="label").astype(int)
    print(f"  final feature shape: {out.shape}")
    print(f"  label distribution: {y.value_counts().to_dict()}")
    return out, y


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train_one(name: str, X: pd.DataFrame, y: pd.Series):
    hr("="); print(f"TRAIN: {name}"); hr("=")
    print(f"  input shape           : {X.shape}")
    print(f"  class distribution    : {y.value_counts().to_dict()}")

    # Deduplicate — but keep label aligned
    combined = X.copy(); combined["__y__"] = y.values
    before = len(combined)
    combined = combined.drop_duplicates()
    after = len(combined)
    print(f"  rows before dedup     : {before:,}")
    print(f"  rows after  dedup     : {after:,}  (removed {before - after:,})")

    y = combined.pop("__y__").astype(int)
    X = combined

    # Ensure no NaN / inf
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42)
    print(f"  train / test          : {len(X_tr):,} / {len(X_te):,}")

    scaler = StandardScaler().fit(X_tr)
    X_tr_s = scaler.transform(X_tr)
    X_te_s = scaler.transform(X_te)

    clf = RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_tr_s, y_tr)

    y_pred = clf.predict(X_te_s)
    y_prob = clf.predict_proba(X_te_s)[:, 1]

    p  = precision_score(y_te, y_pred, zero_division=0)
    r  = recall_score(y_te, y_pred, zero_division=0)
    f1 = f1_score(y_te, y_pred, zero_division=0)
    try:
        auc = roc_auc_score(y_te, y_prob)
    except ValueError:
        auc = float("nan")
    cm = confusion_matrix(y_te, y_pred)

    print()
    print(f"  precision : {p:.4f}")
    print(f"  recall    : {r:.4f}")
    print(f"  f1        : {f1:.4f}")
    print(f"  roc_auc   : {auc:.4f}")
    print(f"  confusion matrix (rows=true, cols=pred):")
    print(f"    {cm.tolist()}")

    print()
    print("  feature importances:")
    for f_name, imp in sorted(zip(CANONICAL, clf.feature_importances_),
                              key=lambda t: -t[1]):
        print(f"    {f_name:20s}: {imp:.4f}")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    clf_path    = MODELS_DIR / f"{name}_classifier.pkl"
    scaler_path = MODELS_DIR / f"{name}_scaler.pkl"
    with open(clf_path, "wb") as f:
        pickle.dump(clf, f)
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    print()
    print(f"  saved: {clf_path}")
    print(f"  saved: {scaler_path}")
    print()


# ---------------------------------------------------------------------------
# Sanity check — reload saved artifacts
# ---------------------------------------------------------------------------
def sanity_check():
    hr("="); print("SANITY CHECK — reload saved artifacts"); hr("=")
    dummy = np.ones((1, 8), dtype=float)
    for name in ["ddos", "link_failure", "service_crash"]:
        clf_p    = MODELS_DIR / f"{name}_classifier.pkl"
        scaler_p = MODELS_DIR / f"{name}_scaler.pkl"
        if not clf_p.exists() or not scaler_p.exists():
            print(f"  [SKIP] {name}: artifact missing")
            continue
        with open(clf_p, "rb") as f: clf = pickle.load(f)
        with open(scaler_p, "rb") as f: sc = pickle.load(f)
        d = sc.transform(dummy)
        prob = clf.predict_proba(d)[0]
        print(f"  {name:15s} dummy-ones prediction: classes={clf.classes_.tolist()}  proba={prob.tolist()}")
    print()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    hr()
    print("NeuroSynapse — Training Run")
    print(f"models will be saved to: {MODELS_DIR}")
    hr()
    print()

    # 1) DDoS
    X, y = load_ddos()
    train_one("ddos", X, y)

    # 2) Link Failure
    X, y = load_link_failure()
    train_one("link_failure", X, y)

    # 3) Service Crash
    X, y = load_service_crash()
    train_one("service_crash", X, y)

    # 4) Sanity
    sanity_check()
    return 0


if __name__ == "__main__":
    sys.exit(main())