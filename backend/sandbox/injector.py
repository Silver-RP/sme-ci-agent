"""Anomaly injector + ground truth (T-011).

Reads ``injected_anomalies`` and ``false_positive_case`` from the scenario YAML and applies
them on top of the "normal" tables from ``simulate``.

Effect window: ``[start, end)``. When ``end`` is absent the effect lasts until the end of the
horizon (the YAML never restores the setpoint). Inside the window the KPI of the affected
machine is redrawn as ``clip(Normal(effect, noise_sd), 0, 1)`` for *all* shifts of that machine
(a changed setpoint persists across shifts).

Ground truth is returned as a separate list of ``GroundTruth`` and never written into the tables
that detect receives.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from backend.domain_config import DEFAULT_PROFILE_PATH
from backend.sandbox.schema import TABLE_NAMES
from backend.sandbox.simulator import (
    DEFAULT_SCENARIO_PATH,
    SimParams,
    _typed,
    params_from_config,
    simulate,
)

PLANNED_ROOT_CAUSE = "planned_maintenance"


@dataclass(frozen=True)
class GroundTruth:
    """Hidden truth about one injected event. Kept OUT of the tables detect reads.

    ``start``/``end`` is the effect window ``[start, end)``. ``planned`` is True for planned
    maintenance (FP1): a change in the KPI that is NOT a real anomaly.
    """

    id: str
    machine_id: str
    start: pd.Timestamp
    end: pd.Timestamp
    root_cause: str
    planned: bool
    kpi: str
    effect_value: float
    correct_fix: str = ""

    def contains(self, ts: pd.Timestamp) -> bool:
        return self.start <= ts < self.end

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "machine_id": self.machine_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "root_cause": self.root_cause,
            "planned": self.planned,
            "kpi": self.kpi,
            "effect_value": self.effect_value,
            "correct_fix": self.correct_fix,
        }


@dataclass(frozen=True)
class Dataset:
    tables: dict[str, pd.DataFrame]
    ground_truth: list[GroundTruth]


def load_scenario(path: str | Path = DEFAULT_SCENARIO_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _window(spec: dict, horizon_end: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(spec["start"])
    end = pd.Timestamp(spec["end"]) if spec.get("end") else horizon_end
    return start, end


def inject(
    tables: dict[str, pd.DataFrame], params: SimParams, scenario: dict
) -> Dataset:
    """Apply anomalies and planned maintenance from ``scenario`` to ``tables`` (not mutated)."""
    rng = np.random.default_rng([params.seed, 1])  # separate stream: normal data stays unchanged
    horizon_end = pd.Timestamp(params.start_date) + pd.Timedelta(days=params.days)
    kpi_log = tables["kpi_log"].copy()
    log_rows: list[dict] = []
    sub_operators: dict[tuple[pd.Timestamp, str, str], str] = {}
    truth: list[GroundTruth] = []

    def redraw(machine: str, start: pd.Timestamp, end: pd.Timestamp, level: float) -> None:
        mask = (
            (kpi_log["machine_id"] == machine)
            & (kpi_log["timestamp"] >= start)
            & (kpi_log["timestamp"] < end)
        )
        n = int(mask.sum())
        if n:
            kpi_log.loc[mask, "value"] = np.clip(rng.normal(level, params.noise_sd, n), 0.0, 1.0)

    for spec in scenario.get("injected_anomalies", []):
        start, end = _window(spec, horizon_end)
        machine = spec["machine"]
        level = float(spec["effect"][params.kpi])
        trace = spec.get("trace", {})
        gt = spec.get("ground_truth", {})
        redraw(machine, start, end, level)
        log_rows.append(
            {
                "timestamp": start,
                "machine_id": machine,
                "event_type": "setpoint_change",
                "parameter": trace.get("parameter", params.setpoint_param),
                "old_value": params.sop_setpoint,
                "new_value": float(trace["new_setpoint_c"]),
                "note": "setpoint changed by operator",
            }
        )
        if spec.get("end"):  # setpoint restored when the window closes
            log_rows.append(
                {
                    "timestamp": end,
                    "machine_id": machine,
                    "event_type": "setpoint_change",
                    "parameter": trace.get("parameter", params.setpoint_param),
                    "old_value": float(trace["new_setpoint_c"]),
                    "new_value": params.sop_setpoint,
                    "note": "setpoint restored",
                }
            )
        if "substitute_operator" in trace:
            shift = spec["shift"]
            first = start.normalize() - pd.Timedelta(days=int(trace.get("substitute_nights_before", 0)))
            last = start.normalize() + pd.Timedelta(days=int(trace.get("substitute_nights_after", 0)))
            for d in pd.date_range(first, last, freq="D"):
                sub_operators[(d, shift, machine)] = trace["substitute_operator"]
        truth.append(
            GroundTruth(
                id=spec["id"],
                machine_id=machine,
                start=start,
                end=end,
                root_cause=gt["root_cause"],
                planned=False,
                kpi=params.kpi,
                effect_value=level,
                correct_fix=gt.get("correct_fix", ""),
            )
        )

    fp = scenario.get("false_positive_case")
    if fp and fp.get("start"):
        start, end = _window(fp, horizon_end)
        level = float(fp["effect"][params.kpi])
        redraw(fp["machine"], start, end, level)
        # planned maintenance is part of the schedule: visible to detect as an ordinary log entry
        for ts, text in ((start, "planned maintenance start"), (end, "planned maintenance end")):
            log_rows.append(
                {
                    "timestamp": ts,
                    "machine_id": fp["machine"],
                    "event_type": "maintenance",
                    "parameter": "",
                    "old_value": np.nan,
                    "new_value": np.nan,
                    "note": text,
                }
            )
        truth.append(
            GroundTruth(
                id=fp["id"],
                machine_id=fp["machine"],
                start=start,
                end=end,
                root_cause=PLANNED_ROOT_CAUSE,
                planned=bool(fp.get("planned", True)),
                kpi=params.kpi,
                effect_value=level,
            )
        )

    machine_log = pd.concat(
        [tables["machine_log"], pd.DataFrame(log_rows, columns=tables["machine_log"].columns)],
        ignore_index=True,
    ).sort_values(["timestamp", "machine_id"], kind="stable")

    sched = tables["shift_schedule"].copy()
    for (d, shift, machine), op in sub_operators.items():
        m = (sched["date"] == d) & (sched["shift"] == shift) & (sched["machine_id"] == machine)
        sched.loc[m, "operator_id"] = op
        sched.loc[m, "is_substitute"] = True

    out = dict(tables)
    out["kpi_log"] = kpi_log
    out["machine_log"] = machine_log
    out["shift_schedule"] = sched
    out = {name: _typed(name, out[name]) for name in TABLE_NAMES}
    return Dataset(tables=out, ground_truth=truth)


def generate_dataset(
    seed: int = 42,
    scenario_path: str | Path = DEFAULT_SCENARIO_PATH,
    profile_path: str | Path = DEFAULT_PROFILE_PATH,
) -> Dataset:
    """Normal data (simulate) + injected anomalies. Ground truth is a separate output."""
    params = params_from_config(scenario_path, profile_path, seed=seed)
    return inject(simulate(params), params, load_scenario(scenario_path))
