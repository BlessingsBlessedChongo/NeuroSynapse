"""
Train ensemble ML models for NeuroSynapse.

Run from project root:
    python backend/training/train_ensemble.py
"""

import os
import sys
import django

# Setup Django environment BEFORE importing any Django modules
# The key fix: use the correct settings module name and add backend to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Initialize Django
django.setup()

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

from monitoring.simulated_device import SimulatedDevice
from monitoring.connector import TELEMETRY_FEATURE_ORDER


def generate_training_data(n_samples=2000):
    """Generate synthetic training data using SimulatedDevice."""
    print("[TRAINING] Generating training data...")
    sim = SimulatedDevice()

    features = []
    labels = []
    failure_types = []

    # Generate healthy samples
    sim.reset()
    for _ in range(n_samples // 2):
        telemetry = sim.get_telemetry()
        features.append([
            telemetry['cpu_usage'],
            telemetry['memory_usage'],
            telemetry['packet_loss'],
            telemetry['latency_ms'],
            telemetry['bandwidth_util'],
            telemetry['interface_up_count'],
            telemetry['ospf_neighbors'],
            telemetry['error_count'],
        ])
        labels.append(0)
        failure_types.append('NORMAL')

    # Generate anomalous samples
    failures = {
        'LINK_FAILURE': n_samples // 6,
        'SERVICE_CRASH': n_samples // 6,
        'DDOS_ATTACK': n_samples // 6,
    }

    for failure_type, count in failures.items():
        print(f"[TRAINING] Generating {failure_type} samples ({count})...")
        for i in range(count):
            # Reset then inject
            sim.reset()
            sim.inject_failure(failure_type)
            telemetry = sim.get_telemetry()

            features.append([
                telemetry['cpu_usage'],
                telemetry['memory_usage'],
                telemetry['packet_loss'],
                telemetry['latency_ms'],
                telemetry['bandwidth_util'],
                telemetry['interface_up_count'],
                telemetry['ospf_neighbors'],
                telemetry['error_count'],
            ])
            labels.append(1)
            failure_types.append(failure_type)

    X = np.array(features)
    y_anomaly = np.array(labels)
    y_failure = np.array(failure_types)

    print(f"[TRAINING] Generated {len(X)} samples")
    print(f"[TRAINING] Normal: {np.sum(y_anomaly == 0)}, Anomalous: {np.sum(y_anomaly == 1)}")
    unique, counts = np.unique(y_failure, return_counts=True)
    print(f"[TRAINING] Distribution: {dict(zip(unique, counts))}")
    return X, y_anomaly, y_failure


def train_ensemble(X, y_anomaly, y_failure):
    """Train ensemble models."""
    print("\n[TRAINING] Training ensemble models...")

    X_train, X_test, y_anomaly_train, y_anomaly_test, y_failure_train, y_failure_test = train_test_split(
        X, y_anomaly, y_failure, test_size=0.2, random_state=42, stratify=y_anomaly
    )

    print(f"[TRAINING] Train size: {len(X_train)}, Test size: {len(X_test)}")

    # Scale features
    print("[TRAINING] Scaling features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Isolation Forest
    print("[TRAINING] Training Isolation Forest...")
    isolation_forest = IsolationForest(
        contamination=0.1,
        random_state=42,
        n_estimators=100,
    )
    isolation_forest.fit(X_train_scaled)

    # LOF
    print("[TRAINING] Training Local Outlier Factor...")
    local_outlier_factor = LocalOutlierFactor(
        contamination=0.1,
        novelty=True,
        n_neighbors=20,
    )
    local_outlier_factor.fit(X_train_scaled)

    # Failure Classifier
    print("[TRAINING] Training Failure Classifier...")
    failure_classifier = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
    )

    anomaly_mask = y_anomaly_train == 1
    if np.sum(anomaly_mask) > 0:
        X_train_anomaly = X_train_scaled[anomaly_mask]
        y_failure_train_anomaly = y_failure_train[anomaly_mask]
        failure_classifier.fit(X_train_anomaly, y_failure_train_anomaly)
    else:
        print("[WARNING] No anomalous samples for classifier!")

    # Evaluate
    print("\n[TRAINING] Evaluating models...")

    if_pred = isolation_forest.predict(X_test_scaled)
    lof_pred = local_outlier_factor.predict(X_test_scaled)

    if_binary = np.where(if_pred == -1, 1, 0)
    lof_binary = np.where(lof_pred == -1, 1, 0)

    IF_WEIGHT = 0.6
    LOF_WEIGHT = 0.4
    THRESHOLD = 0.5

    ensemble_pred = np.where(
        (IF_WEIGHT * if_binary + LOF_WEIGHT * lof_binary) > THRESHOLD,
        1, 0
    )

    ensemble_accuracy = accuracy_score(y_anomaly_test, ensemble_pred)
    print(f"[TRAINING] IF Accuracy: {accuracy_score(y_anomaly_test, if_binary):.2%}")
    print(f"[TRAINING] LOF Accuracy: {accuracy_score(y_anomaly_test, lof_binary):.2%}")
    print(f"[TRAINING] Ensemble Accuracy: {ensemble_accuracy:.2%}")

    anomaly_test_mask = y_anomaly_test == 1
    if np.sum(anomaly_test_mask) > 0:
        X_test_anomaly = X_test_scaled[anomaly_test_mask]
        y_test_anomaly = y_failure_test[anomaly_test_mask]
        class_pred = failure_classifier.predict(X_test_anomaly)
        class_accuracy = accuracy_score(y_test_anomaly, class_pred)
        print(f"[TRAINING] Classifier Accuracy: {class_accuracy:.2%}")
        print(f"\n[TRAINING] Classification Report:\n{classification_report(y_test_anomaly, class_pred)}")
    else:
        class_accuracy = 0

    # Save models
    models_dir = os.path.join(BACKEND_DIR, 'models')
    os.makedirs(models_dir, exist_ok=True)

    print(f"\n[TRAINING] Saving models to {models_dir}...")

    joblib.dump(isolation_forest, os.path.join(models_dir, 'isolation_forest.pkl'))
    joblib.dump(local_outlier_factor, os.path.join(models_dir, 'local_outlier_factor.pkl'))
    joblib.dump(failure_classifier, os.path.join(models_dir, 'failure_classifier.pkl'))
    joblib.dump(scaler, os.path.join(models_dir, 'scaler.pkl'))
    joblib.dump(TELEMETRY_FEATURE_ORDER, os.path.join(models_dir, 'feature_columns.pkl'))

    metadata = {
        'ensemble_accuracy': float(ensemble_accuracy),
        'classifier_accuracy': float(class_accuracy),
        'if_weight': IF_WEIGHT,
        'lof_weight': LOF_WEIGHT,
        'threshold': THRESHOLD,
        'n_samples': len(X),
        'feature_names': TELEMETRY_FEATURE_ORDER,
    }
    joblib.dump(metadata, os.path.join(models_dir, 'model_metadata.pkl'))

    print(f"[TRAINING] Models saved successfully")
    print(f"[TRAINING] Metadata: {metadata}")

    return isolation_forest, local_outlier_factor, failure_classifier, scaler


if __name__ == '__main__':
    print("=" * 60)
    print("NEUROSYNAPSE - ENSEMBLE ML TRAINING")
    print("=" * 60)

    X, y_anomaly, y_failure = generate_training_data(2000)
    train_ensemble(X, y_anomaly, y_failure)

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)