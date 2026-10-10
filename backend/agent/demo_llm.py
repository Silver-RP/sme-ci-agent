"""Scripted LLM for demos and end-to-end tests (no API key, no network).

Selected with the env var ``SME_LLM=scripted``. The script follows the synthetic scenario 1
(machine M02 setpoint drift): a first low-confidence answer makes the agent ask a person, then
Investigate finds the cause and Improve proposes a SOP change. KPI and SOP ids come from the domain config.
"""

from __future__ import annotations

import json
import os

from backend.agent.llm import LLM, LLMResponse, ScriptedLLM, ToolCall
from backend.domain_config import DomainConfig
from backend.sandbox.injector import load_scenario

LLM_ENV = "SME_LLM"


def _group(config: DomainConfig) -> str:
    return "machine" if "machine" in config.hypothesis_groups else next(iter(config.hypothesis_groups))


def demo_low_confidence(config: DomainConfig) -> str:
    """An Investigate answer that is unsure: the agent asks a person."""
    return json.dumps(
        {
            "hypotheses": [{"group": _group(config), "description": "unclear cause", "confidence": 0.2}],
            "insufficient_evidence": True,
        }
    )


def demo_investigate(config: DomainConfig, description: str | None = None) -> list[LLMResponse | str]:
    """One tool call, then a confident hypothesis. ``description`` defaults to the cause the simulator models."""
    kpi = config.kpis[0]
    return [
        LLMResponse(tool_calls=[ToolCall(id="t1", name="correlate", arguments={"kpi": kpi.name, "machine_id": config.demo.machine_id})]),
        json.dumps(
            {
                "hypotheses": [
                    {"group": _group(config), "description": description or config.signals.setpoint_deviation, "confidence": 0.8}
                ],
                "insufficient_evidence": False,
            }
        ),
    ]


def demo_improve(config: DomainConfig, parameter: str | None = None) -> str:
    """A proposal with an SOP change and an action. ``parameter`` defaults to the one the simulator links to the
    anomaly; any other name is a wrong fix (the KPI stays high, so Measure fails)."""
    kpi = config.kpis[0]
    sop = config.sop[0]
    right = config.actions.parameters[0]
    return json.dumps(
        {
            "change": "Restore the setpoint and add a setpoint check step to the SOP",
            "rationale": "Evidence 0 shows the defect rate follows the setpoint change",
            "evidence_refs": [0],
            "expected_kpi": {"kpi": kpi.name, "direction": "decrease", "target": kpi.target},
            "sop_change": {
                "sop_id": sop.id,
                "new_content": "Verify the setpoint.\nCheck the setpoint again after the shift change.",
            },
            "action": {
                "parameter": parameter or right,
                "machine_id": config.demo.machine_id,
                "value": load_scenario()["baseline"][right],  # back to the SOP value
            },
        }
    )


def scripted_demo_llm(config: DomainConfig, *, ask_first: bool = True, then: tuple[str, ...] = ()) -> ScriptedLLM:
    """A fresh script per run (a ScriptedLLM keeps a cursor, so never share one between runs)."""
    investigate = demo_investigate(config)
    improve = demo_improve(config)
    # `then` lists what a person sending a proposal back needs next: "investigate" (revise / halt -> investigate:
    # Investigate + Improve again) or "improve" (reject: Improve again)
    more = {"investigate": [*investigate, improve], "improve": [improve]}
    extra = [r for step in then for r in more[step]]
    return ScriptedLLM([*([demo_low_confidence(config)] if ask_first else []), *investigate, improve, *extra])


SCENARIO_ENV = "SME_DEMO_SCENARIO"
ROLLBACK_SCENARIO = "rollback"


class DemoLLM:
    """Demo LLM that answers by step, not from a fixed list, so it never runs out when a person rejects, revises
    or halts and the agent investigates / proposes again. One instance per run (it counts the steps it was asked).

    Investigate calls pass tools; Improve calls do not. The first investigation asks a person (low confidence);
    later ones are confident. With ``rollback=True`` the first proposal sets a parameter the simulator does not
    link to the anomaly, so Measure fails and the agent proposes a rollback; every later proposal is the right fix.
    """

    def __init__(self, config: DomainConfig, *, ask_first: bool = True, rollback: bool = False) -> None:
        self._config = config
        self._ask_first = ask_first
        self._rollback = rollback
        self._investigations = 0
        self._improvements = 0
        self.calls: list[dict] = []

    def complete(self, system: str, messages: list, tools: list) -> LLMResponse:
        self.calls.append({"system": system, "messages": list(messages), "tools": list(tools)})
        if tools:
            return self._investigate(messages)
        return self._improve()

    def _investigate(self, messages: list) -> LLMResponse:
        steps = demo_investigate(self._config)
        if len(messages) > 1:  # a tool result (or a format retry) came back: give the final answer
            return LLMResponse(text=steps[1])
        self._investigations += 1
        if self._ask_first and self._investigations == 1:
            return LLMResponse(text=demo_low_confidence(self._config))
        return steps[0]

    def _improve(self) -> LLMResponse:
        self._improvements += 1
        wrong = self._rollback and self._improvements == 1
        return LLMResponse(text=demo_improve(self._config, self._config.actions.parameters[-1] if wrong else None))


def llm_from_env(config: DomainConfig) -> LLM | None:
    """The demo LLM when ``SME_LLM=scripted``, else None (caller falls back to the real one).
    ``SME_DEMO_SCENARIO=rollback`` makes the first proposal fail Measure; any other value keeps the straight path."""
    mode = (os.environ.get(LLM_ENV) or "").strip().lower()
    if mode == "scripted":
        scenario = (os.environ.get(SCENARIO_ENV) or "").strip().lower()
        return DemoLLM(config, rollback=scenario == ROLLBACK_SCENARIO)
    return None
