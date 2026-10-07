"""Approval, Act, Measure, Learn and rollback nodes (T-024).

Flow after Improve (conditional edges, ADR-002; no LLM is called in any node here):

    improve -> wait_approval --approved--> act -> measure --pass--> learn -> END
                    |                                  \\--fail--> rollback_propose -> wait_rollback
                    \\--rejected--> improve (or halt)                    |--confirmed--> rollback_apply -> investigate
                                                                         \\--declined--> halt

The rollback decision is a number comparison against the KPI target and tolerance read from the domain
config (``evaluate_kpi``), then a person confirms. Nodes that call ``interrupt`` hold no side effect before it
(the node re-runs from its start on resume); every tool call and decision lands in ``audit_log``.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from backend.agent.events import make_event
from backend.agent.state import AgentState
from backend.db import repo
from backend.domain_config import DomainConfig
from backend.tools.actions import apply_sop, measure, propose_sop, save_learning
from backend.tools.readonly import ToolContext

APPROVED = "approved"
REJECTED = "rejected"
NON_HUMAN = {"agent", "system", "llm"}


class DecisionError(ValueError):
    """The value a person resumed the graph with is not a valid decision."""


class _Emitter:
    """Builds consecutive events inside one node (seq continues from the events already in state)."""

    def __init__(self, state: AgentState, config: DomainConfig) -> None:
        self.state, self.config, self.events = state, config, []

    def __call__(self, type_: str, agent: str, payload: dict[str, Any]) -> None:
        seq = len(self.state.get("events", [])) + len(self.events) + 1
        self.events.append(make_event(self.state, type_, agent, payload, seq, self.config.domain))


def parse_decision(value: Any) -> dict[str, Any]:
    """Validate a human decision: ``{"decision": "approved"|"rejected", "decided_by": str, "reason"?: str}``."""
    if not isinstance(value, dict):
        raise DecisionError("decision must be an object with 'decision' and 'decided_by'")
    decision = value.get("decision")
    if decision not in (APPROVED, REJECTED):
        raise DecisionError(f"decision must be {APPROVED!r} or {REJECTED!r}, got {decision!r}")
    by = str(value.get("decided_by") or value.get("approved_by") or "").strip()
    if not by or by.lower() in NON_HUMAN:
        raise DecisionError("decision must name the human who decided (decided_by)")
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


def resolve_change_time(state: AgentState) -> str:
    """When the change takes effect: ``state['change_time']`` if given, else the end of the anomaly window
    (the sandbox clock: the fix is applied once the anomaly run ends). Raises if neither exists."""
    value = state.get("change_time") or (state.get("anomaly") or {}).get("end")
    if not value:
        raise ValueError("change_time is required: set state['change_time'] or an anomaly with an 'end' time")
    return str(value)


def route_after_approval(state: AgentState, config: DomainConfig) -> str:
    approval = state.get("approval") or {}
    if approval.get("decision") == APPROVED:
        return "act"
    if state.get("rejection_count", 0) >= config.loop.max_rejections:
        return "halt"
    return "improve"


def route_after_measure(state: AgentState, config: DomainConfig) -> str:
    return "learn" if (state.get("measurement") or {}).get("passed") else "rollback_propose"


def route_after_rollback_confirm(state: AgentState, config: DomainConfig) -> str:
    if (state.get("approval") or {}).get("decision") != APPROVED:
        return "halt"
    return "rollback_apply"


def route_after_rollback(state: AgentState, config: DomainConfig) -> str:
    return "halt" if state.get("rollback_count", 0) >= config.loop.max_rollbacks else "investigate"


def make_wait_approval_node(config: DomainConfig, ctx: ToolContext):
    def wait_approval(state: AgentState) -> dict[str, Any]:
        proposal = state.get("proposal") or {}
        if proposal.get("sop_proposal"):
            resolve_change_time(state)  # fail now, not after a person approved something that cannot be measured
        raw = interrupt({"kind": "proposal", "proposal": proposal, "run_id": state.get("run_id", "")})
        d = parse_decision(raw)
        repo.append_audit(
            ctx.session, actor=d["decided_by"], action="approval_decided",
            params={"kind": "proposal", **d}, run_id=ctx.run_id,
        )
        emit = _Emitter(state, config)
        emit("approval_decided", "system", {"kind": "proposal", **d, "change": proposal.get("change")})
        update: dict[str, Any] = {"approval": d, "events": emit.events}
        if d["decision"] == REJECTED:
            update["rejection_count"] = state.get("rejection_count", 0) + 1
            update["proposal"] = {**proposal, "status": REJECTED}
            update["evidence"] = [
                *state.get("evidence", []),
                {"source": "human_rejection", "reason": d["reason"], "rejected_change": proposal.get("change")},
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
        if not sop:
            emit("sop_applied", "improvement", {"applied": False, "reason": "proposal has no SOP change"})
            return {"applied": None, "events": emit.events}
        change_time = resolve_change_time(state)  # validate BEFORE any side effect
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
        }
        emit("sop_applied", "improvement", {"applied": True, **{k: v for k, v in applied.items() if k != "previous_content"}})
        return {"applied": applied, "events": emit.events, "proposal": {**proposal, "status": "applied"}}

    return act


def make_measure_node(config: DomainConfig, ctx: ToolContext):
    def measure_node(state: AgentState) -> dict[str, Any]:
        expected = _expected(state)
        change_time = (state.get("applied") or {}).get("change_time") or resolve_change_time(state)
        anomaly = state.get("anomaly") or {}
        res = measure(
            ctx,
            kpi=expected["kpi"],
            change_time=change_time,
            window_days=config.measure.window_days,
            machine_id=anomaly.get("machine_id") or anomaly.get("machine"),
        )
        kpi_cfg = next(k for k in config.kpis if k.name == expected["kpi"])
        passed = evaluate_kpi(res, expected["direction"], kpi_cfg.target, config.measure.tolerance)
        measurement = {
            **res,
            "direction": expected["direction"],
            "target": kpi_cfg.target,
            "tolerance": config.measure.tolerance,
            "passed": passed,
        }
        repo.append_audit(
            ctx.session, actor="system", action="kpi_threshold_check",
            params={k: measurement[k] for k in ("kpi", "after", "target", "tolerance", "direction", "passed")},
            run_id=ctx.run_id,
        )
        emit = _Emitter(state, config)
        emit("kpi_measured", "quality", measurement)
        return {"measurement": measurement, "events": emit.events}

    return measure_node


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
            "outcome": "success",
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
        raw = interrupt({"kind": "rollback", "proposal": proposal, "run_id": state.get("run_id", "")})
        d = parse_decision(raw)
        repo.append_audit(
            ctx.session, actor=d["decided_by"], action="approval_decided",
            params={"kind": "rollback", **d}, run_id=ctx.run_id,
        )
        emit = _Emitter(state, config)
        emit("approval_decided", "system", {"kind": "rollback", **d, "change": proposal.get("change")})
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
            {"source": "rollback", "reason": (state.get("measurement") or {}).get("after"), **payload},
        ]
        return {
            "events": emit.events,
            "rollback_count": count,
            "evidence": evidence,
            "proposal": None,
            "approval": None,
            "applied": None,
            "measurement": None,
            "evidence_gap": False,
        }

    return rollback_apply


def make_loop_halt_node(config: DomainConfig):
    """A loop limit was reached or a person declined a rollback: stop and wait for a person."""

    def halt(state: AgentState) -> dict[str, Any]:
        decided = state.get("approval") or {}
        if decided.get("decision") == REJECTED and (state.get("proposal") or {}).get("kind") == "rollback":
            reason = "rollback_declined"
        elif state.get("rollback_count", 0) >= config.loop.max_rollbacks:
            reason = "max_rollbacks_reached"
        else:
            reason = "max_rejections_reached"
        emit = _Emitter(state, config)
        emit("run_finished", "system", {"status": "awaiting_human", "reason": reason})
        return {"status": "awaiting_human", "events": emit.events}

    return halt
