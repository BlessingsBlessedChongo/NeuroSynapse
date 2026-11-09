"""Load and run the dedicated SDS classifiers without feature-name warnings."""

from pathlib import Path
from typing import Dict, Tuple

import joblib
import pandas as pd


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

BACKEND_DIR = Path(__file__).resolve().parents[1]
MODEL_DIRS = (BACKEND_DIR / "models", BACKEND_DIR / "training" / "models")
MODEL_NAMES = ("ddos", "link_failure", "service_crash")


class DedicatedModelLoader:
    def __init__(self):
        self.models: Dict[str, object] = {}
        self.scalers: Dict[str, object] = {}
        self.medians: Dict[str, list] = {}
        self.errors = []
        self._load()

    def _find(self, filename):
        for directory in MODEL_DIRS:
            path = directory / filename
            if path.exists():
                return path
        return None

    def _load(self):
        for name in MODEL_NAMES:
            classifier_path = self._find(f"{name}_classifier.pkl")
            scaler_path = self._find(f"{name}_scaler.pkl")
            if not classifier_path or not scaler_path:
                self.errors.append(f"missing {name} classifier or scaler")
                continue
            try:
                self.models[name] = joblib.load(classifier_path)
                self.scalers[name] = joblib.load(scaler_path)
                median_path = self._find(f"{name}_median.pkl")
                median = joblib.load(median_path) if median_path else None
                if median is None:
                    median = getattr(self.scalers[name], "mean_", [0.0] * len(CANONICAL))
                self.medians[name] = list(median)
            except Exception as exc:
                self.errors.append(f"{name}: {exc}")

    def _frame(self, name: str, vector: dict) -> pd.DataFrame:
        median = self.medians.get(name, [0.0] * len(CANONICAL))
        values = []
        for index, key in enumerate(CANONICAL):
            value = vector.get(key)
            values.append(median[index] if value is None else value)
        return pd.DataFrame([values], columns=CANONICAL)

    def predict(self, name: str, vector: dict) -> Tuple[int, float]:
        frame = self._frame(name, vector)
        scaled = self.scalers[name].transform(frame)
        label = int(self.models[name].predict(scaled)[0])
        probabilities = self.models[name].predict_proba(scaled)[0]
        return label, float(max(probabilities))

    def predict_ddos(self, vector):
        return self.predict("ddos", vector)

    def predict_link_failure(self, vector):
        return self.predict("link_failure", vector)

    def predict_service_crash(self, vector):
        return self.predict("service_crash", vector)

    def predict_all(self, vector):
        """Combine binary model outputs into a fault type or manual review."""
        predictions = {
            "ddos": self.predict_ddos(vector),
            "link_failure": self.predict_link_failure(vector),
            "service_crash": self.predict_service_crash(vector),
        }
        positive = {
            name: confidence
            for name, (label, confidence) in predictions.items()
            if label == 1
        }
        if not positive:
            normal_confidence = max(
                1.0 - confidence for _, confidence in predictions.values()
            )
            return {
                "fault_type": "manual_review",
                "confidence": round(normal_confidence, 4),
                "model_used": "dedicated_binary_classifiers",
                "features": vector,
            }
        fault_type, confidence = max(positive.items(), key=lambda item: item[1])
        if confidence < 0.70:
            fault_type = "manual_review"
        return {
            "fault_type": fault_type,
            "confidence": round(confidence, 4),
            "model_used": "dedicated_binary_classifiers",
            "features": vector,
        }

    def models_healthy(self) -> bool:
        if len(self.models) != len(MODEL_NAMES):
            return False
        try:
            vector = {key: 0.0 for key in CANONICAL}
            for name in MODEL_NAMES:
                self.predict(name, vector)
            return True
        except Exception:
            return False


model_loader = DedicatedModelLoader()


def models_healthy() -> bool:
    return model_loader.models_healthy()


def predict_ddos(vector):
    return model_loader.predict_ddos(vector)


def predict_link_failure(vector):
    return model_loader.predict_link_failure(vector)


def predict_service_crash(vector):
    return model_loader.predict_service_crash(vector)


def predict_all(vector):
    return model_loader.predict_all(vector)