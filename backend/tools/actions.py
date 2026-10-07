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


def _check_approval(approval: dict | None, sop_id: str) -> str:
    if not isinstance(approval, dict):
        raise PermissionError("apply_sop requires a human approval record")
    if approval.get("decision") != APPROVED:
        raise PermissionError("approval decision is not 'approved'")
    approver = str(approval.get("approved_by") or "").strip()
    if not approver or approver.lower() in {"agent", "system"}:
        raise PermissionError("approval must come from a human (approved_by)")
    if approval.get("sop_id") not in (None, sop_id):
        raise PermissionError("approval is for a different SOP")
    return approver


@_audited
def apply_sop(
    ctx: ToolContext,
    *,
    sop_id: str,
    new_content: str,
    approval: dict | None = None,
) -> dict:
    """Create a new SOP version (previous + 1). Refused without a human approval record."""
    approver = _check_approval(approval, sop_id)
    if not new_content.strip():
        raise ValueError("new_content must be non-empty")
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
                    created_by="config",
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
) -> dict:
    """Mean KPI in ``[change - window, change)`` vs ``[change, change + window)``, plus MTTD/MTTR.

    MTTD = detected_at - started_at; MTTR = resolved_at - detected_at (hours, None if the needed
    times are missing). Times out of order raise ``ValueError``.
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

    k = ctx.tables["kpi_log"]
    k = k[k["kpi"] == kpi]
    if machine_id is not None:
        k = k[k["machine_id"] == machine_id]
    before = _slice(k, "timestamp", str(t0 - w), str(t0))["value"]
    after = _slice(k, "timestamp", str(t0), str(t0 + w))["value"]
    if before.empty or after.empty:
        raise ValueError("no KPI data in the before or after window")
    b, a = float(before.mean()), float(after.mean())

    def hours(x: pd.Timestamp | None, y: pd.Timestamp | None) -> float | None:
        return None if x is None or y is None else (y - x) / pd.Timedelta(hours=1)

    return {
        "kpi": kpi,
        "machine_id": machine_id,
        "change_time": t0.isoformat(),
        "window_days": window_days,
        "before": b,
        "after": a,
        "delta": a - b,
        "n_before": len(before),
        "n_after": len(after),
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
