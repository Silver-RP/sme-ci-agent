"""Agent graph skeleton: Observe -> Detect -> Investigate (mock, no LLM) -> end.

Interrupt/Postgres checkpointer come later (T-021); the checkpointer is injectable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from backend.agent.state import AgentState, Hypothesis, validate_hypothesis_groups
from backend.domain_config import DomainConfig
from backend.tools.fake_metrics import fetch_kpi_breakdown

DEFAULT_PERIOD = ("2026-10-01", "2026-10-07")


def make_event(
    state: AgentState,
    type_: str,
    agent: str,
    payload: dict[str, Any],
    seq: int,
    default_domain: str = "",
) -> dict[str, Any]:
    """Build an event following docs/schema/events.json."""
    return {
        "event_id": f"evt_{state.get('run_id', '')}_{seq:04d}",
        "run_id": state.get("run_id", ""),
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": type_,
        "agent": agent,
        "domain": state.get("domain") or default_domain,
        "payload": payload,
    }


def build_graph(config: DomainConfig, checkpointer: Any | None = None):
    """Compile the graph. KPI and hypothesis groups come from `config`, not from code."""
    kpi = config.kpis[0]  # kpi type is a parameter derived from config

    def seq_of(state: AgentState, offset: int = 0) -> int:
        # derived from this run's own events, so no counter leaks between runs
        return len(state.get("events", [])) + offset + 1

    def observe(state: AgentState) -> dict[str, Any]:
        start, end = DEFAULT_PERIOD
        data = fetch_kpi_breakdown(kpi.name, start, end)
        ev = make_event(
            state,
            "tool_called",
            "quality",
            {"tool": "fetch_kpi_breakdown", "kpi": kpi.name, "start": start, "end": end},
            seq_of(state),
            config.domain,
        )
        return {"evidence": [*state.get("evidence", []), data], "events": [ev]}

    def detect(state: AgentState) -> dict[str, Any]:
        obs = state["evidence"][-1]
        anomaly = {
            "kpi": obs["kpi"],
            "value": obs["value"],
            "baseline": obs["baseline"],
            **obs["breakdown"],
        }
        ev = make_event(state, "anomaly_detected", "quality", dict(anomaly), seq_of(state), config.domain)
        return {"anomaly": anomaly, "events": [ev]}

    def investigate(state: AgentState) -> dict[str, Any]:
        anomaly = state["anomaly"] or {}
        start, end = DEFAULT_PERIOD
        data = fetch_kpi_breakdown(anomaly["kpi"], start, end)
        group = next(iter(config.hypothesis_groups))
        cause = config.hypothesis_groups[group][0]
        hypotheses = [Hypothesis(group=group, description=f"mock: {cause}", confidence=0.5)]
        validate_hypothesis_groups(hypotheses, config)
        events = [
            make_event(
                state,
                "tool_called",
                "investigation",
                {"tool": "fetch_kpi_breakdown", "kpi": anomaly["kpi"], "start": start, "end": end},
                seq_of(state),
                config.domain,
            ),
            make_event(
                state,
                "hypothesis_updated",
                "investigation",
                {"hypotheses": [h.model_dump() for h in hypotheses]},
                seq_of(state, 1),
                config.domain,
            ),
        ]
        return {
            "hypotheses": hypotheses,
            "evidence": [*state.get("evidence", []), data],
            "events": events,
        }

    g = StateGraph(AgentState)
    g.add_node("observe", observe)
    g.add_node("detect", detect)
    g.add_node("investigate", investigate)
    g.add_edge(START, "observe")
    g.add_edge("observe", "detect")
    g.add_edge("detect", "investigate")
    g.add_edge("investigate", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())
