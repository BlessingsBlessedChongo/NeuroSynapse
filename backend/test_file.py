import pickle, numpy as np, pandas as pd
from pathlib import Path

MODELS = Path("training/models")
CANONICAL = ["cpu_usage","memory_usage","latency_ms","packet_loss",
             "interface_up_count","bandwidth_util","error_count","ospf_neighbors"]

# Three synthetic scenarios
scenarios = {
    "all_zero_normal":     [0,0,0,0,1,0,0,0],
    "high_bandwidth":      [0,0,50,0,1,1_000_000,0,0],
    "high_error":          [0,0,10,0,1,100,50,0],
    "service_crash_like":  [0.4,1.5e8,300,0,1,5e6,0,0],
}

for name in ["ddos","link_failure","service_crash"]:
    with open(MODELS / f"{name}_classifier.pkl","rb") as f: clf = pickle.load(f)
    with open(MODELS / f"{name}_scaler.pkl","rb") as f: sc  = pickle.load(f)
    print("="*80)
    print(name.upper())
    for label, vec in scenarios.items():
        df = pd.DataFrame([vec], columns=CANONICAL)
        x  = sc.transform(df)
        p  = clf.predict_proba(x)[0].tolist()
        print(f"  {label:22s} -> classes={clf.classes_.tolist()}  proba={[round(v,4) for v in p]}")