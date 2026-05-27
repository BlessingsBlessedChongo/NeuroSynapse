"""
ML Inference Engine for NeuroSynapse.
Loads trained models and makes predictions on live telemetry data.
"""

import os
import numpy as np
import joblib
from django.conf import settings


class InferenceEngine:
    """Loads ML models and provides prediction methods."""
    
    def __init__(self):
        self.anomaly_detector = None
        self.failure_classifier = None
        self.feature_columns = None
        self.metadata = None
        self.loaded = False
        self._load_models()
    
    def _get_models_path(self):
        """Get the absolute path to the models directory."""
        # Go up from backend/ to project root, then to models/
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(backend_dir)
        return os.path.join(project_root, 'models')
    
    def _load_models(self):
        """Load all trained models from disk."""
        models_path = self._get_models_path()
        
        try:
            self.anomaly_detector = joblib.load(
                os.path.join(models_path, 'anomaly_detector.pkl')
            )
            self.failure_classifier = joblib.load(
                os.path.join(models_path, 'failure_classifier.pkl')
            )
            self.feature_columns = joblib.load(
                os.path.join(models_path, 'feature_columns.pkl')
            )
            self.metadata = joblib.load(
                os.path.join(models_path, 'model_metadata.pkl')
            )
            self.loaded = True
            print(f"[AI ENGINE] Models loaded successfully")
            print(f"[AI ENGINE] Anomaly accuracy: {self.metadata.get('anomaly_accuracy', 'N/A')}")
            print(f"[AI ENGINE] Classifier accuracy: {self.metadata.get('classifier_accuracy', 'N/A')}")
        except FileNotFoundError as e:
            print(f"[AI ENGINE] Models not found: {e}")
            print(f"[AI ENGINE] Run 'python training/train_models.py' first")
        except Exception as e:
            print(f"[AI ENGINE] Error loading models: {e}")
    
    def extract_features(self, telemetry):
        """Convert a Telemetry object into a feature array."""
        # Count interfaces that are up
        interface_status = telemetry.interface_status or {}
        up_count = sum(
            1 for details in interface_status.values()
            if details.get('status') == 'up'
        )
        
        # Count OSPF neighbors
        ospf_neighbors = 0  # Default if not in telemetry
        
        # Build feature array in the correct order
        features = np.array([[
            telemetry.cpu_usage or 0,
            telemetry.memory_usage or 0,
            telemetry.packet_loss or 0,
            telemetry.latency_ms or 0,
            telemetry.bandwidth_util or 30,  # Default
            up_count,
            ospf_neighbors,
            0,  # error_count default
        ]])
        
        return features
    
    def detect_anomaly(self, telemetry):
        """Check if telemetry indicates an anomaly.
        
        Returns:
            (is_anomaly: bool, confidence: float)
        """
        if not self.loaded:
            return False, 0.0
        
        features = self.extract_features(telemetry)
        
        # Isolation Forest: -1 = anomaly, 1 = normal
        prediction = self.anomaly_detector.predict(features)[0]
        is_anomaly = prediction == -1
        
        # Get anomaly score (lower = more anomalous)
        score = self.anomaly_detector.score_samples(features)[0]
        # Convert to confidence (0 to 1)
        confidence = 1.0 - (1.0 / (1.0 + np.exp(-score)))
        
        return is_anomaly, confidence
    
    def classify_failure(self, telemetry):
        """Classify the type of failure from telemetry.
        
        Returns:
            (failure_type: str, confidence: float)
        """
        if not self.loaded:
            return 'UNKNOWN', 0.0
        
        features = self.extract_features(telemetry)
        
        # Get prediction and probabilities
        predicted_class = self.failure_classifier.predict(features)[0]
        probabilities = self.failure_classifier.predict_proba(features)[0]
        confidence = max(probabilities)
        
        return predicted_class, confidence
    
    def diagnose(self, telemetry):
        """Full diagnosis: detect anomaly and classify failure.
        
        Returns:
            dict with keys: is_anomaly, anomaly_confidence, 
                           failure_type, classification_confidence
        """
        is_anomaly, anomaly_conf = self.detect_anomaly(telemetry)
        
        result = {
            'is_anomaly': is_anomaly,
            'anomaly_confidence': round(anomaly_conf, 4),
            'failure_type': 'NORMAL',
            'classification_confidence': 0.0,
        }
        
        if is_anomaly:
            failure_type, class_conf = self.classify_failure(telemetry)
            result['failure_type'] = failure_type
            result['classification_confidence'] = round(class_conf, 4)
        
        return result


# Create a global instance
engine = InferenceEngine()