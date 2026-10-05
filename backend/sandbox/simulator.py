"""Parameterised simulator producing "normal" synthetic plant data.

Resolution: one ``kpi_log`` row per (date, shift, machine).
Setpoint-sensitive KPI model (KPI name is a parameter, not hard-coded):

    mean  = baseline + sensitivity_per_c * |setpoint - sop_setpoint|
    value = clip(Normal(mean, noise_sd), 0, 1)

All numbers come from parameters; ``params_from_config`` reads them from
data/scenarios/<scenario>.yaml and data/context_profile.yaml.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from backend.domain_config import DEFAULT_PROFILE_PATH, DomainConfig, load_domain_config
from backend.sandbox.schema import TABLE_NAMES, TABLE_SCHEMAS

DEFAULT_SCENARIO_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "scenarios" / "scenario1.yaml"
)

_DTYPES = {
    "str": "object",
    "int": "int64",
    "float": "float64",
    "bool": "bool",
    "datetime": "datetime64[ns]",
}


@dataclass(frozen=True)
class SetpointChange:
    """A change of the controlled setpoint on one machine, effective from ``timestamp``."""

    machine_id: str
    timestamp: datetime
    value: float


@dataclass(frozen=True)
class SimParams:
    machines: tuple[str, ...]
    shifts: tuple[str, ...]
    shift_start_hours: dict[str, int]
    start_date: str
    days: int
    kpi: str
    baseline: float
    noise_sd: float
    sop_setpoint: float
    sensitivity_per_c: float
    seed: int = 42
    setpoint_param: str = "zone3_setpoint_c"
    setpoint_changes: tuple[SetpointChange, ...] = ()
    materials: tuple[str, ...] = ("MAT-A", "MAT-B")
    sop_entries: tuple[tuple[str, int, str, tuple[str, ...]], ...] = field(default_factory=tuple)

    def with_(self, **changes) -> SimParams:
        return replace(self, **changes)


def expected_kpi_value(
    setpoint: float | np.ndarray, sop_setpoint: float, baseline: float, sensitivity_per_c: float
):
    """Expected KPI value given the deviation of the setpoint from the SOP value."""
    return baseline + sensitivity_per_c * np.abs(np.asarray(setpoint, dtype=float) - sop_setpoint)


def empty_table(name: str) -> pd.DataFrame:
    schema = TABLE_SCHEMAS[name]
    return pd.DataFrame({c: pd.Series(dtype=_DTYPES[k]) for c, k in schema.items()})


def _typed(name: str, df: pd.DataFrame) -> pd.DataFrame:
    schema = TABLE_SCHEMAS[name]
    out = df.reindex(columns=list(schema))
    for col, kind in schema.items():
        out[col] = out[col].astype(_DTYPES[kind])
    return out.reset_index(drop=True)


def _setpoint_series(params: SimParams, machine: str, times: pd.DatetimeIndex) -> np.ndarray:
    values = np.full(len(times), params.sop_setpoint, dtype=float)
    changes = sorted(
        (c for c in params.setpoint_changes if c.machine_id == machine), key=lambda c: c.timestamp
    )
    for c in changes:
        values[times >= pd.Timestamp(c.timestamp)] = c.value
    return values


def simulate(params: SimParams) -> dict[str, pd.DataFrame]:
    """Generate the 6 tables for normal operation (plus logged setpoint changes, if any)."""
    rng = np.random.default_rng(params.seed)
    dates = pd.date_range(params.start_date, periods=params.days, freq="D")

    kpi_rows = []
    sched_rows = []
    for m_idx, machine in enumerate(params.machines):
        ts_list, date_list, shift_list = [], [], []
        for d in dates:
            for shift in params.shifts:
                ts_list.append(d + pd.Timedelta(hours=params.shift_start_hours[shift]))
                date_list.append(d)
                shift_list.append(shift)
                sched_rows.append(
                    (d, shift, machine, f"OP-{shift[:1].upper()}{m_idx + 1:02d}", False)
                )
        times = pd.DatetimeIndex(ts_list)
        setpoints = _setpoint_series(params, machine, times)
        mean = expected_kpi_value(
            setpoints, params.sop_setpoint, params.baseline, params.sensitivity_per_c
        )
        values = np.clip(rng.normal(mean, params.noise_sd), 0.0, 1.0)
        kpi_rows.append(
            pd.DataFrame(
                {
                    "timestamp": times,
                    "date": date_list,
                    "shift": shift_list,
                    "machine_id": machine,
                    "kpi": params.kpi,
                    "value": values,
                }
            )
        )
    kpi_log = (
        pd.concat(kpi_rows, ignore_index=True).sort_values(["timestamp", "machine_id"], kind="stable")
        if kpi_rows
        else empty_table("kpi_log")
    )

    machine_log = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp(c.timestamp),
                "machine_id": c.machine_id,
                "event_type": "setpoint_change",
                "parameter": params.setpoint_param,
                "old_value": _previous_value(params, c),
                "new_value": c.value,
                "note": "",
            }
            for c in sorted(params.setpoint_changes, key=lambda c: c.timestamp)
        ]
    )

    inv_rows = []
    for mat in params.materials:
        for d in dates:
            batch = f"{mat}-B{d.isocalendar().week:02d}"
            inv_rows.append((d, mat, batch, int(rng.integers(500, 1500))))
    inventory = pd.DataFrame(inv_rows, columns=["date", "material_id", "batch_id", "stock_qty"])

    supplier = pd.DataFrame(
        [
            (f"SUP-{i + 1:02d}", f"Supplier {i + 1} (synthetic)", mat, 3 + i)
            for i, mat in enumerate(params.materials)
        ],
        columns=["supplier_id", "name", "material_id", "lead_time_days"],
    )

    sop = pd.DataFrame(
        [
            (sop_id, version, title, n, text)
            for sop_id, version, title, steps in params.sop_entries
            for n, text in enumerate(steps, start=1)
        ],
        columns=["sop_id", "version", "title", "step_no", "step_text"],
    )

    tables = {
        "kpi_log": kpi_log,
        "machine_log": machine_log,
        "shift_schedule": pd.DataFrame(
            sched_rows, columns=["date", "shift", "machine_id", "operator_id", "is_substitute"]
        ),
        "inventory": inventory,
        "supplier": supplier,
        "sop": sop,
    }
    return {name: _typed(name, tables[name]) for name in TABLE_NAMES}


def _previous_value(params: SimParams, change: SetpointChange) -> float:
    prev = params.sop_setpoint
    for c in sorted(params.setpoint_changes, key=lambda c: c.timestamp):
        if c.machine_id != change.machine_id:
            continue
        if c.timestamp < change.timestamp:
            prev = c.value
    return float(prev)


def params_from_config(
    scenario_path: str | Path = DEFAULT_SCENARIO_PATH,
    profile_path: str | Path = DEFAULT_PROFILE_PATH,
    *,
    seed: int = 42,
    setpoint_changes: Sequence[SetpointChange] = (),
) -> SimParams:
    """Build SimParams from the scenario YAML + domain config. The KPI must exist in the profile."""
    scenario = yaml.safe_load(Path(scenario_path).read_text(encoding="utf-8"))
    cfg: DomainConfig = load_domain_config(profile_path)
    plant, base = scenario["plant"], scenario["baseline"]
    kpi = base["kpi"]
    if kpi not in {k.name for k in cfg.kpis}:
        raise ValueError(f"KPI {kpi!r} not defined in the domain config")
    start = pd.Timestamp(plant.get("start_date", "2026-01-01"))
    days = (start + pd.DateOffset(months=int(plant["horizon_months"])) - start).days
    return SimParams(
        machines=tuple(plant["machines"]),
        shifts=tuple(plant["shifts"]),
        shift_start_hours=dict(plant["shift_start_hours"]),
        start_date=str(start.date()),
        days=days,
        kpi=kpi,
        baseline=float(base["value"]),
        noise_sd=float(base["noise_sd"]),
        sop_setpoint=float(base["zone3_setpoint_c"]),
        sensitivity_per_c=float(base["setpoint_sensitivity_per_c"]),
        seed=seed,
        setpoint_changes=tuple(setpoint_changes),
        sop_entries=tuple((s.id, s.version, s.title, tuple(s.steps)) for s in cfg.sop),
    )
