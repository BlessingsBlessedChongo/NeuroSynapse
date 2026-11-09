"""
NeuroSynapse Dataset Inspection Script  (v2)
--------------------------------------------
Purpose: Verify that raw data files exist, are readable, and contain the
         expected columns. Read-only. Prints to console only. Writes nothing.

Covers:
  - DDoS          : CIC-IDS2017 (Friday-DDos, Monday-benign) + UNSW-NB15
  - Link Failure  : Cisco telemetry (baseline / port-flap / admin-down)
  - Service Crash : re2ob_pyg.pkl

Usage:
    cd backend/training
    python inspect_datasets.py
"""

import os
import sys
import gzip
import pickle
from pathlib import Path

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR      = Path(__file__).resolve().parent      # backend/training
BACKEND_DIR   = BASE_DIR.parent                      # backend
DATASETS_DIR  = BASE_DIR / "datasets"

CIC_DIR       = BASE_DIR / "cicids2017"
UNSW_DIR      = BASE_DIR / "unsw_nb15"
CISCO_FILES   = {
    "baseline":   BACKEND_DIR / "baseline_no_anomaly.csv.gz",
    "portflap":   BACKEND_DIR / "portflaptypes.csv.gz",
    "admin_down": BACKEND_DIR / "admin_down_20180724_45m.csv",
}
RE2OB_PKL     = BACKEND_DIR / "re2ob_pyg.pkl"

CIC_FILES = {
    "Friday-DDoS":  CIC_DIR / "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
    "Monday":       CIC_DIR / "Monday-WorkingHours.pcap_ISCX.csv",
}
UNSW_FILES = {
    "train": UNSW_DIR / "UNSW_NB15_training-set.csv",
    "test":  UNSW_DIR / "UNSW_NB15_testing-set.csv",
}


def hr(char="=", width=100):
    print(char * width)


def exists(path: Path, label: str = "") -> bool:
    if not path.exists():
        print(f"  [FAIL] MISSING: {path}")
        return False
    print(f"  [OK]  found: {path}  ({path.stat().st_size:,} bytes)")
    return True


# ---------------------------------------------------------------------------
# 1) DDoS — CIC-IDS2017
# ---------------------------------------------------------------------------
def inspect_cic():
    hr("#")
    print("GROUP: DDoS — CIC-IDS2017")
    hr("#")
    for label, path in CIC_FILES.items():
        hr("-")
        print(f"FILE [{label}]: {path}")
        hr("-")
        if not exists(path):
            continue
        try:
            # Only read what we need for the schema
            df = pd.read_csv(path, nrows=5, low_memory=False)
            print(f"  columns ({len(df.columns)}):")
            for c in df.columns:
                print(f"    - {c}")
            # Look for the label column
            label_cols = [c for c in df.columns if "label" in c.lower()]
            print(f"  label-candidate columns: {label_cols}")
            if label_cols:
                # Full value counts for label column (small memory)
                full = pd.read_csv(path, usecols=label_cols, low_memory=False)
                for lc in label_cols:
                    print(f"  value_counts[{lc}]:")
                    print(full[lc].value_counts(dropna=False).to_string())
            print("  first 3 rows (transposed for readability):")
            print(df.head(3).T.to_string())
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 2) DDoS — UNSW-NB15
# ---------------------------------------------------------------------------
def inspect_unsw():
    hr("#")
    print("GROUP: DDoS — UNSW-NB15")
    hr("#")
    for label, path in UNSW_FILES.items():
        hr("-")
        print(f"FILE [{label}]: {path}")
        hr("-")
        if not exists(path):
            continue
        try:
            df = pd.read_csv(path, nrows=5, low_memory=False)
            print(f"  columns ({len(df.columns)}):")
            for c in df.columns:
                print(f"    - {c}")
            # attack_cat and label
            for col in ["attack_cat", "label"]:
                if col in df.columns:
                    full = pd.read_csv(path, usecols=[col], low_memory=False)
                    print(f"  value_counts[{col}]:")
                    print(full[col].value_counts(dropna=False).to_string())
            print("  first 3 rows (transposed):")
            print(df.head(3).T.to_string())
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 3) Link Failure — Cisco telemetry
# ---------------------------------------------------------------------------
def inspect_cisco():
    hr("#")
    print("GROUP: Link Failure — Cisco telemetry")
    hr("#")
    for tag, path in CISCO_FILES.items():
        hr("-")
        print(f"FILE [{tag}]: {path}")
        hr("-")
        if not exists(path):
            continue
        try:
            opener = gzip.open if str(path).endswith(".gz") else open
            # Read a sample of 200k rows
            df = pd.read_csv(path,
                             compression="gzip" if str(path).endswith(".gz") else None,
                             nrows=200_000, low_memory=False)
            print(f"  sampled rows: {len(df):,}   columns: {len(df.columns)}")

            # Filter to interface-sensor rows
            if "name" in df.columns:
                iface_mask = df["name"].astype(str).str.contains(
                    "infra-statistics/interfaces", na=False)
                n_iface = int(iface_mask.sum())
                print(f"  interface-sensor rows in sample: {n_iface:,} "
                      f"({100*n_iface/len(df):.1f}%)")
                iface_df = df[iface_mask]
                print(f"  interface-sensor unique names:")
                for v in iface_df["name"].unique()[:10]:
                    print(f"    - {v}")
            else:
                iface_df = df

            # Value counts for the interface-state columns
            for col in ["actual-line-state", "actual-state", "state",
                        "line-state", "interface-name", "interface"]:
                if col in iface_df.columns:
                    vc = iface_df[col].value_counts(dropna=False).head(10)
                    print(f"  value_counts[{col}] (top 10):")
                    print(vc.to_string())

            # Time range
            if "time" in iface_df.columns:
                t = pd.to_numeric(iface_df["time"], errors="coerce").dropna()
                if len(t):
                    t_min = pd.to_datetime(t.min(), unit="ns", errors="coerce")
                    t_max = pd.to_datetime(t.max(), unit="ns", errors="coerce")
                    print(f"  time range (sample): {t_min}  ->  {t_max}")

            # Null counts on the interface rows for interesting columns
            interesting = ["bandwidth","bytes-received","bytes-sent",
                           "carrier-transitions","checksum-error-packets",
                           "crc-errors","discard-packets","input-errors",
                           "output-errors","input-drops","output-drops",
                           "input-queue-drops","output-queue-drops",
                           "input-packet-rate","output-packet-rate",
                           "input-data-rate","output-data-rate",
                           "packets-received","packets-sent"]
            present = [c for c in interesting if c in iface_df.columns]
            if present:
                print(f"  null counts on interface rows (interesting cols):")
                nn = iface_df[present].isna().sum()
                print(nn.to_string())

            print("  first 2 interface rows (transposed, truncated):")
            if len(iface_df):
                print(iface_df.head(2).T.head(40).to_string())
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 4) Service Crash — re2ob_pyg.pkl
# ---------------------------------------------------------------------------
def inspect_re2ob():
    hr("#")
    print("GROUP: Service Crash — re2ob_pyg.pkl")
    hr("#")
    if not exists(RE2OB_PKL):
        return
    try:
        with open(RE2OB_PKL, "rb") as f:
            obj = pickle.load(f)
        print(f"  type: {type(obj)}")
        if isinstance(obj, dict):
            print(f"  top-level keys: {list(obj.keys())}")
            if "metadata" in obj:
                md = obj["metadata"]
                print(f"  metadata keys: {list(md.keys()) if isinstance(md, dict) else type(md)}")
                if isinstance(md, dict):
                    for k, v in md.items():
                        if k == "service_p99":
                            print(f"    service_p99: {len(v)} services")
                            for s in list(v.keys())[:3]:
                                print(f"      - {s}: {list(v[s].keys())[:5]}...")
                        else:
                            print(f"    {k}: {v}")
            exps = obj.get("experiments", [])
            print(f"  num experiments: {len(exps)}")
            if exps:
                e0 = exps[0]
                print(f"  first experiment keys: {list(e0.keys())}")
                print(f"  root_cause values (unique):")
                print(pd.Series([e["root_cause"] for e in exps])
                      .value_counts().to_string())
                print(f"  inject_time_relative values (unique):")
                print(pd.Series([e["inject_time_relative"] for e in exps])
                      .value_counts().to_string())
                if "ts_features" in e0:
                    svcs = list(e0["ts_features"].keys())
                    print(f"  services ({len(svcs)}): {svcs}")
                    svc0 = svcs[0]
                    df0 = e0["ts_features"][svc0]
                    print(f"  sample service '{svc0}' shape: {df0.shape}")
                    print(f"  sample service columns: {list(df0.columns)}")
                    print(f"  sample service head(2):")
                    print(df0.head(2).to_string())
                for k in ["normal_features", "anomaly_features"]:
                    if k in e0:
                        v = e0[k]
                        print(f"  {k}: type={type(v)}"
                              + (f", shape={v.shape}" if hasattr(v, "shape") else ""))
                for k in ["normal_pyg", "anomaly_pyg"]:
                    if k in e0:
                        v = e0[k]
                        print(f"  {k}: type={type(v)}")
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    hr()
    print("NeuroSynapse Dataset Inspection Report (v2)")
    hr()
    print(f"BASE_DIR      : {BASE_DIR}")
    print(f"BACKEND_DIR   : {BACKEND_DIR}")
    print(f"DATASETS_DIR  : {DATASETS_DIR}")
    print()

    inspect_cic()
    print()
    inspect_unsw()
    print()
    inspect_cisco()
    print()
    inspect_re2ob()

    hr()
    print("[INFO] Inspection complete.")
    hr()
    return 0


if __name__ == "__main__":
    sys.exit(main())