"""Post-change data for one run (R8/dev-01): what the plant would log after an approved change.

Mechanism (same idea as the setpoint model in ``simulator.py``): the anomaly comes from a wrong setpoint.
When the applied change addresses that cause, the setpoint goes back to the SOP value, so the KPI of the
affected machine returns to its baseline. When it does not, the setpoint stays wrong and the KPI stays at the
anomaly level. Rows from ``change_time`` on are redrawn in a COPY of ``kpi_log``; the source tables are never
modified, and the result is a pure function of its inputs (so Measure can rebuild it from the run state).
"""

from __future__ import annotations

import zlib
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from backend.domain_config import DomainConfig, load_domain_config
from backend.sandbox.injector import load_scenario
from backend.sandbox.kpi_derive import derive_kpi_log
from backend.sandbox.simulator import DEFAULT_SCENARIO_PATH, expected_kpi_value


def mechanism_causes(scenario: Mapping[str, Any] | None = None) -> list[str]:
    """Root causes the sandbox models as a fixable mechanism (from the scenario file, not visible to the agent)."""
    scenario = scenario if scenario is not None else load_scenario(DEFAULT_SCENARIO_PATH)
    return sorted(
        {
            a["ground_truth"]["root_cause"]
            for a in scenario.get("injected_anomalies", [])
            if a.get("ground_truth", {}).get("root_cause")
        }
    )


def action_level(
    action: Mapping[str, Any] | None,
    machine_id: str | None,
    baseline: float,
    scenario: Mapping[str, Any] | None = None,
) -> float | None:
    """KPI level after a structured action, from the simulator's setpoint model; ``None`` = nothing changes.

    The action must set the modelled setpoint parameter on the affected machine. The new level is
    ``expected_kpi_value(value, SOP setpoint, baseline, sensitivity)`` (the SetpointChange mechanism of
    ``simulator.py``): the SOP value gives the baseline, a value still off the SOP keeps part of the excess.
    Any other parameter or machine leaves the anomaly where it is.
    """
    if not action or machine_id is None:
        return None
    scenario = scenario if scenario is not None else load_scenario(DEFAULT_SCENARIO_PATH)
    base = scenario.get("baseline", {})
    params = {
        a.get("trace", {}).get("parameter") for a in scenario.get("injected_anomalies", []) if a.get("trace")
    } - {None}
    param = action.get("parameter")
    if param not in params or param not in base or action.get("machine_id") != machine_id:
        return None
    try:
        value = float(action["value"])
    except (KeyError, TypeError, ValueError):
        return None
    sensitivity = float(base["setpoint_sensitivity_per_c"])
    return float(expected_kpi_value(value, float(base[param]), baseline, sensitivity))


def _seed(run_id: str, base_seed: int) -> list[int]:
    return [base_seed, 2, zlib.crc32(str(run_id).encode())]


def build_post_change_tables(
    tables: Mapping[str, pd.DataFrame],
    *,
    kpi: str,
    change_time: str | pd.Timestamp,
    machine_id: str | None,
    fixed: bool,
    baseline: float,
    noise_sd: float,
    window_days: int = 7,
    anomaly_start: str | pd.Timestamp | None = None,
    run_id: str = "",
    seed: int = 42,
    level: float | None = None,
    config: DomainConfig | None = None,
) -> dict[str, pd.DataFrame]:
    """Return new tables where the counts of ``production_log`` (machine ``machine_id``, from ``change_time`` on)
    are regenerated (binomial at the post-change level) and the ``kpi_log`` rows of ``kpi`` are derived again from them.
    Without a usable ``production_log`` the ``kpi_log`` ratios are redrawn directly.

    ``fixed=True``: level = ``baseline``. ``fixed=False``: level = mean of the machine's KPI between
    ``anomaly_start`` (or ``window_days`` before the change) and the change, i.e. the problem continues.
    ``level`` (when given) overrides both: the KPI level the structured action leads to (see ``action_level``).
    The input tables are not modified (the returned dict holds a copy of ``kpi_log``).
    """
    t0 = pd.Timestamp(change_time)
    k = tables["kpi_log"].copy()
    on_kpi = k["kpi"] == kpi
    on_machine = on_kpi if machine_id is None else on_kpi & (k["machine_id"] == machine_id)
    if level is not None:
        level = float(level)
    elif fixed:
        level = float(baseline)
    elif machine_id is None:
        level = None
    else:
        start = pd.Timestamp(anomaly_start) if anomaly_start else t0 - pd.Timedelta(days=window_days)
        past = k.loc[on_machine & (k["timestamp"] >= start) & (k["timestamp"] < t0), "value"]
        level = float(past.mean()) if len(past) else None
    mask = on_machine & (k["timestamp"] >= t0)
    out = dict(tables)
    out["kpi_log"] = k
    if level is None:
        return out
    rng = np.random.default_rng(_seed(run_id, seed))
    cfg = config if config is not None else load_domain_config()
    kpi_cfg = next((c for c in cfg.kpis if c.name == kpi), None)
    pl_src = tables.get("production_log")
    if (
        pl_src is not None and len(pl_src) and kpi_cfg is not None
        and {kpi_cfg.numerator, kpi_cfg.denominator, "shift_start", "machine_id"} <= set(pl_src.columns)
    ):
        # contract path: redraw the COUNTS after the change (binomial), then derive kpi_log from them
        pl = pl_src.copy()
        rows = (pl["shift_start"] >= t0) & ((pl["machine_id"] == machine_id) if machine_id is not None else True)
        den = pl.loc[rows, kpi_cfg.denominator].to_numpy(dtype="int64")
        if len(den):
            p = float(np.clip(level, 0.0, 1.0))
            pl.loc[rows, kpi_cfg.numerator] = rng.binomial(den, p).astype(pl[kpi_cfg.numerator].dtype)
        out["production_log"] = pl
        derived, _notes = derive_kpi_log(pl, cfg.model_copy(update={"kpis": [kpi_cfg]}))
        derived = derived.drop_duplicates(["timestamp", "machine_id"], keep="last")
        new = derived.set_index(["timestamp", "machine_id"])["value"]
        keys = pd.MultiIndex.from_frame(k.loc[mask, ["timestamp", "machine_id"]])
        vals = new.reindex(keys).to_numpy()
        old = k.loc[mask, "value"].to_numpy()
        k.loc[mask, "value"] = np.where(np.isnan(vals), old, vals)
        return out
    n = int(mask.sum())  # no production_log to regenerate counts from: redraw the ratio directly
    if n:
        k.loc[mask, "value"] = np.clip(rng.normal(level, noise_sd, n), 0.0, 1.0)
    return out
