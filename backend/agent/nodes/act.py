"""Approval, Act, Measure, Learn and rollback nodes (T-024).

Flow after Improve (conditional edges, ADR-002; no LLM is called in any node here):

    improve -> wait_approval --approved--> act -> measure --pass--> learn -> END
                    |                                  \\--fail--> rollback_propose -> wait_rollback
                    \\--rejected--> improve (or halt)                    |--confirmed--> rollback_apply -> investigate
                                                                         \\--declined--> halt

Measure runs on data the sandbox simulates after ``change_time`` (copy; source tables untouched), measures the
anomaly's KPI with the good direction from the config, and with too few points answers "insufficient evidence":
measure -> ask_evidence -> wait_evidence -> measure (bounded by ``ask.max_questions``, then loop_halt).
The rollback decision is a number comparison against the KPI target and tolerance read from the domain
config (``evaluate_kpi``), then a person confirms. Nodes that call ``interrupt`` hold no side effect before it
(the node re-runs from its start on resume); every tool call and decision lands in ``audit_log``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from typing import Any

import pandas as pd
from langgraph.types import interrupt

from backend.agent.events import make_event
from backend.agent.nodes.ask import halt_options, halt_payload
from backend.agent.state import AgentState
from backend.db import repo
from backend.domain_config import DomainConfig, load_domain_config
from backend.sandbox.injector import load_scenario
from backend.sandbox.post_change import action_level, build_post_change_tables
from backend.tools.actions import apply_sop, measure, propose_sop, save_learning
from backend.tools.readonly import ToolContext

APPROVED = "approved"
REJECTED = "rejected"
MEASURED = "measured"
INSUFFICIENT = "insufficient_evidence"
NOT_APPLIED = "not_applied"
REVISE = "revise"
INVESTIGATE = "investigate"
FINISH = "finish"


class DecisionError(ValueError):
    """The value a person resumed the graph with is not a valid decision."""


class _Emitter:
    """Builds consecutive events inside one node (seq continues from the events already in state)."""

    def __init__(self, state: AgentState, config: DomainConfig) -> None:
        self.state, self.config, self.events = state, config, []

    def __call__(self, type_: str, agent: str, payload: dict[str, Any]) -> None:
        seq = len(self.state.get("events", [])) + len(self.events) + 1
        self.events.append(make_event(self.state, type_, agent, payload, seq, self.config.domain))


def proposal_fingerprint(proposal: dict[str, Any]) -> dict[str, str]:
    """Identity of what a person is asked to decide on: ``proposal_id`` and a hash of the content shown.

    The id is the proposal's own ``proposal_id`` (else its SOP proposal's, else derived from the hash); the hash
    covers the whole proposal, so an approval cannot be reused for a different (or edited) proposal.
    """
    digest = hashlib.sha256(json.dumps(proposal, sort_keys=True, default=str).encode()).hexdigest()
    pid = proposal.get("proposal_id") or (proposal.get("sop_proposal") or {}).get("proposal_id") or digest[:12]
    return {"proposal_id": str(pid), "proposal_hash": digest}


def current_sop(ctx: ToolContext, proposal: dict[str, Any]) -> dict[str, Any] | None:
    """The SOP text now in force for the SOP this proposal changes (read-only), so the person sees old -> new."""
    sop_id = (proposal.get("sop_proposal") or {}).get("sop_id")
    if not sop_id:
        return None
    row = repo.get_sop_version(ctx.session, sop_id)
    if row is not None:
        return {"sop_id": sop_id, "version": row.version, "content": row.content}
    base = [x for x in ctx.config.sop if x.id == sop_id]
    if not base:
        return None
    top = max(base, key=lambda x: x.version)
    return {"sop_id": sop_id, "version": top.version, "content": "\n".join(top.steps)}


def check_binding(raw: Any, fp: dict[str, str], kind: str) -> None:
    """If the decision names a proposal/kind (the API always does), it must match the one waiting."""
    if not isinstance(raw, dict):
        return
    for key, want in (("proposal_id", fp["proposal_id"]), ("kind", kind)):
        if raw.get(key) is not None and raw[key] != want:
            raise DecisionError(f"decision {key} {raw[key]!r} does not match the pending {want!r}")


ALLOWED_DECISIONS = {
    "proposal": (APPROVED, REJECTED, REVISE),  # revise: dispute the hypothesis / add information -> Investigate
    "rollback": (APPROVED, REJECTED),
    "halt": (INVESTIGATE, FINISH),  # a stopped run: investigate again or end it
}


def parse_decision(value: Any, config: DomainConfig | None = None, kind: str | None = None) -> dict[str, Any]:
    """Validate a human decision: ``{"decision": ..., "decided_by": str, "reason"?: str}``.

    The valid decisions depend on the ``kind`` of the pending interrupt (argument, else ``value['kind']``, else
    "proposal"). ``revise`` needs a reason: it is the feedback Investigate will receive.
    """
    if not isinstance(value, dict):
        raise DecisionError("decision must be an object with 'decision' and 'decided_by'")
    kind = kind or value.get("kind") or "proposal"
    if kind not in ALLOWED_DECISIONS:
        raise DecisionError(f"unknown decision kind {kind!r}")
    decision = value.get("decision")
    if decision not in ALLOWED_DECISIONS[kind]:
        raise DecisionError(f"decision for a {kind} must be one of {list(ALLOWED_DECISIONS[kind])}, got {decision!r}")
    if decision == REVISE and not str(value.get("reason") or "").strip():
        raise DecisionError("'revise' needs a reason: the feedback or information for the new investigation")
    config = config or load_domain_config()
    raw_by = value.get("decided_by") or value.get("approved_by")
    by = config.resolve_approver(raw_by)
    if by is None:
        raise DecisionError(
            f"decided_by {str(raw_by or '').strip()!r} is not a valid approver; allowed: {', '.join(config.approvers)}"
        )
    return {"decision": decision, "decided_by": by, "reason": str(value.get("reason") or "")}


def evaluate_kpi(measurement: dict[str, Any], direction: str, target: float, tolerance: float) -> bool:
    """Pure threshold check (no LLM): True when the KPI after the change is on the good side of the limit."""
    after = measurement["after"]
    if direction == "decrease":
        return after <= target * (1 + tolerance)
    if direction == "increase":
        return after >= target * (1 - tolerance)
    raise ValueError(f"unknown direction {direction!r}")


def _expected(state: AgentState) -> dict[str, Any]:
    return (state.get("proposal") or {})["expected_kpi"]


def validate_change_time(change_time: str, ctx: ToolContext, anomaly: dict[str, Any] | None) -> None:
    """``change_time`` must not be in the future of the data, nor before the anomaly started."""
    t = pd.Timestamp(change_time)
    last = ctx.tables["kpi_log"]["timestamp"].max()
    if pd.notna(last) and t > last:
        raise ValueError(f"change_time {change_time} is in the future: the data ends at {last.isoformat()}")
    a_start = (anomaly or {}).get("start")
    if a_start and t < pd.Timestamp(a_start):
        raise ValueError(f"change_time {change_time} is before the anomaly started ({a_start})")


def resolve_change_time(state: AgentState, ctx: ToolContext | None = None) -> str:
    """When the change takes effect: ``state['change_time']`` if given, else the end of the anomaly window
    (sandbox clock) when at least ``measure.window_days`` of data follow it, else the latest time that still
    leaves a full after-window (never before the anomaly start). With ``ctx`` the value is validated
    against the data. Raises ``ValueError`` if no time can be determined or it is invalid."""
    anomaly = state.get("anomaly") or {}
    value = state.get("change_time")
    if not value:
        value = anomaly.get("end")
        if not value:
            raise ValueError("change_time is required: set state['change_time'] or an anomaly with an 'end' time")
        if ctx is not None:
            last = ctx.tables["kpi_log"]["timestamp"].max()
            window = pd.Timedelta(days=ctx.config.measure.window_days)
            if pd.notna(last) and pd.Timestamp(value) > last - window:
                room = last - window
                if anomaly.get("start"):
                    room = max(room, pd.Timestamp(anomaly["start"]))
                value = room.isoformat()
    value = str(value)
    if ctx is not None:
        validate_change_time(value, ctx, anomaly)
    return value


def _sim_levels(kpi: str, config: DomainConfig) -> tuple[float, float]:
    """(baseline level, noise sd) the sandbox uses for ``kpi`` after a fix; from the scenario, else KPI target."""
    base = load_scenario().get("baseline", {})
    if base.get("kpi") == kpi:
        return float(base["value"]), float(base["noise_sd"])
    return next(k.target for k in config.kpis if k.name == kpi), 0.0


def _measured_kpi(state: AgentState) -> str:
    """The KPI to measure is the anomaly's KPI; the LLM's expected_kpi is only a fallback when it has none."""
    return (state.get("anomaly") or {}).get("kpi") or _expected(state)["kpi"]


def route_after_approval(state: AgentState, config: DomainConfig) -> str:
    approval = state.get("approval") or {}
    if approval.get("decision") == APPROVED:
        return "act"
    if approval.get("decision") == REVISE:
        # the person disputes the hypothesis or adds information: not a rejection; bounded by loop.max_revisions
        return "halt" if state.get("revision_count", 0) > config.loop.max_revisions else "investigate"
    if state.get("rejection_count", 0) >= config.loop.max_rejections:
        return "halt"
    return "improve"


def route_after_measure(state: AgentState, config: DomainConfig) -> str:
    m = state.get("measurement") or {}
    if m.get("status") == NOT_APPLIED:
        return "learn"  # nothing was changed: nothing to roll back, and nothing to call a success
    if m.get("status") == INSUFFICIENT:
        if state.get("measure_wait_count", 0) >= config.ask.max_questions:
            return "halt"
        return "ask_evidence"
    return "learn" if m.get("passed") else "rollback_propose"


def route_after_rollback_confirm(state: AgentState, config: DomainConfig) -> str:
    if (state.get("approval") or {}).get("decision") != APPROVED:
        return "halt"
    return "rollback_apply"


def route_after_rollback(state: AgentState, config: DomainConfig) -> str:
    if state.get("rollback_total", 0) >= config.loop.max_total_rollbacks:
        return "halt"
    return "halt" if state.get("rollback_count", 0) >= config.loop.max_rollbacks else "investigate"


def make_wait_approval_node(config: DomainConfig, ctx: ToolContext):
    def wait_approval(state: AgentState) -> dict[str, Any]:
        proposal = state.get("proposal") or {}
        if proposal.get("sop_proposal"):
            resolve_change_time(state, ctx)  # fail now, not after a person approved something that cannot be measured
        fp = proposal_fingerprint(proposal)
        raw = interrupt({"kind": "proposal", "proposal": proposal, "run_id": state.get("run_id", ""), "current_sop": current_sop(ctx, proposal), **fp})
        check_binding(raw, fp, "proposal")
        d = parse_decision(raw, config, "proposal")
        repo.append_audit(
            ctx.session, actor=d["decided_by"], action="approval_decided",
            params={"kind": "proposal", **fp, **d}, run_id=ctx.run_id,
        )
        ctx.session.commit()  # the decision is durable even if a later step fails and the API rolls back (H-07)
        emit = _Emitter(state, config)
        emit("approval_decided", "system", {"kind": "proposal", **fp, **d, "change": proposal.get("change")})
        update: dict[str, Any] = {"approval": d, "events": emit.events}
        if d["decision"] == REJECTED:
            update["rejection_count"] = state.get("rejection_count", 0) + 1
            update["proposal"] = {**proposal, "status": REJECTED}
            update["evidence"] = [
                *state.get("evidence", []),
                {"source": "human_rejection", "reason": d["reason"], "rejected_change": proposal.get("change")},
            ]
        elif d["decision"] == REVISE:
            update["revision_count"] = state.get("revision_count", 0) + 1
            update["proposal"] = {**proposal, "status": REVISE}
            update["question_count"] = 0  # new information: Investigate may ask again
            update["evidence_gap"] = False
            update["evidence"] = [
                *state.get("evidence", []),
                {"source": "human_feedback", "feedback": d["reason"], "disputed_proposal": proposal.get("change"),
                 "disputed_hypothesis": proposal.get("hypothesis")},
            ]
        else:
            update["proposal"] = {**proposal, "status": APPROVED}
        return update

    return wait_approval


def make_act_node(config: DomainConfig, ctx: ToolContext):
    def act(state: AgentState) -> dict[str, Any]:
        proposal = state.get("proposal") or {}
        approval = state.get("approval") or {}
        sop = proposal.get("sop_proposal")
        emit = _Emitter(state, config)
        # Improve already requires both; this is the second line of defence (R9i): never write a SOP that cannot
        # be measured, and never "complete" a run that changed nothing. Fails before any side effect.
        if not sop:
            raise ValueError("cannot act: the proposal has no sop_proposal (a proposal needs both a SOP change and an action)")
        if not proposal.get("action"):
            raise ValueError("cannot act: the proposal has no action, so the SOP change could not be measured; no SOP written")
        change_time = resolve_change_time(state, ctx)  # validate BEFORE any side effect
        anomaly = state.get("anomaly") or {}
        res = apply_sop(
            ctx,
            sop_id=sop["sop_id"],
            new_content=sop["new_content"],
            approval={"decision": APPROVED, "approved_by": approval.get("decided_by"), "sop_id": sop["sop_id"]},
        )
        previous = repo.get_sop_version(ctx.session, sop["sop_id"], res["version"] - 1)
        applied = {
            "sop_id": sop["sop_id"],
            "version": res["version"],
            "previous_version": previous.version if previous else None,
            "previous_content": previous.content if previous else None,
            "approved_by": res["approved_by"],
            "change_time": change_time,
            "change": proposal.get("change"),  # kept for the memory of a later rollback; not sent in the event
            "action": proposal.get("action"),  # the structured change a person approved; Measure follows this only
            "sim": {  # what the sandbox needs to produce the data after the change (rebuilt by Measure)
                "machine_id": anomaly.get("machine_id") or anomaly.get("machine"),
                "anomaly_start": anomaly.get("start"),
            },
        }
        emit("sop_applied", "improvement", {"applied": True, **{k: v for k, v in applied.items() if k not in ("previous_content", "change", "sim")}})
        return {"applied": applied, "events": emit.events, "proposal": {**proposal, "status": "applied"}}

    return act


def make_measure_node(config: DomainConfig, ctx: ToolContext):
    def measure_node(state: AgentState) -> dict[str, Any]:
        kpi = _measured_kpi(state)  # the anomaly's KPI, never the LLM's choice
        kpi_cfg = next((k for k in config.kpis if k.name == kpi), None)
        if kpi_cfg is None:
            raise ValueError(f"unknown KPI {kpi!r}; domain config defines {[k.name for k in config.kpis]}")
        direction = kpi_cfg.direction  # good direction comes from the config
        applied = state.get("applied")
        emit = _Emitter(state, config)
        base = {
            "kpi": kpi,
            "direction": direction,
            "target": kpi_cfg.target,
            "tolerance": config.measure.tolerance,
        }
        if not applied:
            measurement = {
                **base, "status": NOT_APPLIED, "passed": None, "before": None, "after": None,
                "reason": "the proposal changed no SOP, so there is nothing to measure",
            }
            emit("kpi_measured", "quality", measurement)
            return {"measurement": measurement, "events": emit.events}
        change_time = applied.get("change_time") or resolve_change_time(state, ctx)
        anomaly = state.get("anomaly") or {}
        machine = anomaly.get("machine_id") or anomaly.get("machine")
        sim = applied.get("sim")
        measure_ctx = ctx
        if sim is not None and not applied.get("action"):
            measurement = {
                **base, "status": NOT_APPLIED, "passed": None, "before": None, "after": None,
                "reason": "the proposal has no structured action, so no machine parameter was changed",
            }
            emit("kpi_measured", "quality", measurement)
            return {"measurement": measurement, "events": emit.events}
        if sim is not None:  # data after the change comes from the simulator, in a copy owned by this run
            baseline, noise_sd = _sim_levels(kpi, config)
            post = build_post_change_tables(
                ctx.tables, kpi=kpi, change_time=change_time, machine_id=sim.get("machine_id"),
                fixed=False, level=action_level(applied["action"], sim.get("machine_id"), baseline),
                baseline=baseline, noise_sd=noise_sd,
                window_days=config.measure.window_days, anomaly_start=sim.get("anomaly_start"),
                run_id=str(state.get("run_id", "")),
            )
            measure_ctx = dataclasses.replace(ctx, tables=post)
        res = measure(
            measure_ctx,
            kpi=kpi,
            change_time=change_time,
            window_days=config.measure.window_days,
            machine_id=machine,
            min_samples_after=config.measure.min_samples_after,
        )
        if not res["sufficient"]:
            measurement = {
                **res, **base, "status": INSUFFICIENT, "passed": None,
                "min_samples_after": config.measure.min_samples_after,
            }
            emit("kpi_measured", "quality", measurement)
            return {"measurement": measurement, "events": emit.events}
        passed = evaluate_kpi(res, direction, kpi_cfg.target, config.measure.tolerance)
        measurement = {**res, **base, "status": MEASURED, "passed": passed}
        repo.append_audit(
            ctx.session, actor="system", action="kpi_threshold_check",
            params={k: measurement[k] for k in ("kpi", "after", "target", "tolerance", "direction", "passed")},
            run_id=ctx.run_id,
        )
        emit("kpi_measured", "quality", measurement)
        return {"measurement": measurement, "events": emit.events}

    return measure_node


def make_ask_evidence_node(config: DomainConfig):
    """Too few KPI points after the change: say so and ask a person (no rollback, no failure)."""

    def ask_evidence(state: AgentState) -> dict[str, Any]:
        m = state.get("measurement") or {}
        count = state.get("measure_wait_count", 0) + 1
        payload = {
            "question": (
                f"Not enough evidence yet: only {m.get('n_after')} {m.get('kpi')} point(s) after the change "
                f"(need {m.get('min_samples_after')}). Wait for more data and confirm to measure again."
            ),
            "attempt": count,
            "max_questions": config.ask.max_questions,
        }
        emit = _Emitter(state, config)
        emit("question_asked", "quality", payload)
        return {"measure_wait_count": count, "events": emit.events, "status": ""}

    return ask_evidence


def make_wait_evidence_node(config: DomainConfig):
    def wait_evidence(state: AgentState) -> dict[str, Any]:
        question = next(
            (e["payload"]["question"] for e in reversed(state.get("events", [])) if e["type"] == "question_asked"), ""
        )
        answer = interrupt({"question": question, "run_id": state.get("run_id", "")})
        emit = _Emitter(state, config)
        emit("answer_received", "quality", {"answer": answer})
        return {"evidence": [*state.get("evidence", []), {"source": "human_answer", "answer": answer}], "events": emit.events}

    return wait_evidence


def make_learn_node(config: DomainConfig, ctx: ToolContext):
    def learn(state: AgentState) -> dict[str, Any]:
        proposal = state.get("proposal") or {}
        m = state.get("measurement") or {}
        applied = state.get("applied") or {}
        lesson = {
            "anomaly": state.get("anomaly"),
            "root_cause": proposal.get("hypothesis"),
            "change": proposal.get("change"),
            "rationale": proposal.get("rationale"),
            "sop_id": applied.get("sop_id"),
            "sop_version": applied.get("version"),
            "kpi": m.get("kpi"),
            "kpi_before": m.get("before"),
            "kpi_after": m.get("after"),
            "outcome": "success" if applied and m.get("passed") else "no_change",
        }
        res = save_learning(ctx, content=lesson)
        emit = _Emitter(state, config)
        emit("learning_saved", "improvement", {"learning_id": res["id"], "domain": res["domain"], "content": lesson})
        emit("run_finished", "system", {"status": "completed"})
        return {"status": "completed", "events": emit.events}

    return learn


def _fmt(value: Any) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def make_rollback_propose_node(config: DomainConfig, ctx: ToolContext):
    def rollback_propose(state: AgentState) -> dict[str, Any]:
        applied = state.get("applied")
        m = state.get("measurement") or {}
        rationale = (
            f"{m.get('kpi')} after the change is {_fmt(m.get('after'))}, outside the limit "
            f"(target {m.get('target')}, tolerance {m.get('tolerance')})."
        )
        sop_prop = None
        if applied and applied.get("previous_content"):
            sop_prop = propose_sop(
                ctx, sop_id=applied["sop_id"], new_content=applied["previous_content"],
                rationale=rationale, kpi=m.get("kpi"),
            )
        proposal = {
            "kind": "rollback",
            "proposal_id": uuid.uuid4().hex[:12],
            "change": f"Roll back SOP {applied['sop_id']} to version {applied['previous_version']}"
            if sop_prop else "Roll back the change (no SOP version to restore)",
            "rationale": rationale,
            "expected_kpi": (state.get("proposal") or {}).get("expected_kpi"),
            "status": "pending_approval",
            "sop_proposal": sop_prop,
        }
        emit = _Emitter(state, config)
        emit("proposal_created", "improvement", {"proposal": proposal})
        return {"proposal": proposal, "events": emit.events}

    return rollback_propose


def make_wait_rollback_node(config: DomainConfig, ctx: ToolContext):
    def wait_rollback(state: AgentState) -> dict[str, Any]:
        proposal = state.get("proposal") or {}
        fp = proposal_fingerprint(proposal)
        raw = interrupt({"kind": "rollback", "proposal": proposal, "run_id": state.get("run_id", ""), "current_sop": current_sop(ctx, proposal), **fp})
        check_binding(raw, fp, "rollback")
        d = parse_decision(raw, config, "rollback")
        extra: dict[str, Any] = {}
        if d["decision"] == REJECTED:  # say plainly that the SOP applied earlier is still the one in force
            applied = state.get("applied") or {}
            extra = {"sop_still_in_force": True, "sop_id": applied.get("sop_id"), "sop_version": applied.get("version")}
        repo.append_audit(
            ctx.session, actor=d["decided_by"], action="approval_decided",
            params={"kind": "rollback", **fp, **d, **extra}, run_id=ctx.run_id,
        )
        ctx.session.commit()  # durable even if a later step fails (H-07)
        emit = _Emitter(state, config)
        emit("approval_decided", "system", {"kind": "rollback", **fp, **d, **extra, "change": proposal.get("change")})
        return {"approval": d, "events": emit.events}

    return wait_rollback


def make_rollback_apply_node(config: DomainConfig, ctx: ToolContext):
    def rollback_apply(state: AgentState) -> dict[str, Any]:
        applied = state.get("applied")
        approval = state.get("approval") or {}
        emit = _Emitter(state, config)
        payload: dict[str, Any] = {"rolled_back": False, "approved_by": approval.get("decided_by")}
        if applied and applied.get("previous_content"):
            res = apply_sop(
                ctx,
                sop_id=applied["sop_id"],
                new_content=applied["previous_content"],
                approval={"decision": APPROVED, "approved_by": approval.get("decided_by"), "sop_id": applied["sop_id"]},
            )  # a NEW version holding the old content; the failed version stays in sop_versions
            payload.update(
                rolled_back=True, sop_id=applied["sop_id"], version=res["version"],
                restored_from_version=applied["previous_version"], failed_version=applied["version"],
            )
        emit("rollback_done", "improvement", payload)
        count = state.get("rollback_count", 0) + 1
        evidence = [
            *state.get("evidence", []),
            {
                "source": "rollback",
                "reason": (state.get("measurement") or {}).get("after"),
                "measurement": state.get("measurement"),
                "human_reason": approval.get("reason") or None,
                "rolled_back_change": (applied or {}).get("change"),
                **payload,
            },
        ]
        return {
            "events": emit.events,
            "rollback_count": count,
            "rollback_total": state.get("rollback_total", 0) + 1,
            "evidence": evidence,
            "proposal": None,
            "approval": None,
            "applied": None,
            "measurement": None,
            "evidence_gap": False,
            "measure_wait_count": 0,
        }

    return rollback_apply


def make_loop_halt_node(config: DomainConfig):
    """A loop limit was reached or a person declined a rollback: stop and wait for a person."""

    def halt(state: AgentState) -> dict[str, Any]:
        decided = state.get("approval") or {}
        if (state.get("measurement") or {}).get("status") == INSUFFICIENT:
            reason = "insufficient_evidence"
        elif decided.get("decision") == REJECTED and (state.get("proposal") or {}).get("kind") == "rollback":
            reason = "rollback_declined"
        elif state.get("rollback_total", 0) >= config.loop.max_total_rollbacks:
            reason = "max_total_rollbacks_reached"
        elif state.get("rollback_count", 0) >= config.loop.max_rollbacks:
            reason = "max_rollbacks_reached"
        elif decided.get("decision") == REVISE:
            reason = "max_revisions_reached"
        else:
            reason = "max_rejections_reached"
        extra: dict[str, Any] = {}
        applied = state.get("applied")
        if applied:  # an SOP version is in force (e.g. the rollback was declined): say which
            extra = {"sop_still_in_force": True, "sop_id": applied.get("sop_id"), "sop_version": applied.get("version")}
        emit = _Emitter(state, config)
        emit("question_asked", "system", halt_payload(reason, options=halt_options(state, config), **extra))
        return {"status": "awaiting_human", "events": emit.events}

    return halt


def _last_halt(state: AgentState) -> dict[str, Any]:
    return next(
        (e["payload"] for e in reversed(state.get("events", []))
         if e["type"] == "question_asked" and e["payload"].get("kind") == "halt"),
        {},
    )


def make_wait_halt_node(config: DomainConfig, ctx: ToolContext | None = None):
    """A stopped run waits for a person: ``investigate`` again (with optional information) or ``finish``.

    Shared by the question limit (Ask) and the loop limits (rejections, rollbacks, insufficient evidence). On
    ``investigate`` the counters that caused the stop restart from zero: the person chose to continue.
    """

    def wait_halt(state: AgentState) -> dict[str, Any]:
        halt = _last_halt(state)
        halt_id = "halt_" + str(sum(1 for e in state.get("events", [])
                                    if e["type"] == "question_asked" and e["payload"].get("kind") == "halt"))
        run_id = state.get("run_id", "")
        raw = interrupt({
            "kind": "halt", "proposal_id": halt_id, "run_id": run_id, "reason": halt.get("reason"),
            "question": halt.get("question"), "options": list(halt.get("options") or []),
            "sop_still_in_force": halt.get("sop_still_in_force", False),
            "sop_id": halt.get("sop_id"), "sop_version": halt.get("sop_version"),
        })
        check_binding(raw, {"proposal_id": halt_id}, "halt")
        d = parse_decision(raw, config, "halt")
        offered = list(halt.get("options") or [])
        if offered and d["decision"] not in offered:
            raise DecisionError(f"decision for this halt must be one of {offered}, got {d['decision']!r}")
        info = {k: halt[k] for k in ("sop_still_in_force", "sop_id", "sop_version") if k in halt}
        if ctx is not None:
            repo.append_audit(
                ctx.session, actor=d["decided_by"], action="halt_decided",
                params={"kind": "halt", "proposal_id": halt_id, "halt_reason": halt.get("reason"), **d, **info},
                run_id=ctx.run_id,
            )
            ctx.session.commit()  # durable even if a later step fails (H-07)
        emit = _Emitter(state, config)
        emit("approval_decided", "system",
             {"kind": "halt", "proposal_id": halt_id, "halt_reason": halt.get("reason"), **d, **info})
        if d["decision"] == FINISH:
            emit("run_finished", "system", {"status": "closed", "reason": "closed_by_human", "halt_reason": halt.get("reason")})
            return {"approval": d, "status": "closed", "events": emit.events}
        evidence = [*state.get("evidence", [])]
        evidence.append({"source": "human_feedback", "feedback": d["reason"] or None, "after_halt": halt.get("reason"), **info})
        return {
            "approval": None, "status": "", "events": emit.events, "evidence": evidence,
            "question_count": 0, "rejection_count": 0, "rollback_count": 0, "measure_wait_count": 0,
            "evidence_gap": False, "proposal": None, "applied": None, "measurement": None,
        }

    return wait_halt


def route_after_halt(state: AgentState, config: DomainConfig) -> str:
    return "end" if state.get("status") == "closed" else "investigate"
