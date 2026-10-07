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
    return max(h.confidence for h in hyps) < config.ask.confidence_threshold


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


def make_wait_answer_node(config: DomainConfig):
    def wait_answer(state: AgentState) -> dict[str, Any]:
        question = next(
            (e["payload"]["question"] for e in reversed(state.get("events", [])) if e["type"] == "question_asked"),
            "",
        )
        answer = interrupt({"question": question, "run_id": state.get("run_id", "")})
        ev = make_event(
            state, "answer_received", AGENT, {"answer": answer}, len(state.get("events", [])) + 1, config.domain
        )
        evidence = [*state.get("evidence", []), {"source": "human_answer", "answer": answer}]
        return {"evidence": evidence, "events": [ev]}

    return wait_answer


def make_halt_node(config: DomainConfig):
    """Question limit reached: stop and wait for a person; never conclude by itself."""

    def halt(state: AgentState) -> dict[str, Any]:
        ev = make_event(
            state,
            "run_finished",
            "system",
            {"status": "awaiting_human", "reason": "max_questions_reached", "questions": state.get("question_count", 0)},
            len(state.get("events", [])) + 1,
            config.domain,
        )
        return {"status": "awaiting_human", "events": [ev]}

    return halt
