"""Lessons from ``learning_store`` (read only): which anomalies were already handled, and context for Investigate.

A lesson is context, never a conclusion: it does not count as tool evidence, so it cannot send a run to
Improve (the rule "no evidence from tools -> ask a person" stays in ``route_after_investigate``).
Lessons match by KPI; the machine is deliberately ignored, so a lesson about one machine can inform another.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from backend.db import repo
from backend.domain_config import DomainConfig
from backend.tools.readonly import ToolContext


def anomaly_key(anomaly: dict[str, Any] | None) -> tuple[Any, Any, Any] | None:
    """Identity of an anomaly: KPI, machine, start. None when the anomaly has none of them."""
    if not isinstance(anomaly, dict):
        return None
    key = (anomaly.get("kpi"), anomaly.get("machine"), anomaly.get("start"))
    return key if any(v is not None for v in key) else None


def _contents(ctx: ToolContext) -> list[dict[str, Any]]:
    if ctx.session is None:  # a context without a database has no lessons
        return []
    rows = repo.list_learning(ctx.session, ctx.config.domain)  # newest first
    return [r.content for r in rows if isinstance(r.content, dict)]


def handled_keys(ctx: ToolContext) -> set[tuple[Any, Any, Any]]:
    """Anomalies that already have a ``learning_saved`` lesson in this domain."""
    return {k for c in _contents(ctx) if (k := anomaly_key(c.get("anomaly"))) is not None}


SKIP_ENV = "SME_SKIP_HANDLED"  # "0"/"false": always take the first detected anomaly (repeatable demos, replays)


def skip_handled_enabled() -> bool:
    return os.environ.get(SKIP_ENV, "1").strip().lower() not in {"0", "false", "no", "off"}


def pick_unhandled(found: list[dict[str, Any]], ctx: ToolContext) -> dict[str, Any] | None:
    """First detected ``anomaly_detected`` payload that has no lesson yet (None if all were handled).

    On by default; ``SME_SKIP_HANDLED=0`` turns it off and returns the first detected anomaly.
    """
    if not skip_handled_enabled():
        return found[0]["payload"] if found else None
    done = handled_keys(ctx)
    for ev in found:
        if anomaly_key(ev["payload"]) not in done:
            return ev["payload"]
    return None


def _norm(text: Any) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip() + " "


def _claimed_signal(hyp: Any, config: DomainConfig) -> str | None:
    """The one hypothesis name (from ``hypothesis_groups``) the hypothesis claims, or None.

    Taken from a structured ``signal`` field when present; otherwise the whole description must be exactly one
    known name. Free text that merely mentions a name ("material_batch, not wrong_setpoint") claims nothing."""
    known = {n for names in config.hypothesis_groups.values() for n in names}
    raw = hyp.get("signal") or hyp.get("description", "") if isinstance(hyp, dict) else hyp or ""
    text = _norm(raw)
    matches = [n for n in known if _norm(n) == text]
    return matches[0] if len(matches) == 1 else None


def cause_status(state: dict[str, Any], config: DomainConfig) -> str:
    """``confirmed`` or ``unconfirmed`` (H-32). Confirmed only when the top hypothesis claims exactly one signal (see ``_claimed_signal``), a tool
    result of this run for that very signal (same machine as the anomaly) has |r| >= ``learn.min_cause_evidence``,
    and the action's parameter is linked to that signal in ``learn.cause_parameters``. The KPI result is checked
    by the caller (a lesson without a passed KPI is ``no_change`` anyway). Anything missing means unconfirmed."""
    proposal = state.get("proposal") or {}
    hyp = proposal.get("hypothesis")
    claimed = _claimed_signal(hyp, config)
    action = proposal.get("action")
    param = action.get("parameter") if isinstance(action, dict) else None
    machine = (state.get("anomaly") or {}).get("machine")
    for signal, params in config.learn.cause_parameters.items():
        if signal != claimed or param not in params:
            continue
        for e in state.get("evidence") or []:
            res = e.get("result")
            if e.get("source") != "tool" or e.get("tool") != "correlate" or not isinstance(res, dict):
                continue
            if machine is not None and res.get("machine_id") != machine:
                continue
            for c in res.get("correlations") or []:
                if c.get("hypothesis") == signal and c.get("status") == "ok" and (
                    float(c.get("strength") or 0.0) >= config.learn.min_cause_evidence
                ):
                    return "confirmed"
    return "unconfirmed"


def relevant_lessons(ctx: ToolContext, anomaly: dict[str, Any] | None, limit: int) -> list[dict[str, Any]]:
    """Newest lessons for the same KPI (at most ``limit``), without the machine they came from."""
    kpi = (anomaly or {}).get("kpi")
    if kpi is None or limit <= 0:
        return []
    out: list[dict[str, Any]] = []
    for c in _contents(ctx):
        if c.get("kpi") != kpi and (c.get("anomaly") or {}).get("kpi") != kpi:
            continue
        cause = c.get("root_cause") or {}
        action = (c.get("action") or {}).get("parameter") if isinstance(c.get("action"), dict) else None
        out.append({
            k: v for k, v in {
                "hypothesis_group": cause.get("group") if isinstance(cause, dict) else None,
                "root_cause": cause.get("description") if isinstance(cause, dict) else cause,
                "change": c.get("change"),
                "parameter": action,
                "outcome": c.get("outcome"),
                "cause_status": c.get("cause_status"),
                "kpi_before": c.get("kpi_before"),
                "kpi_after": c.get("kpi_after"),
            }.items() if v is not None
        })
        if len(out) >= limit:
            break
    return out


def lessons_text(lessons: list[dict[str, Any]], unconfirmed_label: str | None = None) -> str:
    """Prompt block, empty string when there are no lessons.

    A lesson with ``cause_status == "unconfirmed"`` gets ``unconfirmed_label`` (from config) as its first key.
    """
    if not lessons:
        return ""
    if unconfirmed_label:
        lessons = [
            {"label": unconfirmed_label, **x} if x.get("cause_status") == "unconfirmed" else x for x in lessons
        ]
    return (
        " Lessons from earlier runs on the same KPI (context only, NOT conclusions: they may not apply to "
        "this machine, so confirm with the tools): " + json.dumps(lessons, default=str, ensure_ascii=False)
    )
