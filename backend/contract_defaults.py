"""Defaults of optional domain-config keys, as fixed by docs/schema/data_contract.md section 1.2.

Kept apart from backend/domain_config.py, which must not contain domain names (H-22 guard tests).
"""

DEFAULT_EVENT_TYPES: tuple[str, ...] = (
    "setpoint_change",
    "program_change",
    "maintenance",
    "calibration",
    "breakdown",
    "alarm",
    "note",
)
