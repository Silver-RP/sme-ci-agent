"""Investigate node: an LLM tool-use loop over the 4 read-only tools (T-014).

The LLM picks tools; each call becomes a ``tool_called`` event and an evidence entry. The loop ends when
the LLM replies with a final JSON answer (hypotheses) or when the step limit from the domain config
runs out; in that case the result is flagged ``evidence_gap`` so the Ask node can handle it.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from backend.agent.events import make_event
from backend.agent.llm import LLM, LLMResponse, ToolCall, ToolSpec
from backend.agent.prompts import build_system_prompt
from backend.agent.state import AgentState, Hypothesis, validate_hypothesis_groups
from backend.domain_config import DomainConfig
from backend.tools.readonly import TOOLS, ToolContext

AGENT = "investigation"

_TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        "query_logs",
        "Filter kpi_log or machine_log by KPI, machine and time window [start, end).",
        {
            "type": "object",
            "properties": {
                "kpi": {"type": "string"},
                "source": {"type": "string", "enum": ["kpi_log", "machine_log"]},
                "machine_id": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
            },
            "required": ["kpi"],
        },
    ),
    ToolSpec(
        "correlate",
        "Correlation between a machine's KPI series and a signal per hypothesis.",
        {
            "type": "object",
            "properties": {
                "kpi": {"type": "string"},
                "machine_id": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "hypotheses": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["kpi", "machine_id"],
        },
    ),
    ToolSpec(
        "get_shift_schedule",
        "Operators per date/shift/machine, with substitutes listed separately.",
        {
            "type": "object",
            "properties": {
                "machine_id": {"type": "string"},
                "shift": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
            },
        },
    ),
    ToolSpec(
        "read_sop",
        "Read a SOP by id (latest version unless a version is given).",
        {
            "type": "object",
            "properties": {"sop_id": {"type": "string"}, "version": {"type": "integer"}},
            "required": ["sop_id"],
        },
    ),
]

FINAL_FORMAT = (
    'When done, reply WITHOUT calling tools with one JSON object: {"hypotheses": [{"group": ..., '
    '"description": ..., "confidence": 0..1}], "insufficient_evidence": false}. '
    "Set insufficient_evidence to true if you cannot conclude."
)


def tool_specs() -> list[ToolSpec]:
    return list(_TOOL_SPECS)


def _parse_final(text: str, config: DomainConfig) -> tuple[list[Hypothesis], bool]:
    """Parse the final answer. Raises ValueError with a message the LLM can act on."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("final answer must be a JSON object; " + FINAL_FORMAT)
    try:
        data = json.loads(m.group(0))
        raw = data["hypotheses"]
        hyps = [Hypothesis.model_validate(h) for h in raw]
    except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as e:
        raise ValueError(f"invalid final answer ({type(e).__name__}): {e}. {FINAL_FORMAT}") from e
    validate_hypothesis_groups(hyps, config)  # ValueError for groups not in the YAML
    return sorted(hyps, key=lambda h: -h.confidence), bool(data.get("insufficient_evidence", False))


def _run_tool(call: ToolCall, ctx: ToolContext) -> tuple[bool, Any]:
    fn = TOOLS.get(call.name)
    if fn is None:
        return False, f"unknown tool {call.name!r}; available: {sorted(TOOLS)}"
    try:
        return True, fn(ctx, **call.arguments)
    except (TypeError, ValueError, KeyError) as e:
        return False, f"{type(e).__name__}: {e}"


def run_investigation(
    state: AgentState, config: DomainConfig, llm: LLM, ctx: ToolContext
) -> dict[str, Any]:
    """Run the loop and return a state update (hypotheses, evidence, events, evidence_gap)."""
    max_steps = config.investigate.max_tool_steps
    evidence = list(state.get("evidence", []))
    events: list[dict[str, Any]] = []
    base = len(state.get("events", []))

    def emit(type_: str, payload: dict[str, Any]) -> None:
        events.append(make_event(state, type_, AGENT, payload, base + len(events) + 1, config.domain))

    system = build_system_prompt(config) + "\n" + FINAL_FORMAT
    anomaly = state.get("anomaly")
    prior_answers = [e for e in evidence if e.get("source") == "human_answer"]
    user_text = f"Anomaly detected: {json.dumps(anomaly, default=str)}. Investigate."
    if prior_answers:
        user_text += " Human answers so far: " + json.dumps(prior_answers, default=str)
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_text}]

    hypotheses: list[Hypothesis] = list(state.get("hypotheses", []))
    gap = True
    for _ in range(max_steps):
        resp: LLMResponse = llm.complete(system, messages, tool_specs())
        content: list[dict[str, Any]] = []
        if resp.text:
            content.append({"type": "text", "text": resp.text})
        if not resp.tool_calls:
            try:
                hypotheses, gap = _parse_final(resp.text, config)
                break
            except ValueError as e:
                evidence.append({"source": "investigation", "error": str(e)})
                messages.append({"role": "assistant", "content": resp.text or "(empty)"})
                messages.append({"role": "user", "content": f"Rejected: {e}"})
                continue
        for c in resp.tool_calls:
            content.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments})
        messages.append({"role": "assistant", "content": content})
        results = []
        for c in resp.tool_calls:
            ok, result = _run_tool(c, ctx)
            emit("tool_called", {"tool": c.name, "arguments": c.arguments, "ok": ok})
            if ok:
                evidence.append({"source": "tool", "tool": c.name, "arguments": c.arguments, "result": result})
            else:
                evidence.append({"source": "tool", "tool": c.name, "arguments": c.arguments, "error": result})
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": c.id,
                    "content": json.dumps(result, default=str),
                    **({} if ok else {"is_error": True}),
                }
            )
        messages.append({"role": "user", "content": results})

    emit(
        "hypothesis_updated",
        {"hypotheses": [h.model_dump() for h in hypotheses], "insufficient_evidence": gap},
    )
    return {"hypotheses": hypotheses, "evidence": evidence, "events": events, "evidence_gap": gap}
