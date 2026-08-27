"""
ML Inference Engine for NeuroSynapse.

MAPE-K ANALYZE phase.

Uses:
    1. Rule-based detection for deterministic network failures.
    2. Isolation Forest for statistical anomaly detection.
    3. Random Forest for failure classification.

The rule detector acts as a safety layer. A clearly abnormal
network state is not discarded simply because the Isolation
Forest does not classify it as an outlier.
"""

import os

import joblib
import numpy as np

from monitoring.connector import (
    TELEMETRY_FEATURE_ORDER,
    normalize_telemetry,
    telemetry_to_feature_vector,
)


DEFAULT_FEATURE_COLUMNS = list(
    TELEMETRY_FEATURE_ORDER
)


class InferenceEngine:
    """
    NeuroSynapse ML inference engine.

    Responsibilities:

        telemetry
            |
            +--> anomaly detection
            |
            +--> failure classification
            |
            v
        diagnosis
    """

    # ---------------------------------------------------------
    # Deterministic anomaly thresholds
    # ---------------------------------------------------------

    CPU_THRESHOLD = 80.0
    MEMORY_THRESHOLD = 90.0
    PACKET_LOSS_THRESHOLD = 10.0
    LATENCY_THRESHOLD = 100.0
    BANDWIDTH_THRESHOLD = 90.0
    ERROR_COUNT_THRESHOLD = 10
    OSPF_NEIGHBOR_MINIMUM = 1

    # Confidence used when deterministic rules identify
    # an obvious failure.
    RULE_BASED_CONFIDENCE = 0.90

    def __init__(self):

        self.anomaly_detector = None
        self.failure_classifier = None

        self.feature_columns = (
            DEFAULT_FEATURE_COLUMNS.copy()
        )

        self.metadata = None
        self.loaded = False

        self._load_models()

    # =========================================================
    # MODEL LOADING
    # =========================================================

    def _get_models_path(self):

        backend_dir = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )

        project_root = os.path.dirname(
            backend_dir
        )

        candidate_paths = [
            os.path.join(
                project_root,
                "models",
            ),
            os.path.join(
                backend_dir,
                "models",
            ),
            os.path.join(
                backend_dir,
                "training",
                "models",
            ),
        ]

        for path in candidate_paths:

            anomaly_path = os.path.join(
                path,
                "anomaly_detector.pkl",
            )

            classifier_path = os.path.join(
                path,
                "failure_classifier.pkl",
            )

            features_path = os.path.join(
                path,
                "feature_columns.pkl",
            )

            if (
                os.path.isdir(path)
                and os.path.exists(anomaly_path)
                and os.path.exists(classifier_path)
                and os.path.exists(features_path)
            ):
                return path

        return os.path.join(
            project_root,
            "models",
        )

    def _load_models(self):

        models_path = self._get_models_path()

        try:

            anomaly_path = os.path.join(
                models_path,
                "anomaly_detector.pkl",
            )

            classifier_path = os.path.join(
                models_path,
                "failure_classifier.pkl",
            )

            feature_path = os.path.join(
                models_path,
                "feature_columns.pkl",
            )

            self.anomaly_detector = (
                joblib.load(anomaly_path)
            )

            self.failure_classifier = (
                joblib.load(classifier_path)
            )

            loaded_columns = (
                joblib.load(feature_path)
            )

            if loaded_columns:

                self.feature_columns = list(
                    loaded_columns
                )

            metadata_path = os.path.join(
                models_path,
                "model_metadata.pkl",
            )

            if os.path.exists(metadata_path):

                self.metadata = (
                    joblib.load(
                        metadata_path
                    )
                )

            self.loaded = True

            print(
                "[AI ENGINE] Models loaded successfully"
            )

            print(
                "[AI ENGINE] Feature order:",
                self.feature_columns,
            )

            if self.metadata:

                print(
                    "[AI ENGINE] "
                    f"Anomaly accuracy: "
                    f"{self.metadata.get('anomaly_accuracy', 'N/A')}"
                )

                print(
                    "[AI ENGINE] "
                    f"Classifier accuracy: "
                    f"{self.metadata.get('classifier_accuracy', 'N/A')}"
                )

        except Exception as exc:

            self.loaded = False

            print(
                f"[AI ENGINE] Models not found: {exc}"
            )

            print(
                "[AI ENGINE] Run "
                "'python backend/training/train_models.py' "
                "first"
            )

    # =========================================================
    # FEATURE EXTRACTION
    # =========================================================

    def extract_features(self, telemetry):
        """
        Convert telemetry into a one-row feature matrix.

        The feature order comes from feature_columns.pkl when
        available, otherwise TELEMETRY_FEATURE_ORDER.
        """

        normalized = normalize_telemetry(
            telemetry
        )

        if normalized is None:

            ordered = [
                0.0
                for _ in self.feature_columns
            ]

        else:

            ordered = []

            for column in self.feature_columns:

                value = normalized.get(
                    column,
                    0.0,
                )

                try:
                    value = float(value)
                except (
                    TypeError,
                    ValueError,
                ):
                    value = 0.0

                ordered.append(value)

        return np.asarray(
            [ordered],
            dtype=float,
        )

    # =========================================================
    # RULE-BASED DETECTION
    # =========================================================

    def _rule_based_detection(
        self,
        telemetry,
    ):
        """
        Deterministic network-failure detection.

        Returns:

            (
                is_anomaly,
                confidence,
                reasons
            )
        """

        normalized = normalize_telemetry(
            telemetry
        )

        if normalized is None:

            return (
                False,
                0.0,
                [],
            )

        cpu = float(
            normalized.get(
                "cpu_usage",
                0.0,
            )
        )

        memory = float(
            normalized.get(
                "memory_usage",
                0.0,
            )
        )

        packet_loss = float(
            normalized.get(
                "packet_loss",
                0.0,
            )
        )

        latency = float(
            normalized.get(
                "latency_ms",
                0.0,
            )
        )

        bandwidth = float(
            normalized.get(
                "bandwidth_util",
                0.0,
            )
        )

        interface_up_count = int(
            normalized.get(
                "interface_up_count",
                0,
            )
        )

        ospf_neighbors = int(
            normalized.get(
                "ospf_neighbors",
                0,
            )
        )

        error_count = int(
            normalized.get(
                "error_count",
                0,
            )
        )

        reasons = []

        if cpu > self.CPU_THRESHOLD:

            reasons.append(
                f"CPU {cpu:.1f}% > "
                f"{self.CPU_THRESHOLD:.1f}%"
            )

        if memory > self.MEMORY_THRESHOLD:

            reasons.append(
                f"Memory {memory:.1f}% > "
                f"{self.MEMORY_THRESHOLD:.1f}%"
            )

        if packet_loss > self.PACKET_LOSS_THRESHOLD:

            reasons.append(
                f"Packet loss {packet_loss:.1f}% > "
                f"{self.PACKET_LOSS_THRESHOLD:.1f}%"
            )

        if latency > self.LATENCY_THRESHOLD:

            reasons.append(
                f"Latency {latency:.1f}ms > "
                f"{self.LATENCY_THRESHOLD:.1f}ms"
            )

        if bandwidth > self.BANDWIDTH_THRESHOLD:

            reasons.append(
                f"Bandwidth {bandwidth:.1f}% > "
                f"{self.BANDWIDTH_THRESHOLD:.1f}%"
            )

        if error_count > self.ERROR_COUNT_THRESHOLD:

            reasons.append(
                f"Errors {error_count} > "
                f"{self.ERROR_COUNT_THRESHOLD}"
            )

        if ospf_neighbors < self.OSPF_NEIGHBOR_MINIMUM:

            reasons.append(
                f"OSPF neighbors {ospf_neighbors} < "
                f"{self.OSPF_NEIGHBOR_MINIMUM}"
            )

        # If all interfaces are down, treat that as an anomaly.
        if interface_up_count <= 0:

            reasons.append(
                "No interfaces are operational"
            )

        is_anomaly = bool(reasons)

        if not is_anomaly:

            return (
                False,
                0.0,
                [],
            )

        # Confidence increases as more independent
        # symptoms are observed.
        reason_count = len(reasons)

        confidence = min(
            1.0,
            self.RULE_BASED_CONFIDENCE
            + ((reason_count - 1) * 0.02),
        )

        return (
            True,
            confidence,
            reasons,
        )

    # =========================================================
    # ISOLATION FOREST
    # =========================================================

    def _isolation_forest_detection(
        self,
        features,
    ):
        """
        Run Isolation Forest.

        Returns:

            (
                is_anomaly,
                score
            )
        """

        if self.anomaly_detector is None:

            return (
                False,
                0.0,
            )

        try:

            prediction = (
                self.anomaly_detector.predict(
                    features
                )[0]
            )

            is_anomaly = (
                prediction == -1
            )

            # decision_function is useful for diagnostics,
            # but its numeric scale depends on the model.
            try:

                decision_score = float(
                    self.anomaly_detector
                    .decision_function(
                        features
                    )[0]
                )

            except Exception:

                decision_score = 0.0

            return (
                is_anomaly,
                decision_score,
            )

        except Exception as exc:

            print(
                "[AI ENGINE] Isolation Forest "
                f"error: {exc}"
            )

            return (
                False,
                0.0,
            )

    # =========================================================
    # ANOMALY DETECTION
    # =========================================================

    def detect_anomaly(self, telemetry):
        if not self.loaded:
            return False, 0.0
    
        features = self.extract_features(telemetry)
        cpu = features[0][0]
        memory = features[0][1]
        packet_loss = features[0][2]
        latency = features[0][3]
        bandwidth = features[0][4]
        error_count = features[0][7]
        ospf_neighbors = features[0][6]
    
        reasons = []
        
        if cpu > 80:
            reasons.append(('cpu', min(1.0, (cpu - 80) / 20)))
        if memory > 90:
            reasons.append(('memory', min(1.0, (memory - 90) / 10)))
        if packet_loss > 10:
            reasons.append(('packet_loss', min(1.0, packet_loss / 50)))
        if latency > 100:
            reasons.append(('latency', min(1.0, (latency - 100) / 300)))
        if bandwidth > 90:
            reasons.append(('bandwidth', min(1.0, (bandwidth - 90) / 10)))
        if error_count > 10:
            reasons.append(('errors', min(1.0, error_count / 50)))
        if ospf_neighbors < 1:
            reasons.append(('ospf', 0.5))
    
        if not reasons:
            return False, 0.0
    
        # Confidence based on severity, not just count
        total_severity = sum(severity for _, severity in reasons)
        avg_severity = total_severity / len(reasons)
        
        # More reasons = higher confidence, but severity matters too
        reason_count = len(reasons)
        
        if reason_count >= 4:
            confidence = 0.85 + (avg_severity * 0.15)  # 85-100%
        elif reason_count == 3:
            confidence = 0.70 + (avg_severity * 0.20)  # 70-90%
        elif reason_count == 2:
            confidence = 0.55 + (avg_severity * 0.20)  # 55-75%
        else:
            confidence = 0.40 + (avg_severity * 0.25)  # 40-65%
        
        confidence = min(1.0, max(0.35, confidence))
        
        return True, confidence

    # =========================================================
    # FAILURE CLASSIFICATION
    # =========================================================

    def classify_failure(self, telemetry):

        if self.failure_classifier is None:

            return (
                "UNKNOWN",
                0.0,
            )

        try:

            features = self.extract_features(
                telemetry
            )

            predicted_class = (
                self.failure_classifier
                .predict(features)[0]
            )

            confidence = 0.0

            if hasattr(
                self.failure_classifier,
                "predict_proba",
            ):

                probabilities = (
                    self.failure_classifier
                    .predict_proba(
                        features
                    )[0]
                )

                confidence = float(
                    np.max(
                        probabilities
                    )
                )

            failure_type = str(
                predicted_class
            )

            if failure_type.upper() == "NORMAL":

                return (
                    "NORMAL",
                    confidence,
                )

            return (
                failure_type,
                confidence,
            )

        except Exception as exc:

            print(
                "[AI ENGINE] Classification "
                f"error: {exc}"
            )

            return (
                "UNKNOWN",
                0.0,
            )

    # =========================================================
    # DIAGNOSIS
    # =========================================================

    def diagnose(self, telemetry):
        """
        Complete ANALYZE phase.

        Returns:

            {
                is_anomaly,
                anomaly_confidence,
                failure_type,
                classification_confidence,
                feature_vector
            }
        """

        normalized = normalize_telemetry(
            telemetry
        )

        feature_vector = (
            telemetry_to_feature_vector(
                normalized
            )
        )

        (
            is_anomaly,
            anomaly_confidence,
        ) = self.detect_anomaly(
            normalized
        )

        result = {
            "is_anomaly": bool(
                is_anomaly
            ),

            "anomaly_confidence": round(
                float(
                    anomaly_confidence
                ),
                4,
            ),

            "failure_type": (
                "NORMAL"
                if not is_anomaly
                else "UNKNOWN"
            ),

            "classification_confidence": 0.0,

            "feature_vector": (
                feature_vector
            ),
        }

        # -----------------------------------------------------
        # Only classify anomalous telemetry
        # -----------------------------------------------------

        if is_anomaly:

            (
                failure_type,
                classification_confidence,
            ) = self.classify_failure(
                normalized
            )

            result[
                "failure_type"
            ] = failure_type

            result[
                "classification_confidence"
            ] = round(
                float(
                    classification_confidence
                ),
                4,
            )

        print(
            "[AI ENGINE] Diagnosis: "
            f"anomaly={result['is_anomaly']} "
            f"type={result['failure_type']} "
            f"anomaly_conf="
            f"{result['anomaly_confidence']:.2%} "
            f"class_conf="
            f"{result['classification_confidence']:.2%}"
        )

        return result


engine = InferenceEngine()