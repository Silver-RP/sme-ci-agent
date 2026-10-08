"""Post-change data for one run (R8/dev-01): what the plant would log after an approved change.

Mechanism (same idea as the setpoint model in ``simulator.py``): the anomaly comes from a wrong setpoint.
When the applied change addresses that cause, the setpoint goes back to the SOP value, so the KPI of the
affected machine returns to its baseline. When it does not, the setpoint stays wrong and the KPI stays at the
anomaly level. Rows from ``change_time`` on are redrawn in a COPY of ``kpi_log``; the source tables are never
modified, and the result is a pure function of its inputs (so Measure can rebuild it from the run state).
"""

from __future__ import annotations

import re
import zlib
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from backend.sandbox.injector import load_scenario
from backend.sandbox.simulator import DEFAULT_SCENARIO_PATH

_GENERIC_WORDS = {"wrong", "incorrect", "bad", "unexpected"}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


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


def fix_addresses_cause(hypothesis: Mapping[str, Any] | None, scenario: Mapping[str, Any] | None = None) -> bool:
    """True when the hypothesis the change is based on names the modelled cause (e.g. a setpoint problem).

    Only the hypothesis text counts; the LLM's own claims about direction or KPI are never used.
    """
    text = _norm((hypothesis or {}).get("description", ""))
    if not text:
        return False
    compact = text.replace(" ", "")  # "set point" / "set-point" / "setpoints" still contain "setpoint"
    for cause in mechanism_causes(scenario):
        if _norm(cause) in text:
            return True
        words = [w for w in _norm(cause).split() if w not in _GENERIC_WORDS]
        if words and all(w in compact for w in words):
            return True
    return False


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
) -> dict[str, pd.DataFrame]:
    """Return new tables where ``kpi_log`` rows of ``kpi`` (for ``machine_id``) from ``change_time`` on are redrawn.

    ``fixed=True``: level = ``baseline``. ``fixed=False``: level = mean of the machine's KPI between
    ``anomaly_start`` (or ``window_days`` before the change) and the change, i.e. the problem continues.
    The input tables are not modified (the returned dict holds a copy of ``kpi_log``).
    """
    t0 = pd.Timestamp(change_time)
    k = tables["kpi_log"].copy()
    on_kpi = k["kpi"] == kpi
    on_machine = on_kpi if machine_id is None else on_kpi & (k["machine_id"] == machine_id)
    if fixed:
        level: float | None = float(baseline)
    elif machine_id is None:
        level = None
    else:
        start = pd.Timestamp(anomaly_start) if anomaly_start else t0 - pd.Timedelta(days=window_days)
        past = k.loc[on_machine & (k["timestamp"] >= start) & (k["timestamp"] < t0), "value"]
        level = float(past.mean()) if len(past) else None
    mask = on_machine & (k["timestamp"] >= t0)
    n = int(mask.sum())
    if level is not None and n:
        rng = np.random.default_rng(_seed(run_id, seed))
        k.loc[mask, "value"] = np.clip(rng.normal(level, noise_sd, n), 0.0, 1.0)
    out = dict(tables)
    out["kpi_log"] = k
    return out
