"""Statistical anomaly detection (T-012). Pure code, no LLM.

Input is ONLY the sandbox tables (never ground truth).

Method, per (machine, KPI):
  1. Reference period = the first ``reference_days`` days of the data, excluding points inside
     planned-maintenance windows. Baseline = mean, sigma = sample SD of that period.
  2. Upper control limit = baseline + ``alert_threshold_sd`` * sigma. The multiplier comes from
     ``alert_threshold_sd`` of the KPI in the domain config (not from the caller).
  3. Anti-false-alarm rule: a point is "confirmed" when it is above the limit AND at least
     ``rule_hits`` of the ``rule_window`` points ending at it (default 2 of 3) are above it.
  4. Confirmed points are merged into one anomaly while the gap between consecutive confirmed
     points is at most ``max_gap`` points; the anomaly starts at the first point above the limit
     of its first confirming window and runs to the last confirmed point.
  5. Planned maintenance (``machine_log`` event_type "maintenance", paired start/end per machine)
     is removed from the series before the rule runs, so it never produces an anomaly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from backend.agent.events import make_event
from backend.domain_config import DetectParams, DomainConfig

MAINTENANCE_EVENT = "maintenance"


@dataclass(frozen=True)
class Anomaly:
    kpi: str
    machine_id: str
    start: pd.Timestamp
    end: pd.Timestamp
    n_points: int
    value: float  # mean KPI value over the anomaly points
    peak: float
    baseline: float
    sigma: float
    upper_limit: float
    shift: str


def planned_maintenance_windows(
    machine_log: pd.DataFrame, horizon_end: pd.Timestamp | None = None
) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    """Pair maintenance entries (start, end, start, end ...) per machine, in time order.

    An unpaired trailing start is open until ``horizon_end`` (or forever if None).
    """
    out: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    if machine_log is None or machine_log.empty:
        return out
    m = machine_log[machine_log["event_type"] == MAINTENANCE_EVENT]
    for machine, grp in m.groupby("machine_id"):
        ts = sorted(pd.to_datetime(grp["timestamp"]))
        wins = []
        for i in range(0, len(ts), 2):
            end = ts[i + 1] if i + 1 < len(ts) else (horizon_end or pd.Timestamp.max)
            wins.append((ts[i], end))
        out[str(machine)] = wins
    return out


def _in_windows(ts: pd.Series, wins: list[tuple[pd.Timestamp, pd.Timestamp]]) -> pd.Series:
    mask = pd.Series(False, index=ts.index)
    for s, e in wins:
        mask |= (ts >= s) & (ts < e)
    return mask


def _runs(flags: list[bool], rule_window: int, rule_hits: int, max_gap: int) -> list[tuple[int, int]]:
    """Return [(first_idx, last_idx)] of merged anomalies over a boolean exceed series."""
    confirmed: list[int] = []
    for i, f in enumerate(flags):
        if not f:
            continue
        lo = max(0, i - rule_window + 1)
        if sum(flags[lo : i + 1]) >= rule_hits:
            confirmed.append(i)
    runs: list[tuple[int, int]] = []
    for i in confirmed:
        # first exceeding point inside the confirming window
        lo = max(0, i - rule_window + 1)
        first = next(j for j in range(lo, i + 1) if flags[j])
        if runs and first - runs[-1][1] <= max_gap:
            runs[-1] = (runs[-1][0], i)
        else:
            runs.append((first, i))
    return runs


def detect_anomalies(
    tables: dict[str, pd.DataFrame],
    config: DomainConfig,
    kpi: str | None = None,
    params: DetectParams | None = None,
    threshold_sd: float | None = None,
) -> list[Anomaly]:
    """Detect anomalies in ``tables['kpi_log']``.

    ``kpi``: KPI name (default: every KPI in the config). ``threshold_sd`` overrides the config
    ``alert_threshold_sd`` (for experiments only; the default comes from the config).
    """
    params = params or config.detect  # defaults come from the domain config (YAML `detect:`)
    kpi_log = tables.get("kpi_log")
    if kpi_log is None or kpi_log.empty:
        return []
    kpis = [k for k in config.kpis if kpi is None or k.name == kpi]
    if kpi is not None and not kpis:
        raise ValueError(f"unknown KPI: {kpi}")
    machine_log = tables.get("machine_log")
    horizon_end = pd.to_datetime(kpi_log["timestamp"]).max() + pd.Timedelta(hours=1)
    windows = planned_maintenance_windows(machine_log, horizon_end)
    t0 = pd.to_datetime(kpi_log["timestamp"]).min().normalize()
    ref_end = t0 + pd.Timedelta(days=params.reference_days)

    found: list[Anomaly] = []
    for k in kpis:
        k_sd = threshold_sd if threshold_sd is not None else k.alert_threshold_sd
        sub = kpi_log[kpi_log["kpi"] == k.name]
        for machine, grp in sub.groupby("machine_id"):
            grp = grp.assign(timestamp=pd.to_datetime(grp["timestamp"])).sort_values("timestamp")
            grp = grp[~_in_windows(grp["timestamp"], windows.get(str(machine), []))]
            ref = grp[grp["timestamp"] < ref_end]["value"]
            if len(ref) < 2:
                continue
            baseline = float(ref.mean())
            sigma = float(ref.std(ddof=1))
            limit = baseline + k_sd * sigma
            flags = (grp["value"] > limit).tolist()
            # points inside the reference period are never alarms (they define "normal")
            in_ref = (grp["timestamp"] < ref_end).tolist()
            flags = [f and not r for f, r in zip(flags, in_ref, strict=True)]
            for a, b in _runs(flags, params.rule_window, params.rule_hits, params.max_gap):
                seg = grp.iloc[a : b + 1]
                above = seg[seg["value"] > limit]
                first = above.iloc[0]
                found.append(
                    Anomaly(
                        kpi=k.name,
                        machine_id=str(machine),
                        start=first["timestamp"],
                        end=seg["timestamp"].iloc[-1],
                        n_points=len(above),
                        value=float(above["value"].mean()),
                        peak=float(above["value"].max()),
                        baseline=baseline,
                        sigma=sigma,
                        upper_limit=limit,
                        shift=str(first["shift"]),
                    )
                )
    return sorted(found, key=lambda a: (a.start, a.machine_id, a.kpi))


def anomaly_events(
    anomalies: list[Anomaly], config: DomainConfig, run_id: str = "run_detect"
) -> list[dict[str, Any]]:
    """Convert anomalies to `anomaly_detected` events (docs/schema/events.json)."""
    state = {"run_id": run_id, "domain": config.domain}
    events = []
    for i, a in enumerate(anomalies, start=1):
        ev = make_event(
            state,  # type: ignore[arg-type]
            "anomaly_detected",
            "quality",
            {
                "kpi": a.kpi,
                "machine": a.machine_id,
                "shift": a.shift,
                "start": a.start.isoformat(),
                "end": a.end.isoformat(),
                "value": round(a.value, 6),
                "peak": round(a.peak, 6),
                "baseline": round(a.baseline, 6),
                "sigma": round(a.sigma, 6),
                "upper_limit": round(a.upper_limit, 6),
                "n_points": a.n_points,
                "planned": False,
            },
            i,
            config.domain,
        )
        events.append(ev)
    return events


def detect(
    tables: dict[str, pd.DataFrame],
    config: DomainConfig,
    kpi: str | None = None,
    params: DetectParams | None = None,
    threshold_sd: float | None = None,
    run_id: str = "run_detect",
) -> list[dict[str, Any]]:
    """Tables in, `anomaly_detected` events out. No ground truth parameter by design."""
    return anomaly_events(detect_anomalies(tables, config, kpi, params, threshold_sd), config, run_id)
