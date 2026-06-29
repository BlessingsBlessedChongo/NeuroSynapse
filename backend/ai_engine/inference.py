"""
ML Inference Engine for NeuroSynapse.
Isolation Forest + LOF ensemble for anomaly detection (>90% target accuracy).
"""

import os
import numpy as np
import joblib
import pandas as pd
from sklearn.neighbors import LocalOutlierFactor

from monitoring.connector import TELEMETRY_FEATURE_ORDER, normalize_telemetry, telemetry_to_feature_vector

DEFAULT_FEATURE_COLUMNS = list(TELEMETRY_FEATURE_ORDER)


class InferenceEngine:
    """Loads ML models and provides prediction methods."""

    def __init__(self):
        self.anomaly_detector = None
        self.lof_detector = None
        self.failure_classifier = None
        self.feature_columns = DEFAULT_FEATURE_COLUMNS
        self.metadata = None
        self.loaded = False
        self._load_models()

    def _get_models_path(self):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(backend_dir)
        for path in [
            os.path.join(project_root, 'models'),
            os.path.join(backend_dir, 'models'),
            os.path.join(backend_dir, 'training', 'models'),
        ]:
            if os.path.exists(path):
                return path
        return os.path.join(project_root, 'models')

    def _get_training_csv_path(self):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.join(backend_dir, 'training', 'training', 'network_training_data.csv'),
            os.path.join(os.path.dirname(backend_dir), 'training', 'training', 'network_training_data.csv'),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _fit_lof_ensemble(self):
        """Fit LOF novelty detector on NORMAL training samples for ensemble scoring."""
        csv_path = self._get_training_csv_path()
        if not csv_path:
            print("[AI ENGINE] LOF ensemble skipped: training CSV not found")
            return

        try:
            df = pd.read_csv(csv_path)
            normal_df = df[df['label'] == 'NORMAL']
            if normal_df.empty:
                return
            X_normal = normal_df[self.feature_columns].values
            self.lof_detector = LocalOutlierFactor(
                n_neighbors=20,
                contamination=0.1,
                novelty=True,
                n_jobs=-1,
            )
            self.lof_detector.fit(X_normal)
            print("[AI ENGINE] LOF ensemble fitted on NORMAL training data")
        except Exception as exc:
            print(f"[AI ENGINE] LOF ensemble setup failed: {exc}")
            self.lof_detector = None

    def _load_models(self):
        models_path = self._get_models_path()
        try:
            self.anomaly_detector = joblib.load(
                os.path.join(models_path, 'anomaly_detector.pkl')
            )
            self.failure_classifier = joblib.load(
                os.path.join(models_path, 'failure_classifier.pkl')
            )
            loaded_columns = joblib.load(
                os.path.join(models_path, 'feature_columns.pkl')
            )
            if loaded_columns:
                self.feature_columns = list(loaded_columns)
            metadata_path = os.path.join(models_path, 'model_metadata.pkl')
            if os.path.exists(metadata_path):
                self.metadata = joblib.load(metadata_path)
            self.loaded = True
            self._fit_lof_ensemble()
            print("[AI ENGINE] Models loaded successfully")
            if self.metadata:
                print(f"[AI ENGINE] Anomaly accuracy: {self.metadata.get('anomaly_accuracy', 'N/A')}")
                print(f"[AI ENGINE] Classifier accuracy: {self.metadata.get('classifier_accuracy', 'N/A')}")
        except Exception as e:
            print(f"[AI ENGINE] Models not found: {e}")
            print("[AI ENGINE] Run 'python backend/training/train_models.py' first")

    def extract_features(self, telemetry):
        """Convert telemetry dict or Django model into a feature matrix row."""
        normalized = normalize_telemetry(telemetry)
        if normalized is None:
            ordered = [0.0] * len(self.feature_columns)
        else:
            ordered = [float(normalized.get(col, 0.0)) for col in self.feature_columns]
        return np.array([ordered], dtype=float)

    @staticmethod
    def _score_to_confidence(score):
        """Map sklearn decision/score output to a stable 0-1 confidence value."""
        return float(1.0 / (1.0 + np.exp(-score)))

    def detect_anomaly(self, telemetry):
        if not self.loaded:
            return False, 0.0

        features = self.extract_features(telemetry)

        iforest_pred = self.anomaly_detector.predict(features)[0]
        iforest_score = float(self.anomaly_detector.score_samples(features)[0])
        iforest_conf = self._score_to_confidence(iforest_score)

        lof_is_anomaly = False
        lof_conf = 0.0
        if self.lof_detector is not None:
            lof_pred = self.lof_detector.predict(features)[0]
            lof_score = float(self.lof_detector.score_samples(features)[0])
            lof_is_anomaly = lof_pred == -1
            lof_conf = self._score_to_confidence(lof_score)

        iforest_is_anomaly = iforest_pred == -1
        is_anomaly = iforest_is_anomaly or lof_is_anomaly

        if is_anomaly:
            confidence = max(iforest_conf, lof_conf) if lof_conf else iforest_conf
        else:
            confidence = 1.0 - max(iforest_conf, lof_conf if lof_conf else iforest_conf)

        return is_anomaly, float(np.clip(confidence, 0.0, 1.0))

    def classify_failure(self, telemetry):
        if not self.loaded:
            return 'UNKNOWN', 0.0

        features = self.extract_features(telemetry)
        predicted_class = self.failure_classifier.predict(features)[0]
        probabilities = self.failure_classifier.predict_proba(features)[0]
        confidence = float(max(probabilities))

        if predicted_class == 'NORMAL':
            return 'UNKNOWN', confidence

        return str(predicted_class), confidence

    def diagnose(self, telemetry):
        """
        Full ANALYZE phase output.
        Accepts raw dict telemetry or a Django Telemetry model instance.
        """
        is_anomaly, anomaly_conf = self.detect_anomaly(telemetry)
        result = {
            'is_anomaly': bool(is_anomaly),
            'anomaly_confidence': round(anomaly_conf, 4),
            'failure_type': 'NORMAL',
            'classification_confidence': 0.0,
            'feature_vector': telemetry_to_feature_vector(telemetry),
        }

        if is_anomaly:
            failure_type, class_conf = self.classify_failure(telemetry)
            result['failure_type'] = failure_type
            result['classification_confidence'] = round(class_conf, 4)

        return result


engine = InferenceEngine()
