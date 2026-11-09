"""
ML Inference Engine for NeuroSynapse.

MAPE-K ANALYZE phase.

Uses:
    1. Rule-based detection for deterministic network failures.
    2. Ensemble ML: Isolation Forest + Local Outlier Factor with weighted voting.
    3. Random Forest for failure classification.

ENSEMBLE VOTING (per spec Section 4.4.3.1):
    IF (0.6 * pred_a + 0.4 * pred_b) > THRESHOLD:
        RETURN "Anomaly Detected"
    ELSE:
        RETURN "Normal"
"""

import os
import logging
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

from monitoring.connector import (
    TELEMETRY_FEATURE_ORDER,
    normalize_telemetry,
    telemetry_to_feature_vector,
)

DEFAULT_FEATURE_COLUMNS = list(TELEMETRY_FEATURE_ORDER)
logger = logging.getLogger('neurosynapse.ai.inference')


class InferenceEngine:
    """
    NeuroSynapse ML inference engine with weighted ensemble voting.
    """

    # Deterministic anomaly thresholds (safety layer)
    CPU_THRESHOLD = 80.0
    MEMORY_THRESHOLD = 90.0
    PACKET_LOSS_THRESHOLD = 10.0
    LATENCY_THRESHOLD = 100.0
    BANDWIDTH_THRESHOLD = 90.0
    ERROR_COUNT_THRESHOLD = 10
    OSPF_NEIGHBOR_MINIMUM = 1

    RULE_BASED_CONFIDENCE = 0.90

    # Ensemble weights as specified in Section 4.4.3.1
    ISOLATION_FOREST_WEIGHT = 0.6
    LOF_WEIGHT = 0.4
    ENSEMBLE_THRESHOLD = 0.5

    def __init__(self):
        # ML models
        self.isolation_forest = None
        self.local_outlier_factor = None
        self.failure_classifier = None
        self.scaler = StandardScaler()

        self.feature_columns = DEFAULT_FEATURE_COLUMNS.copy()
        self.metadata = None
        self.loaded = False

        self._load_models()

    def _get_models_path(self):
        backend_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        project_root = os.path.dirname(backend_dir)

        candidate_paths = [
            os.path.join(project_root, "models"),
            os.path.join(backend_dir, "models"),
            os.path.join(backend_dir, "training", "models"),
        ]

        for path in candidate_paths:
            files_exist = all([
                os.path.exists(os.path.join(path, "isolation_forest.pkl")),
                os.path.exists(os.path.join(path, "local_outlier_factor.pkl")),
                os.path.exists(os.path.join(path, "failure_classifier.pkl")),
                os.path.exists(os.path.join(path, "scaler.pkl")),
                os.path.exists(os.path.join(path, "feature_columns.pkl")),
            ])
            if files_exist:
                return path

        return os.path.join(project_root, "models")

    def _load_models(self):
        models_path = self._get_models_path()

        try:
            self.isolation_forest = joblib.load(
                os.path.join(models_path, "isolation_forest.pkl")
            )
            self.local_outlier_factor = joblib.load(
                os.path.join(models_path, "local_outlier_factor.pkl")
            )
            self.failure_classifier = joblib.load(
                os.path.join(models_path, "failure_classifier.pkl")
            )
            self.scaler = joblib.load(
                os.path.join(models_path, "scaler.pkl")
            )
            loaded_columns = joblib.load(
                os.path.join(models_path, "feature_columns.pkl")
            )

            if loaded_columns:
                self.feature_columns = list(loaded_columns)

            metadata_path = os.path.join(models_path, "model_metadata.pkl")
            if os.path.exists(metadata_path):
                self.metadata = joblib.load(metadata_path)

            self.loaded = True
            logger.info("[AI ENGINE] Ensemble models loaded successfully")
            logger.info("[AI ENGINE] Feature order: %s", self.feature_columns)
            logger.info("[AI ENGINE] IF weight: %s", self.ISOLATION_FOREST_WEIGHT)
            logger.info("[AI ENGINE] LOF weight: %s", self.LOF_WEIGHT)
            logger.info("[AI ENGINE] Threshold: %s", self.ENSEMBLE_THRESHOLD)

        except Exception as exc:
            self.loaded = False
            logger.exception("[AI ENGINE] Models not found: %s", exc)
            logger.error("[AI ENGINE] Run training script first")

    def extract_features(self, telemetry):
        """Convert telemetry into a one-row feature matrix."""
        normalized = normalize_telemetry(telemetry)

        if normalized is None:
            ordered = [0.0 for _ in self.feature_columns]
        else:
            ordered = []
            for column in self.feature_columns:
                value = normalized.get(column, 0.0)
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    value = 0.0
                ordered.append(value)

        return np.asarray([ordered], dtype=float)

    # =========================================================
    # RULE-BASED DETECTION (Safety Layer)
    # =========================================================

    def _rule_based_detection(self, normalized):
        """Deterministic network-failure detection."""
        if not normalized:
            return False, 0.0, []

        cpu = float(normalized.get("cpu_usage", 0.0))
        memory = float(normalized.get("memory_usage", 0.0))
        packet_loss = float(normalized.get("packet_loss", 0.0))
        latency = float(normalized.get("latency_ms", 0.0))
        bandwidth = float(normalized.get("bandwidth_util", 0.0))

        ospf_neighbors = int(normalized.get("ospf_neighbors", 0))
        error_count = int(normalized.get("error_count", 0))

        reasons = []

        if cpu > self.CPU_THRESHOLD:
            reasons.append(f"CPU {cpu:.1f}% > {self.CPU_THRESHOLD:.1f}%")
        if memory > self.MEMORY_THRESHOLD:
            reasons.append(f"Memory {memory:.1f}% > {self.MEMORY_THRESHOLD:.1f}%")
        if packet_loss > self.PACKET_LOSS_THRESHOLD:
            reasons.append(f"Packet loss {packet_loss:.1f}% > {self.PACKET_LOSS_THRESHOLD:.1f}%")
        if latency > self.LATENCY_THRESHOLD:
            reasons.append(f"Latency {latency:.1f}ms > {self.LATENCY_THRESHOLD:.1f}ms")
        if bandwidth > self.BANDWIDTH_THRESHOLD:
            reasons.append(f"Bandwidth {bandwidth:.1f}% > {self.BANDWIDTH_THRESHOLD:.1f}%")
        if error_count > self.ERROR_COUNT_THRESHOLD:
            reasons.append(f"Errors {error_count} > {self.ERROR_COUNT_THRESHOLD}")
        if ospf_neighbors < self.OSPF_NEIGHBOR_MINIMUM:
            reasons.append(f"OSPF neighbors {ospf_neighbors} < {self.OSPF_NEIGHBOR_MINIMUM}")

        # Interface down detection
        interface_status = normalized.get("interface_status", {})
        if isinstance(interface_status, dict):
            down_interfaces = [
                name for name, details in interface_status.items()
                if name != "lo" and isinstance(details, dict) and details.get("status") == "down"
            ]
            if down_interfaces:
                reasons.append(f"Interfaces down: {', '.join(down_interfaces)}")

        is_anomaly = bool(reasons)
        if not is_anomaly:
            return False, 0.0, []

        reason_count = len(reasons)
        confidence = min(
            1.0,
            self.RULE_BASED_CONFIDENCE + ((reason_count - 1) * 0.02),
        )

        return True, confidence, reasons

    def _rule_based_classify(self, normalized):
        """
        Deterministic failure typing when ML confidence is low / domain-shifted.

        Signatures mirror the simulator / PythonRouter failure metrics and the
        synthetic labels used in Objective 1 tests.
        """
        if not normalized:
            return None, 0.0

        cpu = float(normalized.get("cpu_usage", 0.0))
        memory = float(normalized.get("memory_usage", 0.0))
        packet_loss = float(normalized.get("packet_loss", 0.0))
        latency = float(normalized.get("latency_ms", 0.0))
        bandwidth = float(normalized.get("bandwidth_util", 0.0))

        # Resolve the most specific signatures first. DDoS and service
        # crashes can also produce loss/latency, so LINK_FAILURE must not
        # claim them merely because loss is elevated.
        if cpu >= 90.0 and bandwidth >= 80.0:
            return "DDOS_ATTACK", 0.92

        if cpu >= 85.0 and memory >= 70.0 and packet_loss < 25.0 and bandwidth < 85.0:
            return "SERVICE_CRASH", 0.91

        interface_status = normalized.get("interface_status", {}) or {}
        down_interfaces = [
            name for name, details in interface_status.items()
            if name not in ("lo",) and isinstance(details, dict)
            and not str(name).startswith("__")
            and details.get("status") == "down"
        ]

        # LINK_FAILURE: severe loss / latency with relatively normal CPU,
        # or an explicitly down data interface.
        if down_interfaces or (packet_loss >= 50.0 and cpu < 70.0) or (
            latency >= 250.0 and packet_loss >= 40.0 and cpu < 70.0
        ):
            return "LINK_FAILURE", 0.93

        raw_output = normalized.get("raw_output", {})
        if isinstance(raw_output, dict):
            service_output = str(raw_output.get("service", "")).upper()
            if service_output.strip() == "FRR_DOWN":
                return "SERVICE_CRASH", 0.97

        return None, 0.0

    # =========================================================
    # ENSEMBLE ML DETECTION (as per Section 4.4.3.1)
    # =========================================================

    def _ensemble_detection(self, features):
        """
        Weighted ensemble voting as specified in the design doc.

        IF (0.6 * pred_a + 0.4 * pred_b) > THRESHOLD:
            RETURN "Anomaly Detected"
        """
        if not self.loaded or self.isolation_forest is None or self.local_outlier_factor is None:
            return False, 0.0

        try:
            # Scale features
            X_scaled = self.scaler.transform(features)

            # Get predictions: -1 for anomaly, 1 for normal
            if_pred = self.isolation_forest.predict(X_scaled)[0]
            lof_pred = self.local_outlier_factor.predict(X_scaled)[0]

            # Convert to binary: 1 = anomaly, 0 = normal
            if_binary = 1 if if_pred == -1 else 0
            lof_binary = 1 if lof_pred == -1 else 0

            # Weighted voting as per specification
            # IF (0.6 * pred_a + 0.4 * pred_b) > THRESHOLD
            weighted_score = (
                self.ISOLATION_FOREST_WEIGHT * if_binary +
                self.LOF_WEIGHT * lof_binary
            )

            is_anomaly = weighted_score > self.ENSEMBLE_THRESHOLD

            # Confidence is the weighted score (closer to 1 = more confident)
            confidence = float(weighted_score)

            return is_anomaly, confidence

        except Exception as exc:
            logger.exception("[AI ENGINE] Ensemble detection error: %s", exc)
            return False, 0.0

    # =========================================================
    # ANOMALY DETECTION (HYBRID: Rules + Ensemble)
    # =========================================================

    def detect_anomaly(self, telemetry):
        """Combines Rule-Based and Ensemble ML detection."""
        normalized = normalize_telemetry(telemetry)
        if not normalized:
            return False, 0.0

        # 1. Deterministic Rule-Based Check (Safety Layer)
        rule_anomaly, rule_conf, _ = self._rule_based_detection(normalized)
        if rule_anomaly:
            return True, rule_conf

        # 2. Ensemble ML Check (Isolation Forest + LOF with weighted voting)
        if self.loaded:
            features = self.extract_features(normalized)
            ensemble_anomaly, ensemble_conf = self._ensemble_detection(features)
            if ensemble_anomaly:
                return True, ensemble_conf

        return False, 0.0

    # =========================================================
    # FAILURE CLASSIFICATION
    # =========================================================

    def classify_failure(self, telemetry):
        if self.failure_classifier is None or not self.loaded:
            return "UNKNOWN", 0.0

        try:
            features = self.extract_features(telemetry)
            X_scaled = self.scaler.transform(features)
            predicted_class = self.failure_classifier.predict(X_scaled)[0]
            confidence = 0.0

            if hasattr(self.failure_classifier, "predict_proba"):
                probabilities = self.failure_classifier.predict_proba(X_scaled)[0]
                confidence = float(np.max(probabilities))

            failure_type = str(predicted_class)

            if failure_type.upper() == "NORMAL":
                return "NORMAL", confidence

            return failure_type, confidence

        except Exception as exc:
            logger.exception("[AI ENGINE] Classification error: %s", exc)
            return "UNKNOWN", 0.0

    # =========================================================
    # DIAGNOSIS
    # =========================================================

    def diagnose(self, telemetry):
        """Complete ANALYZE phase."""
        normalized = normalize_telemetry(telemetry)
        feature_vector = telemetry_to_feature_vector(normalized)

        is_anomaly, anomaly_confidence = self.detect_anomaly(normalized)

        result = {
            "is_anomaly": bool(is_anomaly),
            "anomaly_confidence": round(float(anomaly_confidence), 4),
            "failure_type": "NORMAL" if not is_anomaly else "UNKNOWN",
            "classification_confidence": 0.0,
            "feature_vector": feature_vector,
        }

        if is_anomaly:
            failure_type, class_conf = self.classify_failure(normalized)
            rule_type, rule_conf = self._rule_based_classify(normalized)

            # Prefer deterministic typing when ML is uncertain or disagrees
            # with a clear signature (common with cross-dataset / simulator
            # domain shift from CICIDS/UNSW-trained models).
            if rule_type:
                if (
                    class_conf < 0.70
                    or failure_type in ("UNKNOWN", "NORMAL", "")
                    or (failure_type != rule_type and rule_conf >= class_conf)
                ):
                    failure_type = rule_type
                    class_conf = max(float(class_conf), float(rule_conf))

            result["failure_type"] = failure_type
            result["classification_confidence"] = round(float(class_conf), 4)

        logger.info(
            f"[AI ENGINE] Diagnosis: "
            f"anomaly={result['is_anomaly']} "
            f"type={result['failure_type']} "
            f"anomaly_conf={result['anomaly_confidence']:.2%} "
            f"class_conf={result['classification_confidence']:.2%}"
        )

        return result


engine = InferenceEngine()