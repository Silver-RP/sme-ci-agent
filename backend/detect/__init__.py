"""Statistical detection (T-012)."""

from backend.detect.statistical import (
    Anomaly,
    DetectedAnomaly,
    DetectParams,
    anomaly_events,
    detect,
    detect_anomalies,
    planned_maintenance_windows,
    replay_detect,
)

__all__ = [
    "Anomaly",
    "DetectParams",
    "DetectedAnomaly",
    "anomaly_events",
    "detect",
    "detect_anomalies",
    "planned_maintenance_windows",
    "replay_detect",
]
