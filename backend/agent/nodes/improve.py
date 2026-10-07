"""Improve node (T-022): turn the top hypothesis + evidence into a change proposal.

The LLM answers with one JSON object (change, rationale, evidence_refs, expected_kpi and optionally
sop_change). The node validates it, calls ``propose_sop`` when a SOP is touched (propose only: nothing is
applied here) and emits ``proposal_created`` (agent = improvement). KPI names come from the domain config.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.agent.events import make_event
from backend.agent.llm import LLM
from backend.agent.prompts import build_system_prompt
from backend.agent.state import AgentState
from backend.domain_config import DomainConfig
from backend.tools.actions import propose_sop
from backend.tools.readonly import ToolContext

AGENT = "improvement"

FINAL_FORMAT = (
    'Reply with one JSON object: {"change": "...", "rationale": "...", "evidence_refs": [indexes into the '
    'evidence list], "expected_kpi": {"kpi": ..., "direction": "decrease"|"increase", "target": number}, '
    '"sop_change": {"sop_id": ..., "new_content": ...} (optional, only when a SOP must change)}.'
)


class ProposalError(ValueError):
    """The LLM proposal is missing a field or is inconsistent with the evidence/config."""


class ExpectedKpi(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kpi: str = Field(min_length=1)
    direction: str = Field(pattern="^(decrease|increase)$")
    target: float


class SopChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sop_id: str = Field(min_length=1)
    new_content: str = Field(min_length=1)


class ProposalDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    evidence_refs: list[int] = Field(min_length=1)
    expected_kpi: ExpectedKpi
    sop_change: SopChange | None = None


def parse_proposal(text: str, evidence: list[dict[str, Any]], config: DomainConfig) -> ProposalDraft:
    """Parse and validate the LLM answer. Raises ProposalError with a clear message."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        raise ProposalError("proposal must be a JSON object. " + FINAL_FORMAT)
    try:
        draft = ProposalDraft.model_validate(json.loads(m.group(0)))
    except json.JSONDecodeError as e:
        raise ProposalError(f"proposal is not valid JSON: {e}. {FINAL_FORMAT}") from e
    except ValidationError as e:
        fields = sorted({".".join(str(p) for p in err["loc"]) for err in e.errors()})
        raise ProposalError(f"proposal missing or invalid field(s): {fields}. {FINAL_FORMAT}") from e
    bad = [i for i in draft.evidence_refs if i < 0 or i >= len(evidence)]
    if bad:
        raise ProposalError(f"evidence_refs {bad} do not point to existing evidence (size {len(evidence)})")
    if draft.expected_kpi.kpi not in {k.name for k in config.kpis}:
        raise ProposalError(f"expected_kpi.kpi {draft.expected_kpi.kpi!r} is not a KPI in the domain config")
    if draft.sop_change and draft.sop_change.sop_id not in {s.id for s in config.sop}:
        raise ProposalError(f"sop_change.sop_id {draft.sop_change.sop_id!r} is not a known SOP")
    return draft


def run_improvement(
    state: AgentState, config: DomainConfig, llm: LLM, ctx: ToolContext
) -> dict[str, Any]:
    """Return a state update with ``proposal`` and a ``proposal_created`` event. Applies nothing."""
    hyps = state.get("hypotheses") or []
    if not hyps:
        raise ProposalError("cannot improve without a hypothesis")
    top = max(hyps, key=lambda h: h.confidence)
    evidence = list(state.get("evidence", []))
    system = build_system_prompt(config) + "\n" + FINAL_FORMAT
    user = (
        f"Anomaly: {json.dumps(state.get('anomaly'), default=str)}. "
        f"Top hypothesis: {json.dumps(top.model_dump())}. "
        f"Evidence (index: item): {json.dumps(dict(enumerate(evidence)), default=str)}. "
        "Propose an improvement."
    )
    resp = llm.complete(system, [{"role": "user", "content": user}], [])
    draft = parse_proposal(resp.text, evidence, config)

    proposal: dict[str, Any] = {
        "hypothesis": top.model_dump(),
        "change": draft.change,
        "rationale": draft.rationale,
        "evidence_refs": draft.evidence_refs,
        "expected_kpi": draft.expected_kpi.model_dump(),
        "status": "pending_approval",
        "sop_proposal": None,
    }
    if draft.sop_change:
        proposal["sop_proposal"] = propose_sop(
            ctx,
            sop_id=draft.sop_change.sop_id,
            new_content=draft.sop_change.new_content,
            rationale=draft.rationale,
            kpi=draft.expected_kpi.kpi,
        )
    ev = make_event(
        state, "proposal_created", AGENT, {"proposal": proposal}, len(state.get("events", [])) + 1, config.domain
    )
    return {"proposal": proposal, "events": [ev]}
