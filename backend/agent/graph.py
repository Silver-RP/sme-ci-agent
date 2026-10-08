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
from backend.agent.nodes.act import (
    make_act_node,
    make_learn_node,
    make_loop_halt_node,
    make_measure_node,
    make_rollback_apply_node,
    make_rollback_propose_node,
    make_wait_approval_node,
    make_wait_rollback_node,
    route_after_approval,
    route_after_measure,
    route_after_rollback,
    route_after_rollback_confirm,
)
from backend.agent.nodes.ask import (
    make_ask_node,
    make_halt_node,
    make_wait_answer_node,
    route_after_investigate,
)
from backend.agent.nodes.improve import run_improvement
from backend.agent.nodes.investigate import run_investigation
from backend.agent.state import AgentState, Hypothesis, validate_hypothesis_groups
from backend.detect.statistical import detect as run_detect
from backend.domain_config import DomainConfig
from backend.tools.fake_metrics import fetch_kpi_breakdown
from backend.tools.readonly import ToolContext

DEFAULT_PERIOD = ("2026-10-01", "2026-10-07")


def build_graph(
    config: DomainConfig,
    checkpointer: Any | None = None,
    llm: LLM | None = None,
    tool_ctx: ToolContext | None = None,
    full_loop: bool = False,
):
    """Compile the graph. KPI and hypothesis groups come from `config`, not from code.

    With ``llm`` and ``tool_ctx`` Investigate is the LLM tool-use loop; without them the old mock runs.
    ``full_loop=True`` (needs both) continues after Investigate through Improve -> approval -> Act ->
    Measure -> Learn, with rollback (person confirms) back to Investigate. Default False keeps the
    graph ending after Investigate/Ask.
    """
    kpi = config.kpis[0]  # kpi type is a parameter derived from config

    def seq_of(state: AgentState, offset: int = 0) -> int:
        # derived from this run's own events, so no counter leaks between runs
        return len(state.get("events", [])) + offset + 1

    def observe(state: AgentState) -> dict[str, Any]:
        if tool_ctx is not None:
            return observe_real(state)
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

    def observe_real(state: AgentState) -> dict[str, Any]:
        """Real Detect (statistical code, no LLM) over the sandbox tables in ``tool_ctx``."""
        found = run_detect(tool_ctx.tables, config, run_id=state.get("run_id", "run_detect"))
        first = found[0]["payload"] if found else None
        ev = make_event(
            state,
            "tool_called",
            "quality",
            {"tool": "detect", "kpis": [k.name for k in config.kpis], "anomalies_found": len(found)},
            seq_of(state),
            config.domain,
        )
        evidence = {"source": "detect", "anomalies_found": len(found), "first": first}
        return {"evidence": [*state.get("evidence", []), evidence], "events": [ev]}

    def detect(state: AgentState) -> dict[str, Any]:
        obs = state["evidence"][-1]
        if tool_ctx is not None:
            first = obs.get("first")
            if first is None:  # nothing abnormal: finish cleanly, no LLM
                ev = make_event(
                    state,
                    "run_finished",
                    "system",
                    {"status": "no_anomaly", "reason": "detect found no anomaly"},
                    seq_of(state),
                    config.domain,
                )
                return {"anomaly": None, "status": "no_anomaly", "events": [ev]}
            ev = make_event(state, "anomaly_detected", "quality", dict(first), seq_of(state), config.domain)
            return {"anomaly": dict(first), "events": [ev]}
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

    if full_loop and (llm is None or tool_ctx is None):
        raise ValueError("full_loop requires both llm and tool_ctx")

    def improve(state: AgentState) -> dict[str, Any]:
        return run_improvement(state, config, llm, tool_ctx)

    g = StateGraph(AgentState)
    g.add_node("observe", observe)
    g.add_node("detect", detect)
    g.add_node("investigate", investigate)
    g.add_edge(START, "observe")
    g.add_edge("observe", "detect")
    if tool_ctx is None:
        g.add_edge("detect", "investigate")
    else:
        g.add_conditional_edges(
            "detect",
            lambda s: "investigate" if s.get("anomaly") else "end",
            {"investigate": "investigate", "end": END},
        )
    if llm is None:
        g.add_edge("investigate", END)  # legacy mock skeleton: no Ask
    else:
        g.add_node("ask", make_ask_node(config))
        g.add_node("wait_answer", make_wait_answer_node(config))
        g.add_node("halt", make_halt_node(config))
        g.add_conditional_edges(
            "investigate",
            lambda s: route_after_investigate(s, config),
            {"end": "improve" if full_loop else END, "ask": "ask", "halt": "halt"},
        )
        g.add_edge("ask", "wait_answer")
        g.add_edge("wait_answer", "investigate")
        g.add_edge("halt", END)
        if full_loop:
            _add_act_loop(g, config, tool_ctx, improve)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


def _add_act_loop(g: StateGraph, config: DomainConfig, ctx: ToolContext, improve) -> None:
    """Improve -> approval -> Act -> Measure -> Learn / rollback; all routing is rule-based (no LLM)."""
    g.add_node("improve", improve)
    g.add_node("wait_approval", make_wait_approval_node(config, ctx))
    g.add_node("act", make_act_node(config, ctx))
    g.add_node("measure", make_measure_node(config, ctx))
    g.add_node("learn", make_learn_node(config, ctx))
    g.add_node("rollback_propose", make_rollback_propose_node(config, ctx))
    g.add_node("wait_rollback", make_wait_rollback_node(config, ctx))
    g.add_node("rollback_apply", make_rollback_apply_node(config, ctx))
    g.add_node("loop_halt", make_loop_halt_node(config))
    g.add_edge("improve", "wait_approval")
    g.add_conditional_edges(
        "wait_approval",
        lambda s: route_after_approval(s, config),
        {"act": "act", "improve": "improve", "halt": "loop_halt"},
    )
    g.add_edge("act", "measure")
    g.add_conditional_edges(
        "measure",
        lambda s: route_after_measure(s, config),
        {"learn": "learn", "rollback_propose": "rollback_propose"},
    )
    g.add_edge("learn", END)
    g.add_edge("rollback_propose", "wait_rollback")
    g.add_conditional_edges(
        "wait_rollback",
        lambda s: route_after_rollback_confirm(s, config),
        {"rollback_apply": "rollback_apply", "halt": "loop_halt"},
    )
    g.add_conditional_edges(
        "rollback_apply",
        lambda s: route_after_rollback(s, config),
        {"investigate": "investigate", "halt": "loop_halt"},
    )
    g.add_edge("loop_halt", END)
