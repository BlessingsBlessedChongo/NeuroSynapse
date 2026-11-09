"""Map canonical telemetry inputs to the dedicated model feature contract."""

from .model_loader import CANONICAL


def build_features(raw: dict) -> dict:
    """Return all canonical keys; missing values remain None for median imputation."""
    return {key: raw.get(key) for key in CANONICAL}