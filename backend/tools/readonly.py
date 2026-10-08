"""Read-only tools (T-014): query_logs, correlate, get_shift_schedule, read_sop.

Rules:
- Tools only READ the sandbox tables (in-memory DataFrames), the domain config and the
  ``sop_versions`` table. They never modify them.
- Every call appends exactly one ``audit_log`` row (action = tool name, params = call parameters)
  via ``repo.append_audit``. The row is written first, so a call that fails validation is logged too.
- Nothing here assumes a particular KPI: the KPI name is a parameter, checked against the domain config.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db import repo
from backend.db.models import SopVersion
from backend.domain_config import DomainConfig, load_domain_config

LOG_SOURCES = ("kpi_log", "machine_log")
SETPOINT_EVENT = "setpoint_change"


@dataclass
class ToolContext:
    """Everything a tool needs. ``tables`` are the 6 sandbox tables; they are never modified."""

    tables: dict[str, pd.DataFrame]
    session: Session
    config: DomainConfig = field(default_factory=load_domain_config)
    run_id: str | None = None
    actor: str = "agent"


def _audited(fn: Callable[..., dict]) -> Callable[..., dict]:
    @functools.wraps(fn)
    def wrapper(ctx: ToolContext, **params: Any) -> dict:
        repo.append_audit(
            ctx.session,
            actor=ctx.actor,
            action=fn.__name__,
            params={k: _jsonable(v) for k, v in params.items()},
            run_id=ctx.run_id,
        )
        # commit the audit row at once: a later failure (rollback of the step) must not lose it
        ctx.session.commit()
        return fn(ctx, **params)

    return wrapper


def _jsonable(v: Any) -> Any:
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def _check_kpi(ctx: ToolContext, kpi: str) -> None:
    names = {k.name for k in ctx.config.kpis}
    if kpi not in names:
        raise ValueError(f"unknown KPI {kpi!r}; domain config defines {sorted(names)}")


def _slice(
    df: pd.DataFrame, col: str, start: str | None, end: str | None
) -> pd.DataFrame:
    """Rows with ``start <= col < end`` (either bound optional). Returns a new frame."""
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= df[col] >= pd.Timestamp(start)
    if end is not None:
        mask &= df[col] < pd.Timestamp(end)
    return df.loc[mask]


def _records(df: pd.DataFrame) -> list[dict]:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].map(lambda t: None if pd.isna(t) else t.isoformat())
    out = out.astype(object).where(out.notna(), None)
    return out.to_dict(orient="records")


@_audited
def query_logs(
    ctx: ToolContext,
    *,
    kpi: str,
    source: str = "kpi_log",
    machine_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Filter a log table. ``kpi_log``: by KPI/machine/time; ``machine_log``: by machine/time.

    The window is ``[start, end)`` (ISO strings). ``kpi`` is always validated against the config.
    """
    _check_kpi(ctx, kpi)
    if source not in LOG_SOURCES:
        raise ValueError(f"source must be one of {LOG_SOURCES}")
    df = ctx.tables[source]
    if source == "kpi_log":
        df = df[df["kpi"] == kpi]
    if machine_id is not None:
        df = df[df["machine_id"] == machine_id]
    df = _slice(df, "timestamp", start, end)
    return {
        "source": source,
        "kpi": kpi,
        "machine_id": machine_id,
        "start": start,
        "end": end,
        "count": len(df),
        "rows": _records(df),
    }


@_audited
def get_shift_schedule(
    ctx: ToolContext,
    *,
    machine_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    shift: str | None = None,
) -> dict:
    """Operators per (date, shift, machine) in ``[start, end)``; lists substitutes separately."""
    df = ctx.tables["shift_schedule"]
    if machine_id is not None:
        df = df[df["machine_id"] == machine_id]
    if shift is not None:
        df = df[df["shift"] == shift]
    df = _slice(df, "date", start, end)
    subs = df[df["is_substitute"]]
    return {
        "machine_id": machine_id,
        "shift": shift,
        "start": start,
        "end": end,
        "count": len(df),
        "rows": _records(df),
        "substitutes": _records(subs),
    }


@_audited
def read_sop(ctx: ToolContext, *, sop_id: str, version: int | None = None) -> dict:
    """SOP by id and version (latest when ``version`` is None).

    Sources: ``sop`` in the domain config and the ``sop_versions`` table; on the same version the DB wins.
    """
    found: dict[int, dict] = {}
    for s in ctx.config.sop:
        if s.id == sop_id:
            found[s.version] = {
                "sop_id": s.id,
                "version": s.version,
                "title": s.title,
                "content": "\n".join(s.steps),
                "steps": list(s.steps),
                "source": "config",
            }
    rows = ctx.session.scalars(select(SopVersion).where(SopVersion.sop_id == sop_id)).all()
    for r in rows:
        found[r.version] = {
            "sop_id": r.sop_id,
            "version": r.version,
            "title": found.get(r.version, {}).get("title", ""),
            "content": r.content,
            "steps": r.content.splitlines(),
            "source": "db",
        }
    if not found:
        return {"found": False, "sop_id": sop_id, "version": version}
    chosen = max(found) if version is None else version
    if chosen not in found:
        return {
            "found": False,
            "sop_id": sop_id,
            "version": version,
            "available_versions": sorted(found),
        }
    return {"found": True, **found[chosen], "available_versions": sorted(found)}


def _pearson(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _setpoint_deviation(ctx: ToolContext, machine_id: str, times: pd.Series) -> np.ndarray | None:
    """|setpoint - reference| at each time; reference = value before the first logged change."""
    ml = ctx.tables["machine_log"]
    ch = ml[(ml["machine_id"] == machine_id) & (ml["event_type"] == SETPOINT_EVENT)].sort_values(
        "timestamp", kind="stable"
    )
    if ch.empty:
        return None
    ref = float(ch["old_value"].iloc[0])
    idx = np.searchsorted(ch["timestamp"].to_numpy(), times.to_numpy(), side="right")
    values = np.concatenate([[ref], ch["new_value"].to_numpy(dtype=float)])
    return np.abs(values[idx] - ref)


def _batch_change(ctx: ToolContext, times: pd.Series) -> np.ndarray | None:
    """1.0 on days where any material's batch differs from the previous day, else 0.0."""
    inv = ctx.tables["inventory"]
    if inv.empty:
        return None
    inv = inv.sort_values(["material_id", "date"], kind="stable")
    changed = inv["batch_id"].ne(inv.groupby("material_id")["batch_id"].shift()) & inv.groupby(
        "material_id"
    )["batch_id"].shift().notna()
    per_day = changed.groupby(inv["date"]).any().astype(float)
    return per_day.reindex(times.dt.normalize()).fillna(0.0).to_numpy()


@_audited
def correlate(
    ctx: ToolContext,
    *,
    kpi: str,
    machine_id: str,
    start: str | None = None,
    end: str | None = None,
    hypotheses: list[str] | None = None,
) -> dict:
    """Pearson correlation between the KPI series of one machine and a signal per hypothesis.

    Signals: ``wrong_setpoint`` = |setpoint - SOP value| from machine_log; ``material_batch`` =
    batch-change indicator from inventory. A hypothesis with no data in the sandbox (e.g.
    ``ambient_temperature``) gets ``status="no_data"`` and strength 0. ``hypotheses`` defaults to
    every hypothesis in the domain config. Result is ranked by |r|, strongest first.
    """
    _check_kpi(ctx, kpi)
    if hypotheses is None:
        hypotheses = [h for group in ctx.config.hypothesis_groups.values() for h in group]
    k = ctx.tables["kpi_log"]
    k = k[(k["kpi"] == kpi) & (k["machine_id"] == machine_id)]
    k = _slice(k, "timestamp", start, end).sort_values("timestamp", kind="stable")
    y = k["value"].to_numpy(dtype=float)
    times = k["timestamp"]

    signals: dict[str, Callable[[], np.ndarray | None]] = {
        "wrong_setpoint": lambda: _setpoint_deviation(ctx, machine_id, times),
        "material_batch": lambda: _batch_change(ctx, times),
    }
    results = []
    for h in hypotheses:
        sig = signals[h]() if h in signals and len(k) else None
        r = _pearson(sig, y) if sig is not None else None
        status = "no_data" if sig is None else ("ok" if r is not None else "constant")
        results.append(
            {
                "hypothesis": h,
                "r": r,
                "strength": abs(r) if r is not None else 0.0,
                "n": len(k),
                "status": status,
            }
        )
    results.sort(key=lambda d: -d["strength"])
    return {
        "kpi": kpi,
        "machine_id": machine_id,
        "start": start,
        "end": end,
        "correlations": results,
    }


TOOLS: dict[str, Callable[..., dict]] = {
    "query_logs": query_logs,
    "correlate": correlate,
    "get_shift_schedule": get_shift_schedule,
    "read_sop": read_sop,
}
