"""
Generate synthetic network telemetry data for training ML models.
Creates labeled data for NORMAL, SERVICE_CRASH, LINK_FAILURE, and DDOS_ATTACK.
"""

import numpy as np
import pandas as pd
import os

# Create output directory
os.makedirs('training', exist_ok=True)

np.random.seed(42)

# Number of samples per class
SAMPLES_PER_CLASS = 500

data = []

# ============================================================
# 1. NORMAL BEHAVIOR
# ============================================================
for i in range(SAMPLES_PER_CLASS):
    data.append({
        'cpu_usage': np.random.normal(30, 10),
        'memory_usage': np.random.normal(40, 8),
        'packet_loss': np.random.normal(0.1, 0.05),
        'latency_ms': np.random.normal(5, 2),
        'bandwidth_util': np.random.normal(35, 10),
        'interface_up_count': np.random.choice([3, 4, 5], p=[0.1, 0.2, 0.7]),
        'ospf_neighbors': np.random.choice([1, 2, 3], p=[0.1, 0.3, 0.6]),
        'error_count': np.random.poisson(1),
        'label': 'NORMAL',
    })

print(f"Generated {SAMPLES_PER_CLASS} NORMAL samples")

# ============================================================
# 2. SERVICE_CRASH
# High CPU, high memory, normal interfaces, normal OSPF
# ============================================================
for i in range(SAMPLES_PER_CLASS):
    data.append({
        'cpu_usage': np.random.normal(92, 5),
        'memory_usage': np.random.normal(85, 8),
        'packet_loss': np.random.normal(2, 1),
        'latency_ms': np.random.normal(50, 15),
        'bandwidth_util': np.random.normal(60, 15),
        'interface_up_count': np.random.choice([3, 4, 5], p=[0.1, 0.3, 0.6]),
        'ospf_neighbors': np.random.choice([1, 2, 3], p=[0.1, 0.3, 0.6]),
        'error_count': np.random.poisson(3),
        'label': 'SERVICE_CRASH',
    })

print(f"Generated {SAMPLES_PER_CLASS} SERVICE_CRASH samples")

# ============================================================
# 3. LINK_FAILURE
# Normal CPU, normal memory, high packet loss, interfaces down, OSPF neighbors missing
# ============================================================
for i in range(SAMPLES_PER_CLASS):
    data.append({
        'cpu_usage': np.random.normal(35, 10),
        'memory_usage': np.random.normal(45, 8),
        'packet_loss': np.random.normal(75, 15),
        'latency_ms': np.random.normal(400, 100),
        'bandwidth_util': np.random.normal(20, 10),
        'interface_up_count': np.random.choice([0, 1], p=[0.5, 0.5]),
        'ospf_neighbors': np.random.choice([0, 1], p=[0.7, 0.3]),
        'error_count': np.random.poisson(50),
        'label': 'LINK_FAILURE',
    })

print(f"Generated {SAMPLES_PER_CLASS} LINK_FAILURE samples")

# ============================================================
# 4. DDOS_ATTACK
# Very high CPU, moderate memory, high packet loss, high bandwidth
# ============================================================
for i in range(SAMPLES_PER_CLASS):
    data.append({
        'cpu_usage': np.random.normal(97, 2),
        'memory_usage': np.random.normal(70, 10),
        'packet_loss': np.random.normal(35, 10),
        'latency_ms': np.random.normal(200, 50),
        'bandwidth_util': np.random.normal(95, 5),
        'interface_up_count': np.random.choice([3, 4, 5], p=[0.1, 0.3, 0.6]),
        'ospf_neighbors': np.random.choice([1, 2, 3], p=[0.1, 0.3, 0.6]),
        'error_count': np.random.poisson(15),
        'label': 'DDOS_ATTACK',
    })

print(f"Generated {SAMPLES_PER_CLASS} DDOS_ATTACK samples")

# Create DataFrame
df = pd.DataFrame(data)

# Shuffle the data
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

# Save
output_path = os.path.join('training', 'network_training_data.csv')
df.to_csv(output_path, index=False)

print(f"\n{'='*50}")
print(f"Training data saved to: {output_path}")
print(f"Total samples: {len(df)}")
print(f"\nClass distribution:")
for label in df['label'].value_counts().index:
    print(f"  {label}: {df['label'].value_counts()[label]} ({df['label'].value_counts()[label]/len(df)*100:.1f}%)")
print(f"\nFeature columns: {list(df.columns[:-1])}")
print(f"{'='*50}")