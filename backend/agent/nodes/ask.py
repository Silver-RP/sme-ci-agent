"""Ask node (T-021): ask a person when evidence is missing or confidence is low.

Split in two graph nodes so the ``question_asked`` event is checkpointed before the run pauses:
``ask`` (emit the question) -> ``wait_answer`` (LangGraph ``interrupt``; on resume emits
``answer_received``, appends the answer to evidence and the graph returns to Investigate).
Thresholds and the question limit come from the domain config.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from backend.agent.events import make_event
from backend.agent.state import AgentState
from backend.domain_config import DomainConfig

AGENT = "investigation"


def needs_question(state: AgentState, config: DomainConfig) -> bool:
    """True when Investigate flagged a gap, produced no hypothesis, or the top confidence is too low."""
    hyps = state.get("hypotheses") or []
    if state.get("evidence_gap") or not hyps:  # empty hypotheses count as missing evidence
        return True
    if max(h.confidence for h in hyps) < config.ask.confidence_threshold:
        return True
    return not has_tool_evidence(state)  # a confident conclusion with no tool result behind it is not enough


def has_tool_evidence(state: AgentState) -> bool:
    """True when at least one tool call in this run returned a result (errors do not count)."""
    return any(
        e.get("source") == "tool" and "error" not in e and "result" in e for e in state.get("evidence", [])
    )


def route_after_investigate(state: AgentState, config: DomainConfig) -> str:
    if not needs_question(state, config):
        return "end"
    if state.get("question_count", 0) >= config.ask.max_questions:
        return "halt"
    return "ask"


def _question_text(state: AgentState, config: DomainConfig) -> str:
    hyps = state.get("hypotheses") or []
    if not hyps:
        return "Evidence is insufficient to form a hypothesis. What else do you know about this anomaly?"
    top = max(hyps, key=lambda h: h.confidence)
    if top.confidence >= config.ask.confidence_threshold:  # asked only because no tool result supports it
        return (
            f"Top hypothesis ({top.group}: {top.description}) has confidence {top.confidence:.2f} but no tool "
            "result supports it. Can you confirm it or give the evidence you have?"
        )
    return (
        f"Top hypothesis ({top.group}: {top.description}) has confidence {top.confidence:.2f}, below "
        f"{config.ask.confidence_threshold:.2f}. Can you confirm or add information?"
    )


def make_ask_node(config: DomainConfig):
    def ask(state: AgentState) -> dict[str, Any]:
        count = state.get("question_count", 0) + 1
        payload = {
            "question": _question_text(state, config),
            "attempt": count,
            "max_questions": config.ask.max_questions,
        }
        ev = make_event(state, "question_asked", AGENT, payload, len(state.get("events", [])) + 1, config.domain)
        return {"question_count": count, "events": [ev], "status": ""}

    return ask


def open_question(state: AgentState) -> dict[str, Any]:
    """The question now waiting for a person: text, id (the event_id of its question_asked) and attempt (H-20)."""
    ev = next((e for e in reversed(state.get("events", [])) if e["type"] == "question_asked"), None)
    if ev is None:
        return {"question": "", "question_id": "", "attempt": 0, "run_id": state.get("run_id", "")}
    return {
        "question": ev["payload"]["question"],
        "question_id": ev["event_id"],
        "attempt": ev["payload"].get("attempt", 0),
        "run_id": state.get("run_id", ""),
    }


def make_wait_answer_node(config: DomainConfig):
    def wait_answer(state: AgentState) -> dict[str, Any]:
        answer = interrupt(open_question(state))
        ev = make_event(
            state, "answer_received", AGENT, {"answer": answer}, len(state.get("events", [])) + 1, config.domain
        )
        evidence = [*state.get("evidence", []), {"source": "human_answer", "answer": answer}]
        return {"evidence": evidence, "events": [ev]}

    return wait_answer


HALT_OPTIONS = ["investigate", "finish"]


def halt_options(state: AgentState, config: DomainConfig) -> list[str]:
    """What a person may choose at a halt: once the run's total rollbacks are used up, only to finish."""
    if state.get("rollback_total", 0) >= config.loop.max_total_rollbacks:
        return ["finish"]
    return list(HALT_OPTIONS)


def halt_payload(reason: str, options: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    """Payload of the ``question_asked`` event that stops the run for a person (resumable, not a dead end)."""
    options = list(options if options is not None else HALT_OPTIONS)
    if options == ["finish"]:
        question = f"The agent stopped ({reason}). Finish the run?"
    else:
        question = f"The agent stopped ({reason}). Investigate again (add information if you have any) or finish?"
    return {
        "kind": "halt",
        "reason": reason,
        "status": "awaiting_human",
        "question": question,
        "options": options,
        **extra,
    }


def make_halt_node(config: DomainConfig):
    """Question limit reached: stop and wait for a person (``wait_halt`` interrupts); never conclude by itself."""

    def halt(state: AgentState) -> dict[str, Any]:
        ev = make_event(
            state,
            "question_asked",
            "system",
            halt_payload("max_questions_reached", options=halt_options(state, config), questions=state.get("question_count", 0)),
            len(state.get("events", [])) + 1,
            config.domain,
        )
        return {"status": "awaiting_human", "events": [ev]}

    return halt
