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


def scripted_demo_llm(config: DomainConfig, *, ask_first: bool = True, then: tuple[str, ...] = ()) -> ScriptedLLM:
    """A fresh script per run (a ScriptedLLM keeps a cursor, so never share one between runs)."""
    kpi = config.kpis[0]
    group = "machine" if "machine" in config.hypothesis_groups else next(iter(config.hypothesis_groups))
    low = json.dumps(
        {
            "hypotheses": [{"group": group, "description": "unclear cause", "confidence": 0.2}],
            "insufficient_evidence": True,
        }
    )
    investigate = [
        LLMResponse(tool_calls=[ToolCall(id="t1", name="correlate", arguments={"kpi": kpi.name, "machine_id": config.demo.machine_id})]),
        json.dumps(
            {
                "hypotheses": [{"group": group, "description": config.signals.setpoint_deviation, "confidence": 0.8}],
                "insufficient_evidence": False,
            }
        ),
    ]
    sop = config.sop[0]
    improve = json.dumps(
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
                "parameter": config.actions.parameters[0],
                "machine_id": config.demo.machine_id,
                "value": load_scenario()["baseline"][config.actions.parameters[0]],  # back to the SOP value
            },
        }
    )
    # `then` lists what a person sending a proposal back needs next: "investigate" (revise / halt -> investigate:
    # Investigate + Improve again) or "improve" (reject: Improve again)
    more = {"investigate": [*investigate, improve], "improve": [improve]}
    extra = [r for step in then for r in more[step]]
    return ScriptedLLM([*([low] if ask_first else []), *investigate, improve, *extra])


def llm_from_env(config: DomainConfig) -> LLM | None:
    """The scripted LLM when ``SME_LLM=scripted``, else None (caller falls back to the real one)."""
    mode = (os.environ.get(LLM_ENV) or "").strip().lower()
    if mode == "scripted":
        return scripted_demo_llm(config)
    return None
