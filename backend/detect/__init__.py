"""Statistical detection (T-012)."""

from backend.detect.statistical import (
    Anomaly,
    DetectParams,
    anomaly_events,
    detect,
    detect_anomalies,
    planned_maintenance_windows,
)

__all__ = [
    "Anomaly",
    "DetectParams",
    "anomaly_events",
    "detect",
    "detect_anomalies",
    "planned_maintenance_windows",
]
