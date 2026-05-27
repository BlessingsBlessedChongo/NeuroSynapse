"""
Train the NeuroSynapse ML models:
1. Isolation Forest for anomaly detection
2. Random Forest for failure classification
"""

import os
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)

# Create models directory
os.makedirs('models', exist_ok=True)

# ============================================================
# 1. LOAD DATA
# ============================================================
print("Loading training data...")
df = pd.read_csv(os.path.join('training', 'network_training_data.csv'))

# Features
feature_columns = ['cpu_usage', 'memory_usage', 'packet_loss', 'latency_ms',
                   'bandwidth_util', 'interface_up_count', 'ospf_neighbors', 'error_count']
X = df[feature_columns].values

# Labels
y = df['label'].values

print(f"Total samples: {len(df)}")
print(f"Features: {feature_columns}")

# Split: 80% training, 20% testing
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"Training samples: {len(X_train)}, Testing samples: {len(X_test)}")

# ============================================================
# 2. ANOMALY DETECTOR (Isolation Forest)
# ============================================================
print("\n" + "="*50)
print("TRAINING ANOMALY DETECTOR")
print("="*50)

# Train on NORMAL data only
X_normal = X_train[y_train == 'NORMAL']

anomaly_detector = IsolationForest(
    n_estimators=100,
    contamination=0.1,
    random_state=42,
    n_jobs=-1,
)
anomaly_detector.fit(X_normal)

# Test anomaly detection
# Isolation Forest returns -1 for anomaly, 1 for normal
y_pred_anomaly = anomaly_detector.predict(X_test)
y_pred_anomaly = np.where(y_pred_anomaly == 1, 'NORMAL', 'ANOMALY')
y_true_anomaly = np.where(y_test == 'NORMAL', 'NORMAL', 'ANOMALY')

anomaly_accuracy = accuracy_score(y_true_anomaly, y_pred_anomaly)
print(f"Anomaly Detection Accuracy: {anomaly_accuracy:.2%}")
print(f"\nConfusion Matrix (Anomaly Detection):")
print(pd.DataFrame(
    confusion_matrix(y_true_anomaly, y_pred_anomaly),
    index=['Actual Normal', 'Actual Anomaly'],
    columns=['Pred Normal', 'Pred Anomaly']
))

# ============================================================
# 3. FAILURE CLASSIFIER (Random Forest)
# ============================================================
print("\n" + "="*50)
print("TRAINING FAILURE CLASSIFIER")
print("="*50)

classifier = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    random_state=42,
    n_jobs=-1,
)
classifier.fit(X_train, y_train)

# Test classifier
y_pred_class = classifier.predict(X_test)
classifier_accuracy = accuracy_score(y_test, y_pred_class)
print(f"Classifier Accuracy: {classifier_accuracy:.2%}")

print(f"\nClassification Report:")
print(classification_report(y_test, y_pred_class))

# Cross-validation
cv_scores = cross_val_score(classifier, X, y, cv=5)
print(f"Cross-validation scores: {cv_scores}")
print(f"Mean CV accuracy: {cv_scores.mean():.2%} (+/- {cv_scores.std()*2:.2%})")

# Feature importance
print(f"\nFeature Importance:")
importances = pd.DataFrame({
    'feature': feature_columns,
    'importance': classifier.feature_importances_
}).sort_values('importance', ascending=False)
print(importances.to_string(index=False))

# ============================================================
# 4. SAVE MODELS
# ============================================================
print("\n" + "="*50)
print("SAVING MODELS")
print("="*50)

# Save models
joblib.dump(anomaly_detector, os.path.join('models', 'anomaly_detector.pkl'))
print("Saved: models/anomaly_detector.pkl")

joblib.dump(classifier, os.path.join('models', 'failure_classifier.pkl'))
print("Saved: models/failure_classifier.pkl")

# Save feature columns
joblib.dump(feature_columns, os.path.join('models', 'feature_columns.pkl'))
print("Saved: models/feature_columns.pkl")

# Save training metadata
metadata = {
    'features': feature_columns,
    'n_features': len(feature_columns),
    'anomaly_accuracy': anomaly_accuracy,
    'classifier_accuracy': classifier_accuracy,
    'cv_mean': cv_scores.mean(),
    'classes': classifier.classes_.tolist(),
}
joblib.dump(metadata, os.path.join('models', 'model_metadata.pkl'))
print("Saved: models/model_metadata.pkl")

print(f"\n{'='*50}")
print(f"TRAINING COMPLETE")
print(f"Anomaly Detection Accuracy: {anomaly_accuracy:.2%}")
print(f"Failure Classification Accuracy: {classifier_accuracy:.2%}")
print(f"Models saved in: models/")
print(f"{'='*50}")

# ============================================================
# 5. QUICK MANUAL TEST
# ============================================================
print("\n" + "="*50)
print("MANUAL TEST PREDICTIONS")
print("="*50)

test_cases = [
    ([25, 40, 0.1, 5, 35, 4, 2, 1], "Expected: NORMAL"),
    ([95, 88, 3, 60, 65, 4, 2, 5], "Expected: SERVICE_CRASH"),
    ([30, 42, 80, 450, 15, 0, 0, 60], "Expected: LINK_FAILURE"),
    ([99, 75, 40, 250, 98, 4, 2, 20], "Expected: DDOS_ATTACK"),
]

for features, expected in test_cases:
    features_array = np.array(features).reshape(1, -1)
    
    # Check anomaly
    is_anomaly = anomaly_detector.predict(features_array)[0] == -1
    
    # Classify
    predicted_class = classifier.predict(features_array)[0]
    probabilities = classifier.predict_proba(features_array)[0]
    confidence = max(probabilities)
    
    status = "ANOMALY" if is_anomaly else "NORMAL"
    print(f"\nFeatures: {features}")
    print(f"  Status: {status}")
    print(f"  Prediction: {predicted_class} (confidence: {confidence:.2%})")
    print(f"  {expected}")