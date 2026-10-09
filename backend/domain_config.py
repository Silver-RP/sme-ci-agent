"""Loader + validation for the domain config (data/context_profile.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "context_profile.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KPI(_Strict):
    name: str = Field(min_length=1)
    unit: str
    target: float
    alert_threshold_sd: float = Field(gt=0)
    direction: str = Field(default="decrease", pattern="^(decrease|increase)$")  # which way is good


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
    max_log_rows: int = Field(default=50, ge=1)  # rows a log/schedule tool returns; more -> cut and flagged
    max_format_retries: int = Field(default=1, ge=0)  # times the LLM may be asked to fix an unparsable answer


class ImproveParams(_Strict):
    """Improve parameters (YAML key ``improve:``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_evidence_item_chars: int = Field(default=800, ge=100)  # size cap per evidence item in the prompt
    max_format_retries: int = Field(default=1, ge=0)  # times the LLM may be asked to fix an unparsable proposal


class ActionLimit(_Strict):
    """Allowed value range (inclusive) of one action parameter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min: float
    max: float

    @model_validator(mode="after")
    def _ordered(self) -> ActionLimit:
        if self.min > self.max:
            raise ValueError("min must be <= max")
        return self


class ActionParams(_Strict):
    """Actions a proposal may take (YAML key ``actions:``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameters: list[str] = Field(default_factory=list)  # equipment parameter names a structured action may set
    limits: dict[str, ActionLimit] = Field(default_factory=dict)  # allowed value range per parameter

    @model_validator(mode="after")
    def _limits_cover_parameters(self) -> ActionParams:
        if set(self.limits) != set(self.parameters):
            raise ValueError("actions.limits must have exactly one min/max entry per actions.parameters name")
        return self


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
    min_samples_after: int = Field(default=6, ge=1)  # fewer KPI points after the change -> "not enough evidence"


class LoopParams(_Strict):
    """Loop limits (YAML key ``loop:``) so Improve/rollback cycles end and wait for a person."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_rejections: int = Field(default=3, ge=1)  # proposals a person may reject before the run halts
    max_rollbacks: int = Field(default=2, ge=1)  # rollbacks since the last halt before the run halts
    max_total_rollbacks: int = Field(default=4, ge=1)  # rollbacks in the whole run (halts do not reset it); then only "finish"
    max_revisions: int = Field(default=3, ge=0)  # "revise" decisions allowed in a run; one more halts
    max_retries: int = Field(default=3, ge=0)  # consecutive failed /retry calls allowed per run


class SignalNames(_Strict):
    """Domain names used by tools (YAML key ``signals:``); no defaults, they belong to the YAML."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    setpoint_event: str = Field(min_length=1)
    setpoint_deviation: str = Field(min_length=1)
    batch_change: str = Field(min_length=1)


class DemoParams(_Strict):
    """What the scripted demo LLM investigates (YAML key ``demo:``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    machine_id: str = Field(min_length=1)


class DomainConfig(_Strict):
    domain: str = Field(min_length=1)
    signals: SignalNames
    demo: DemoParams
    default_period: tuple[str, str]
    actions: ActionParams = Field(default_factory=ActionParams)
    ask: AskParams = Field(default_factory=AskParams)
    measure: MeasureParams = Field(default_factory=MeasureParams)
    loop: LoopParams = Field(default_factory=LoopParams)
    detect: DetectParams = Field(default_factory=DetectParams)
    investigate: InvestigateParams = Field(default_factory=InvestigateParams)
    improve: ImproveParams = Field(default_factory=ImproveParams)
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
