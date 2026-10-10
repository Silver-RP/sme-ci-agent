"""KPI time series for the dashboard chart (R10a/dev-02). Read only.

The source is ONE function, ``load_kpi_rows``: today it reads the sandbox ``kpi_log`` table (the same one the tools
read); R10b1 changes only that function to read ``production_log``.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.detect.statistical import detect_anomalies, series_limits
from backend.domain_config import DomainConfig

MAX_POINTS = 1000  # more points than this are merged into daily means (6 months of data is ~180 days)


class SeriesError(ValueError):
    """Bad query parameter (the API turns it into 422)."""


def load_kpi_rows(tables: dict[str, pd.DataFrame], kpi: str) -> pd.DataFrame:
    """Rows (timestamp, shift, machine_id, value) of one KPI. The only place that knows where the data lives."""
    df = tables.get("kpi_log")
    if df is None or df.empty:
        return pd.DataFrame(columns=["timestamp", "shift", "machine_id", "value"])
    sub = df[df["kpi"] == kpi]
    return sub.assign(timestamp=pd.to_datetime(sub["timestamp"]))[["timestamp", "shift", "machine_id", "value"]]


def _parse(name: str, value: str | None) -> pd.Timestamp | None:
    if value is None:
        return None
    try:
        return pd.Timestamp(value)
    except (ValueError, TypeError) as e:
        raise SeriesError(f"{name} is not a date/time: {value!r}") from e


def kpi_series(
    tables: dict[str, pd.DataFrame],
    config: DomainConfig,
    kpi: str,
    machine: str | None = None,
    shift: str | None = None,
    start: str | None = None,
    end: str | None = None,
    max_points: int = MAX_POINTS,
) -> dict[str, Any]:
    """Points, baseline, upper limit and anomalies of a KPI. ``start <= ts < end`` (either optional).

    ``baseline`` / ``upper_limit`` belong to one machine, so they are null when ``machine`` is not given.
    Several machines at the same time are averaged into one point.
    """
    names = [k.name for k in config.kpis]
    if kpi not in names:
        raise SeriesError(f"unknown KPI {kpi!r}; domain config defines {sorted(names)}")
    rows = load_kpi_rows(tables, kpi)
    machines, shifts = sorted(rows["machine_id"].unique()), sorted(rows["shift"].unique())
    if machine is not None and machine not in machines:
        raise SeriesError(f"unknown machine {machine!r}; data has {machines}")
    if shift is not None and shift not in shifts:
        raise SeriesError(f"unknown shift {shift!r}; data has {shifts}")
    t_start, t_end = _parse("start", start), _parse("end", end)

    sel = rows
    if machine is not None:
        sel = sel[sel["machine_id"] == machine]
    if shift is not None:
        sel = sel[sel["shift"] == shift]
    if t_start is not None:
        sel = sel[sel["timestamp"] >= t_start]
    if t_end is not None:
        sel = sel[sel["timestamp"] < t_end]
    pts = sel.groupby("timestamp")["value"].mean().sort_index()
    if len(pts) > max_points:  # merge into daily means to keep the response small
        pts = pts.groupby(pts.index.normalize()).mean()
    points = [{"ts": ts.isoformat(), "value": round(float(v), 6)} for ts, v in pts.items()]

    baseline = upper = None
    if machine is not None:
        limits = series_limits(tables, config, kpi, machine)
        if limits is not None:
            baseline, upper = round(limits[0], 6), round(limits[2], 6)

    anomalies = []
    for a in detect_anomalies(tables, config, kpi=kpi):
        if machine is not None and a.machine_id != machine:
            continue
        if shift is not None and a.shift != shift:
            continue
        if t_start is not None and a.end < t_start:
            continue
        if t_end is not None and a.start >= t_end:
            continue
        anomalies.append(
            {"start": a.start.isoformat(), "end": a.end.isoformat(), "machine": a.machine_id, "shift": a.shift}
        )
    return {
        "kpi": kpi,
        "machine": machine,
        "shift": shift,
        "points": points,
        "baseline": baseline,
        "upper_limit": upper,
        "anomalies": anomalies,
    }
