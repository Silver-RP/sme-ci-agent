"""Parameterised simulator producing "normal" synthetic plant data, as COUNTS (data contract 2.1).

Resolution: one ``production_log`` row per (shift_start, machine). Per row:

    units_produced      ~ round(Normal(units_mean * machine_factor * shift_factor, units_cv * mean)), >= 1
    <numerator column>  ~ Binomial(units_produced, p)

``p`` of the scenario KPI follows the setpoint model (KPI name is a parameter, not hard-coded):

    p = clip(baseline + sensitivity_per_c * |setpoint - sop_setpoint|, 0, 1)

Other KPIs of the domain config use their own target as ``p``. ``kpi_log`` is DERIVED from
``production_log`` (ratio = numerator / denominator, contract 2.8); only the scenario KPI is kept.

Also generated: ``material_batches`` (a new lot per material every few days, each production row
uses the lot of its machine's material), ``sop`` (from the domain config) and "ordinary" machine
events (program changes, alarms, small tweaks of parameters that the model does not use) so the
answer is not given away. All numbers come from parameters; ``params_from_config`` reads them from
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
from backend.sandbox.kpi_derive import derive_kpi_log
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
    # volume (per machine / shift)
    units_mean: float = 1200.0
    units_cv: float = 0.1
    machine_factor: dict[str, float] = field(default_factory=dict)
    shift_factor: dict[str, float] = field(default_factory=dict)
    products: tuple[str, ...] = ("PRD-A",)
    product_change_days: int = 9
    # KPI -> (numerator column, denominator column); target of every KPI (p of the non-scenario KPIs)
    kpi_columns: dict[str, tuple[str, str]] = field(default_factory=dict)
    kpi_targets: dict[str, float] = field(default_factory=dict)
    profile_path: str = str(DEFAULT_PROFILE_PATH)
    # material lots
    receive_every_days: int = 7
    shelf_life_days: int = 90
    conditional_rate: float = 0.05
    # ordinary machine events
    alarms_per_month: float = 2.0
    tweaks_per_month: float = 3.0
    tweak_step: float = 2.0
    tweak_reference: dict[str, float] = field(default_factory=dict)
    limits: dict[str, tuple[float, float]] = field(default_factory=dict)

    def with_(self, **changes) -> SimParams:
        return replace(self, **changes)

    @property
    def numerator(self) -> str:
        """Production-log column that counts the scenario KPI's numerator."""
        try:
            return self.kpi_columns[self.kpi][0]
        except KeyError:
            raise ValueError(f"KPI {self.kpi!r} has no column mapping in the params") from None


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


def scenario_kpi_log(production_log: pd.DataFrame, params: SimParams) -> pd.DataFrame:
    """``kpi_log`` derived from ``production_log`` for the scenario KPI only (contract 2.8)."""
    cfg = load_domain_config(params.profile_path)
    one = cfg.model_copy(update={"kpis": [k for k in cfg.kpis if k.name == params.kpi]})
    kpi_log, _notes = derive_kpi_log(production_log, one)
    return kpi_log


def _material_for(params: SimParams, m_idx: int) -> str | None:
    return params.materials[m_idx % len(params.materials)] if params.materials else None


def _lot_id(material: str, received: pd.Timestamp) -> str:
    return f"{material}-{received:%Y%m%d}"


def _material_batches(params: SimParams, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    step = max(1, params.receive_every_days)
    for i, mat in enumerate(params.materials):
        for off in range(0, max(params.days, 0), step):
            received = pd.Timestamp(params.start_date) + pd.Timedelta(days=off)
            roll = rng.random()
            qc = "conditional" if roll < params.conditional_rate else "pass"
            rows.append(
                {
                    "batch_id": _lot_id(mat, received),
                    "material_id": mat,
                    "supplier_id": f"SUP-{i + 1:02d}",
                    "received_date": received,
                    "expiry_date": received + pd.Timedelta(days=params.shelf_life_days),
                    "qc_result": qc,
                }
            )
    return pd.DataFrame(rows, columns=list(TABLE_SCHEMAS["material_batches"]))


def _batch_ids(params: SimParams, material: str | None, times: pd.DatetimeIndex) -> np.ndarray:
    """Lot of ``material`` in use at each time: the most recently received one."""
    if material is None or not len(times):
        return np.full(len(times), "", dtype=object)
    start = pd.Timestamp(params.start_date)
    step = max(1, params.receive_every_days)
    days = np.asarray((times.normalize() - start).days)
    off = (days // step) * step
    return np.array([_lot_id(material, start + pd.Timedelta(days=int(o))) for o in off], dtype=object)


def _product_changes(params: SimParams, m_idx: int, rng: np.random.Generator) -> list[pd.Timestamp]:
    start = pd.Timestamp(params.start_date)
    step = max(1, params.product_change_days)
    offs = list(range(step + m_idx % step, params.days, step))
    if not offs and params.days >= 2:
        offs = [params.days // 2]
    return [
        start + pd.Timedelta(days=o, hours=int(rng.integers(0, 24)), minutes=int(rng.integers(0, 60)))
        for o in offs
    ]


def _normal_events(params: SimParams, m_idx: int, machine: str, rng, changes: list[pd.Timestamp]) -> list[dict]:
    """Ordinary machine-log rows: program changes, alarms, small tweaks of unmodelled parameters."""
    if params.days <= 0:
        return []
    start = pd.Timestamp(params.start_date)
    horizon_min = params.days * 24 * 60
    rows: list[dict] = []

    def at(minute: int) -> pd.Timestamp:
        return start + pd.Timedelta(minutes=int(minute))

    for k, ts in enumerate(changes, start=1):
        prod = params.products[(m_idx + k) % len(params.products)]
        rows.append(
            {"timestamp": ts, "machine_id": machine, "event_type": "program_change", "parameter": "",
             "old_value": np.nan, "new_value": np.nan, "note": f"PRG-{prod}"}
        )
    ref = dict(params.tweak_reference)
    names = sorted(ref)
    n_alarm = max(1, int(rng.poisson(params.alarms_per_month * params.days / 30.0)))
    for _ in range(n_alarm):
        param = names[int(rng.integers(0, len(names)))] if names else ""
        rows.append(
            {"timestamp": at(rng.integers(0, horizon_min)), "machine_id": machine, "event_type": "alarm",
             "parameter": param, "old_value": np.nan,
             "new_value": float(ref[param] + rng.normal(0, 2 * params.tweak_step)) if param else np.nan,
             "note": "temperature deviation, back to normal" if param else "controller warning"}
        )
    for param in names:
        lo, hi = params.limits.get(param, (-np.inf, np.inf))
        n = int(rng.poisson(params.tweaks_per_month * params.days / 30.0 / max(len(names), 1)))
        cur = float(ref[param])
        for minute in sorted(int(x) for x in rng.integers(0, horizon_min, n)):
            step = float(rng.choice([-1, 1])) * float(rng.integers(1, max(2, int(params.tweak_step) + 1)))
            new = float(np.clip(cur + step, lo, hi))
            if new == cur:
                new = float(np.clip(cur - step, lo, hi))
            if new == cur:
                continue
            rows.append(
                {"timestamp": at(minute), "machine_id": machine, "event_type": "setpoint_change",
                 "parameter": param, "old_value": cur, "new_value": new, "note": "fine adjustment"}
            )
            cur = new
    return rows


def simulate(params: SimParams) -> dict[str, pd.DataFrame]:
    """Generate the sandbox tables for normal operation (plus logged setpoint changes, if any)."""
    # independent streams: changing one table's model leaves the others as they were
    rng_units = np.random.default_rng([params.seed, 10])
    rng_count = np.random.default_rng([params.seed, 11])
    rng_events = np.random.default_rng([params.seed, 12])
    rng_batch = np.random.default_rng([params.seed, 13])
    rng_inv = np.random.default_rng([params.seed, 14])
    dates = pd.date_range(params.start_date, periods=params.days, freq="D")
    numerator = params.numerator if params.machines else None
    denominator = params.kpi_columns[params.kpi][1] if params.kpi in params.kpi_columns else "units_produced"
    other_p = {
        params.kpi_columns[k][0]: float(t)
        for k, t in params.kpi_targets.items()
        if k in params.kpi_columns and k != params.kpi
    }

    prod_rows = []
    sched_rows = []
    event_rows: list[dict] = []
    for m_idx, machine in enumerate(params.machines):
        ts_list, shift_list = [], []
        for d in dates:
            for shift in params.shifts:
                ts_list.append(d + pd.Timedelta(hours=params.shift_start_hours[shift]))
                shift_list.append(shift)
                sched_rows.append(
                    (d, shift, machine, f"OP-{shift[:1].upper()}{m_idx + 1:02d}", False)
                )
        times = pd.DatetimeIndex(ts_list)
        n = len(times)
        mean_units = np.array(
            [
                params.units_mean * params.machine_factor.get(machine, 1.0) * params.shift_factor.get(s, 1.0)
                for s in shift_list
            ],
            dtype=float,
        )
        units = np.maximum(1, np.rint(rng_units.normal(mean_units, params.units_cv * mean_units))).astype("int64")
        p = np.clip(
            expected_kpi_value(
                _setpoint_series(params, machine, times), params.sop_setpoint, params.baseline,
                params.sensitivity_per_c,
            ),
            0.0,
            1.0,
        )
        frame = {
            "shift_start": times,
            "shift": shift_list,
            "machine_id": machine,
            denominator: units,
            numerator: rng_count.binomial(units, p) if numerator else units,
        }
        for col, base in other_p.items():
            frame[col] = rng_count.binomial(units, min(max(base, 0.0), 1.0))
        changes = _product_changes(params, m_idx, rng_events)
        change_idx = np.searchsorted(
            np.array([c.value for c in changes], dtype="int64"), times.values.astype("int64"), side="right"
        ) if changes else np.zeros(n, dtype=int)
        frame["product_id"] = [params.products[(m_idx + int(i)) % len(params.products)] for i in change_idx]
        frame["batch_id"] = _batch_ids(params, _material_for(params, m_idx), times)
        prod_rows.append(pd.DataFrame(frame))
        event_rows.extend(_normal_events(params, m_idx, machine, rng_events, changes))
    production_log = (
        pd.concat(prod_rows, ignore_index=True).sort_values(["shift_start", "machine_id"], kind="stable")
        if prod_rows
        else empty_table("production_log")
    )
    production_log = _typed("production_log", production_log)
    kpi_log = scenario_kpi_log(production_log, params) if len(production_log) else empty_table("kpi_log")

    event_rows.extend(
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
    )
    machine_log = pd.DataFrame(event_rows, columns=list(TABLE_SCHEMAS["machine_log"]))
    if len(machine_log):
        machine_log = machine_log.sort_values(["timestamp", "machine_id"], kind="stable")

    # legacy tables (deprecated, replaced by material_batches; kept until the tools stop reading them)
    inv_rows = []
    for mat in params.materials:
        for d in dates:
            batch = f"{mat}-B{d.isocalendar().week:02d}"
            inv_rows.append((d, mat, batch, int(rng_inv.integers(500, 1500))))
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
        "production_log": production_log,
        "material_batches": _material_batches(params, rng_batch),
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
    prod = scenario.get("production", {})
    mats = scenario.get("materials", {})
    events = scenario.get("normal_events", {})
    extra: dict = {}
    if "units_mean" in prod:
        extra["units_mean"] = float(prod["units_mean"])
    if "units_cv" in prod:
        extra["units_cv"] = float(prod["units_cv"])
    if "products" in prod:
        extra["products"] = tuple(prod["products"])
    if "product_change_days" in prod:
        extra["product_change_days"] = int(prod["product_change_days"])
    if "items" in mats:
        extra["materials"] = tuple(mats["items"])
    for key, field_name, cast in (
        ("receive_every_days", "receive_every_days", int),
        ("shelf_life_days", "shelf_life_days", int),
        ("conditional_rate", "conditional_rate", float),
    ):
        if key in mats:
            extra[field_name] = cast(mats[key])
    for key, field_name in (
        ("alarms_per_machine_per_month", "alarms_per_month"),
        ("setpoint_tweaks_per_machine_per_month", "tweaks_per_month"),
        ("tweak_step", "tweak_step"),
    ):
        if key in events:
            extra[field_name] = float(events[key])
    return SimParams(
        machines=tuple(cfg.plant.machines),
        shifts=tuple(cfg.plant.shifts),
        shift_start_hours=dict(cfg.plant.shift_start_hours),
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
        machine_factor={k: float(v) for k, v in prod.get("machine_factor", {}).items()},
        shift_factor={k: float(v) for k, v in prod.get("shift_factor", {}).items()},
        kpi_columns={k.name: (k.numerator, k.denominator) for k in cfg.kpis},
        kpi_targets={k.name: float(k.target) for k in cfg.kpis},
        profile_path=str(profile_path),
        tweak_reference={k: float(v) for k, v in events.get("reference_values", {}).items()},
        limits={k: (v.min, v.max) for k, v in cfg.actions.limits.items()},
        **extra,
    )
