"""Action tools (T-023): propose_sop, apply_sop, measure, save_learning.

Rules:
- ``propose_sop`` only builds a proposal; it never touches ``sop_versions``.
- ``apply_sop`` writes a new SOP version ONLY when a human approval record is passed in. Without a
  valid approval it raises ``PermissionError`` and nothing changes. Old versions are never modified.
- ``measure`` reads ``kpi_log`` only (never ground truth). KPI is a parameter, checked against config.
- ``save_learning`` writes ``learning_store``; the domain comes from the domain config.
- Every call appends exactly one ``audit_log`` row (written first, so refused calls are logged too).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pandas as pd
from sqlalchemy.exc import IntegrityError

from backend.db import repo
from backend.db.models import SopVersion
from backend.tools.readonly import ToolContext, _audited, _check_kpi, _slice

APPROVED = "approved"


@_audited
def propose_sop(
    ctx: ToolContext,
    *,
    sop_id: str,
    new_content: str,
    rationale: str,
    kpi: str | None = None,
) -> dict:
    """Build a change proposal. Does NOT change ``sop_versions``; a human must approve it first."""
    if not sop_id or not new_content.strip():
        raise ValueError("sop_id and new_content must be non-empty")
    if kpi is not None:
        _check_kpi(ctx, kpi)
    current = repo.get_sop_version(ctx.session, sop_id)
    base = current.version if current is not None else None
    if base is None:
        base = max((s.version for s in ctx.config.sop if s.id == sop_id), default=None)
    return {
        "proposal_id": uuid.uuid4().hex[:12],
        "sop_id": sop_id,
        "base_version": base,
        "new_content": new_content,
        "rationale": rationale,
        "kpi": kpi,
        "status": "pending_approval",
    }


def _check_approval(approval: dict | None, sop_id: str, config) -> str:
    if not isinstance(approval, dict):
        raise PermissionError("apply_sop requires a human approval record")
    if approval.get("decision") != APPROVED:
        raise PermissionError("approval decision is not 'approved'")
    approver = config.resolve_approver(approval.get("approved_by"))
    if approver is None:
        raise PermissionError(
            f"approved_by {str(approval.get('approved_by') or '').strip()!r} is not a valid approver; "
            f"allowed: {', '.join(config.approvers)}"
        )
    if approval.get("sop_id") != sop_id:  # a missing sop_id is not accepted: the approval must name this SOP
        raise PermissionError("approval is for a different SOP (or names none)")
    return approver


class SopConflict(RuntimeError):
    """The SOP in force is not the version the proposal was built on (H-14): nothing was written."""

    def __init__(self, sop_id: str, base_version: int | None, current_version: int | None) -> None:
        self.sop_id, self.base_version, self.current_version = sop_id, base_version, current_version
        super().__init__(
            f"SOP {sop_id} conflict: the proposal is based on version {base_version}, "
            f"but version {current_version} is now in force; nothing was changed"
        )


_NOT_CHECKED: Any = object()


def sop_version_in_force(ctx: ToolContext, sop_id: str) -> int | None:
    """Version now in force: the newest row in ``sop_versions``, else the newest in the domain config."""
    current = repo.get_sop_version(ctx.session, sop_id)
    if current is not None:
        return current.version
    return max((s.version for s in ctx.config.sop if s.id == sop_id), default=None)


@_audited
def apply_sop(
    ctx: ToolContext,
    *,
    sop_id: str,
    new_content: str,
    approval: dict | None = None,
    base_version: Any = _NOT_CHECKED,
) -> dict:
    """Create a new SOP version (previous + 1). Refused without a human approval record.

    With ``base_version`` given (the version the proposal was built on; may be None for an unknown SOP), a different
    version in force raises ``SopConflict`` and writes nothing. A concurrent write that takes the same version number
    is also a ``SopConflict`` (unique ``(sop_id, version)``).
    """
    approver = _check_approval(approval, sop_id, ctx.config)
    if not new_content.strip():
        raise ValueError("new_content must be non-empty")
    if base_version is not _NOT_CHECKED:
        in_force = sop_version_in_force(ctx, sop_id)
        if in_force != base_version:
            raise SopConflict(sop_id, base_version, in_force)
    try:
        with ctx.session.begin_nested():
            return _write_sop_version(ctx, sop_id, new_content, approver)
    except IntegrityError as exc:
        if base_version is _NOT_CHECKED:
            raise
        raise SopConflict(sop_id, base_version, sop_version_in_force(ctx, sop_id)) from exc


def _write_sop_version(ctx: ToolContext, sop_id: str, new_content: str, approver: str) -> dict:
    if repo.get_sop_version(ctx.session, sop_id) is None:
        # First DB version of a config-defined SOP: keep the config version as the base row,
        # so the new version is base + 1 and the old content stays readable.
        base = [s for s in ctx.config.sop if s.id == sop_id]
        if base:
            top = max(base, key=lambda s: s.version)
            ctx.session.add(
                SopVersion(
                    sop_id=sop_id,
                    version=top.version,
                    content="\n".join(top.steps),
                    created_by=top.origin,
                    run_id=ctx.run_id,
                )
            )
            ctx.session.flush()
    row = repo.add_sop_version(
        ctx.session, sop_id, new_content, created_by=approver, run_id=ctx.run_id
    )
    return {"sop_id": sop_id, "version": row.version, "approved_by": approver}


def _ts(v: str | None, name: str) -> pd.Timestamp | None:
    return None if v is None else pd.Timestamp(v)


@_audited
def measure(
    ctx: ToolContext,
    *,
    kpi: str,
    change_time: str,
    window_days: int = 7,
    machine_id: str | None = None,
    started_at: str | None = None,
    detected_at: str | None = None,
    resolved_at: str | None = None,
    min_samples_after: int | None = None,
    min_units_after: int | None = None,
) -> dict:
    """KPI before/after the change, plus MTTD/MTTR.

    Pooled over units (R10b2): ``sum(numerator) / sum(denominator)`` of ``production_log`` in
    ``[change - window, change)`` vs ``[change, change + window)`` (columns from the KPI config), not a mean of
    shift ratios. ``n_before``/``n_after`` are then units (sum of the denominator). Without a usable
    ``production_log`` it falls back to the mean of ``kpi_log`` points and ``n_*`` count points.

    MTTD = detected_at - started_at; MTTR = resolved_at - detected_at (hours, None if the needed
    times are missing). Times out of order raise ``ValueError``.

    With ``min_units_after`` (or, on the ``kpi_log`` fallback, ``min_samples_after``) set, too little data is not
    an error: the result has ``sufficient: False`` and ``before``/``after``/``delta`` None (the caller decides what
    to ask). Without any threshold, an empty window raises ``ValueError``.
    """
    _check_kpi(ctx, kpi)
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    t0 = pd.Timestamp(change_time)
    w = pd.Timedelta(days=window_days)
    s, d, r = (
        _ts(started_at, "started_at"),
        _ts(detected_at, "detected_at"),
        _ts(resolved_at, "resolved_at"),
    )
    if s is not None and d is not None and d < s:
        raise ValueError("detected_at is before started_at")
    if d is not None and r is not None and r < d:
        raise ValueError("resolved_at is before detected_at")
    if s is not None and r is not None and r < s:
        raise ValueError("resolved_at is before started_at")

    kpi_cfg = next(k for k in ctx.config.kpis if k.name == kpi)
    pl = ctx.tables.get("production_log")
    pooled = (
        pl is not None
        and {kpi_cfg.numerator, kpi_cfg.denominator, "shift_start", "machine_id"} <= set(pl.columns)
    )
    if pooled:
        p = pl if machine_id is None else pl[pl["machine_id"] == machine_id]
        p = p[[kpi_cfg.numerator, kpi_cfg.denominator, "shift_start"]].copy()
        p[kpi_cfg.numerator] = pd.to_numeric(p[kpi_cfg.numerator], errors="coerce")
        p[kpi_cfg.denominator] = pd.to_numeric(p[kpi_cfg.denominator], errors="coerce")
        p = p.dropna()
        p = p[p[kpi_cfg.denominator] > 0]  # same rows as kpi_log derivation (contract 2.8)
        win_b = _slice(p, "shift_start", str(t0 - w), str(t0))
        win_a = _slice(p, "shift_start", str(t0), str(t0 + w))
        n_before = int(win_b[kpi_cfg.denominator].sum())
        n_after = int(win_a[kpi_cfg.denominator].sum())
        rate = lambda x: float(x[kpi_cfg.numerator].sum() / x[kpi_cfg.denominator].sum())
        if min_units_after is not None:
            sufficient = n_before > 0 and n_after >= max(1, min_units_after)
        elif min_samples_after is not None:
            sufficient = len(win_b) > 0 and len(win_a) >= max(1, min_samples_after)
        else:
            sufficient = True
            if n_before == 0 or n_after == 0:
                raise ValueError("no KPI data in the before or after window")
    else:
        k = ctx.tables["kpi_log"]
        k = k[k["kpi"] == kpi]
        if machine_id is not None:
            k = k[k["machine_id"] == machine_id]
        win_b = _slice(k, "timestamp", str(t0 - w), str(t0))
        win_a = _slice(k, "timestamp", str(t0), str(t0 + w))
        n_before, n_after = len(win_b), len(win_a)
        rate = lambda x: float(x["value"].mean())
        sufficient = True
        if min_samples_after is not None:
            sufficient = n_before > 0 and n_after >= max(1, min_samples_after)
        elif n_before == 0 or n_after == 0:
            raise ValueError("no KPI data in the before or after window")
    b = rate(win_b) if sufficient else None
    a = rate(win_a) if sufficient else None

    def hours(x: pd.Timestamp | None, y: pd.Timestamp | None) -> float | None:
        return None if x is None or y is None else (y - x) / pd.Timedelta(hours=1)

    return {
        "kpi": kpi,
        "machine_id": machine_id,
        "change_time": t0.isoformat(),
        "window_days": window_days,
        "before": b,
        "after": a,
        "delta": a - b if sufficient else None,
        "sufficient": sufficient,
        "n_before": n_before,
        "n_after": n_after,
        "n_unit": "units" if pooled else "points",
        "mttd_hours": hours(s, d),
        "mttr_hours": hours(d, r),
    }


@_audited
def save_learning(ctx: ToolContext, *, content: dict[str, Any]) -> dict:
    """Store a lesson in ``learning_store`` (domain from the domain config)."""
    if not isinstance(content, dict) or not content:
        raise ValueError("content must be a non-empty dict")
    row = repo.save_learning(
        ctx.session, domain=ctx.config.domain, content=content, run_id=ctx.run_id
    )
    return {"id": row.id, "domain": row.domain}


TOOLS: dict[str, Callable[..., dict]] = {
    "propose_sop": propose_sop,
    "apply_sop": apply_sop,
    "measure": measure,
    "save_learning": save_learning,
}
