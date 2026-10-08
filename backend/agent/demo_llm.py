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

LLM_ENV = "SME_LLM"


def scripted_demo_llm(config: DomainConfig, *, ask_first: bool = True) -> ScriptedLLM:
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
        LLMResponse(tool_calls=[ToolCall(id="t1", name="correlate", arguments={"kpi": kpi.name, "machine_id": "M02"})]),
        json.dumps(
            {
                "hypotheses": [{"group": group, "description": "wrong_setpoint", "confidence": 0.8}],
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
        }
    )
    return ScriptedLLM([*([low] if ask_first else []), *investigate, improve])


def llm_from_env(config: DomainConfig) -> LLM | None:
    """The scripted LLM when ``SME_LLM=scripted``, else None (caller falls back to the real one)."""
    mode = (os.environ.get(LLM_ENV) or "").strip().lower()
    if mode == "scripted":
        return scripted_demo_llm(config)
    return None
