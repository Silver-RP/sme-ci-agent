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

# Tables of the input data contract (docs/schema/data_contract.md, R10b1). ``inventory`` and ``supplier``
# above are kept only for compatibility and will be removed once dev-02/dev-03 switch the simulator and
# tools to ``material_batches``. ``sop`` (2.6) is already in TABLE_SCHEMAS. These two are not yet in
# TABLE_SCHEMAS so the simulator's table set stays unchanged until dev-02 generates them.
# Optional columns (contract "T") may be empty.
CONTRACT_TABLE_SCHEMAS: dict[str, dict[str, str]] = {
    "production_log": {
        "shift_start": "datetime",
        "shift": "str",
        "machine_id": "str",
        "units_produced": "int",
        "units_nonconforming": "int",
        "units_reworked": "int",  # optional
        "product_id": "str",  # optional
        "batch_id": "str",  # optional
    },
    "material_batches": {
        "batch_id": "str",
        "material_id": "str",
        "supplier_id": "str",
        "received_date": "datetime",
        "expiry_date": "datetime",  # optional
        "qc_result": "str",  # optional
    },
    "sop": TABLE_SCHEMAS["sop"],
}

DEPRECATED_TABLES: tuple[str, ...] = ("inventory", "supplier")  # to be removed (replaced by material_batches)

TABLE_NAMES: tuple[str, ...] = tuple(TABLE_SCHEMAS)
