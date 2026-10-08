"""Loader + validation for the domain config (data/context_profile.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "context_profile.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KPI(_Strict):
    name: str = Field(min_length=1)
    unit: str
    target: float
    alert_threshold_sd: float = Field(gt=0)


class SOP(_Strict):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str
    steps: list[str] = Field(default_factory=list)


class DetectParams(_Strict):
    """Detect parameters (YAML key ``detect:``). The defaults here are the only place they live."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_days: int = Field(default=28, ge=1)
    rule_window: int = Field(default=3, ge=1)
    rule_hits: int = Field(default=2, ge=1)
    max_gap: int = Field(default=3, ge=0)  # points (shifts) of normal data that keep one anomaly open


class InvestigateParams(_Strict):
    """Investigate parameters (YAML key ``investigate:``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_tool_steps: int = Field(default=6, ge=1)  # max LLM rounds in one investigation


class AskParams(_Strict):
    """Ask parameters (YAML key ``ask:``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)  # top confidence below this -> ask
    max_questions: int = Field(default=2, ge=0)  # max questions per run


class MeasureParams(_Strict):
    """Measure parameters (YAML key ``measure:``): the KPI threshold that decides rollback."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    window_days: int = Field(default=7, ge=1)  # before/after window passed to the measure tool
    # KPI passes when it is within ``tolerance`` (relative) of the KPI target on the good side:
    # decrease: after <= target * (1 + tolerance); increase: after >= target * (1 - tolerance)
    tolerance: float = Field(default=0.25, ge=0.0)


class LoopParams(_Strict):
    """Loop limits (YAML key ``loop:``) so Improve/rollback cycles end and wait for a person."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_rejections: int = Field(default=3, ge=1)  # proposals a person may reject before the run halts
    max_rollbacks: int = Field(default=2, ge=1)  # rollbacks per run before the run halts


class DomainConfig(_Strict):
    domain: str = Field(min_length=1)
    ask: AskParams = Field(default_factory=AskParams)
    measure: MeasureParams = Field(default_factory=MeasureParams)
    loop: LoopParams = Field(default_factory=LoopParams)
    detect: DetectParams = Field(default_factory=DetectParams)
    investigate: InvestigateParams = Field(default_factory=InvestigateParams)
    kpis: list[KPI] = Field(min_length=1)
    hypothesis_groups: dict[str, list[str]] = Field(min_length=1)
    sop: list[SOP]
    approvers: list[str] = Field(min_length=1)  # allow-list of names allowed to approve or reject (synthetic)

    @field_validator("approvers")
    @classmethod
    def _approvers_clean(cls, v: list[str]) -> list[str]:
        cleaned = [a.strip() for a in v]
        if any(not a for a in cleaned):
            raise ValueError("approvers must not contain empty names")
        return cleaned

    def resolve_approver(self, name: object) -> str | None:
        """The one shared approver check: the configured spelling of ``name`` (trimmed, case-insensitive),
        or None when it is empty or not on the allow-list."""
        key = str(name or "").strip().lower()
        if not key:
            return None
        return next((a for a in self.approvers if a.lower() == key), None)


def load_domain_config(path: str | Path = DEFAULT_PROFILE_PATH) -> DomainConfig:
    """Load and validate the domain config. Raises pydantic.ValidationError on bad input."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return DomainConfig.model_validate(data)
