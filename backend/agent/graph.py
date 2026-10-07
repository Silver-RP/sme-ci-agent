"""Agent graph skeleton: Observe -> Detect -> Investigate (LLM tool use, or mock when no LLM is given) -> end.

With an LLM the graph adds Ask (interrupt) after Investigate; the checkpointer is injectable
(see backend/agent/checkpoint.py for Postgres).
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from backend.agent.events import make_event
from backend.agent.llm import LLM
from backend.agent.nodes.ask import (
    make_ask_node,
    make_halt_node,
    make_wait_answer_node,
    route_after_investigate,
)
from backend.agent.nodes.investigate import run_investigation
from backend.agent.state import AgentState, Hypothesis, validate_hypothesis_groups
from backend.domain_config import DomainConfig
from backend.tools.fake_metrics import fetch_kpi_breakdown
from backend.tools.readonly import ToolContext

DEFAULT_PERIOD = ("2026-10-01", "2026-10-07")


def build_graph(
    config: DomainConfig,
    checkpointer: Any | None = None,
    llm: LLM | None = None,
    tool_ctx: ToolContext | None = None,
):
    """Compile the graph. KPI and hypothesis groups come from `config`, not from code.

    With ``llm`` and ``tool_ctx`` Investigate is the LLM tool-use loop; without them the old mock runs.
    """
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
        if llm is not None:
            if tool_ctx is None:
                raise ValueError("tool_ctx is required when llm is given")
            return run_investigation(state, config, llm, tool_ctx)
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
    if llm is None:
        g.add_edge("investigate", END)  # legacy mock skeleton: no Ask
    else:
        g.add_node("ask", make_ask_node(config))
        g.add_node("wait_answer", make_wait_answer_node(config))
        g.add_node("halt", make_halt_node(config))
        g.add_conditional_edges(
            "investigate",
            lambda s: route_after_investigate(s, config),
            {"end": END, "ask": "ask", "halt": "halt"},
        )
        g.add_edge("ask", "wait_answer")
        g.add_edge("wait_answer", "investigate")
        g.add_edge("halt", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())
