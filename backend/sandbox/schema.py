"""Fixed column schema of the 6 sandbox tables (in-memory DataFrames).

Kind per column: "str", "int", "float", "bool", "datetime".
Names are domain-neutral: the KPI is a value of the ``kpi`` column, not a column name.
"""

from __future__ import annotations

TABLE_SCHEMAS: dict[str, dict[str, str]] = {
    "kpi_log": {
        "timestamp": "datetime",  # shift start time
        "date": "datetime",
        "shift": "str",
        "machine_id": "str",
        "kpi": "str",  # KPI name, from domain config
        "value": "float",  # ratio in [0, 1]
    },
    "machine_log": {
        "timestamp": "datetime",
        "machine_id": "str",
        "event_type": "str",  # e.g. setpoint_change, maintenance
        "parameter": "str",
        "old_value": "float",
        "new_value": "float",
        "note": "str",
    },
    "shift_schedule": {
        "date": "datetime",
        "shift": "str",
        "machine_id": "str",
        "operator_id": "str",
        "is_substitute": "bool",
    },
    "inventory": {
        "date": "datetime",
        "material_id": "str",
        "batch_id": "str",
        "stock_qty": "int",
    },
    "supplier": {
        "supplier_id": "str",
        "name": "str",
        "material_id": "str",
        "lead_time_days": "int",
    },
    "sop": {
        "sop_id": "str",
        "version": "int",
        "title": "str",
        "step_no": "int",
        "step_text": "str",
    },
}

TABLE_NAMES: tuple[str, ...] = tuple(TABLE_SCHEMAS)
