"""Neutral agent state: anomaly, hypotheses, evidence, proposal, domain.

Names stay industry-agnostic; KPI/hypothesis groups come from the domain config.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from backend.domain_config import DomainConfig


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group: str = Field(min_length=1)  # key in hypothesis_groups of the domain config
    description: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


def validate_hypothesis_groups(hypotheses: list[Hypothesis], config: DomainConfig) -> None:
    """Raise ValueError if any hypothesis group is not a key of config.hypothesis_groups."""
    unknown = {h.group for h in hypotheses} - set(config.hypothesis_groups)
    if unknown:
        raise ValueError(f"unknown hypothesis group(s): {sorted(unknown)}")


class AgentState(TypedDict, total=False):
    run_id: str
    domain: str
    anomaly: dict[str, Any] | None
    hypotheses: list[Hypothesis]
    evidence: list[dict[str, Any]]
    proposal: dict[str, Any] | None
    evidence_gap: bool  # Investigate could not conclude; Ask should handle it
    question_count: int  # questions asked so far in this run (bounded by config.ask.max_questions)
    status: str  # "" while running; "awaiting_human" when the run stopped waiting for a person
    change_time: str  # ISO time the change takes effect; measure compares windows around it
    approval: dict[str, Any] | None  # the human decision record for the current proposal
    applied: dict[str, Any] | None  # SOP version created by Act (+ previous version, for rollback)
    measurement: dict[str, Any] | None  # last measure result + threshold verdict
    rejection_count: int
    rollback_count: int
    measure_wait_count: int  # times Measure asked a person because the after-window had too few points
    events: Annotated[list[dict[str, Any]], operator.add]


def new_state(run_id: str = "", domain: str = "") -> AgentState:
    """Empty initial state."""
    return AgentState(
        run_id=run_id,
        domain=domain,
        anomaly=None,
        hypotheses=[],
        evidence=[],
        proposal=None,
        events=[],
    )
