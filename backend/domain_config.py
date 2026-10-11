"""Loader + validation for the domain config (data/context_profile.yaml)."""

from __future__ import annotations

import re
import string
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.contract_defaults import DEFAULT_EVENT_TYPES

DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "context_profile.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KPI(_Strict):
    name: str = Field(min_length=1)
    unit: str
    target: float
    alert_threshold_sd: float = Field(gt=0)
    direction: str = Field(default="decrease", pattern="^(decrease|increase)$")  # which way is good
    numerator: str = Field(min_length=1)  # production_log column used as numerator (data contract 1.2)
    denominator: str = Field(default="units_produced", min_length=1)  # production_log column as denominator


class SOP(_Strict):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str
    steps: list[str] = Field(default_factory=list)
    origin: str = "config"  # who made this base version: "config" (YAML) or "import" (dataset sop.csv); = created_by


class DetectParams(_Strict):
    """Detect parameters (YAML key ``detect:``). The defaults here are the only place they live."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_days: int = Field(default=28, ge=1)
    rule_window: int = Field(default=3, ge=1)
    rule_hits: int = Field(default=2, ge=1)
    max_gap: int = Field(default=3, ge=0)  # points (shifts) of normal data that keep one anomaly open
    max_detect_delay_shifts: int = Field(default=3, ge=0)  # timeline replay: detection at most this many shifts after start


class InvestigateParams(_Strict):
    """Investigate parameters (YAML key ``investigate:``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_tool_steps: int = Field(default=6, ge=1)  # max LLM rounds in one investigation
    max_log_rows: int = Field(default=50, ge=1)  # rows a log/schedule tool returns; more -> cut and flagged
    max_format_retries: int = Field(default=1, ge=0)  # times the LLM may be asked to fix an unparsable answer
    max_lessons: int = Field(default=5, ge=0)  # earlier lessons (same KPI) shown to Investigate as context


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
    min_samples_after: int = Field(default=6, ge=1)  # kpi_log fallback (no production_log): fewer points -> "not enough evidence"
    min_units_after: int = Field(default=6000, ge=1)  # units after the change (sum of the KPI denominator) below this -> "not enough evidence"


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


class PlantParams(_Strict):
    """Plant layout (YAML key ``plant:``), data contract 1.2. machines/shifts/shift_start_hours are required."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    machines: list[str] = Field(min_length=1)
    shifts: list[str] = Field(min_length=1)
    shift_start_hours: dict[str, int]
    timezone: str = "Asia/Ho_Chi_Minh"  # IANA name; display/documentation only

    @model_validator(mode="after")
    def _hours_match_shifts(self) -> PlantParams:
        if len(set(self.shifts)) != len(self.shifts):
            raise ValueError("plant.shifts must not repeat a shift")
        if set(self.shift_start_hours) != set(self.shifts):
            raise ValueError("plant.shift_start_hours must have exactly one value per plant.shifts name")
        if any(not 0 <= h <= 23 for h in self.shift_start_hours.values()):
            raise ValueError("plant.shift_start_hours values must be 0-23")
        return self


class MachineLogParams(_Strict):
    """Machine log vocabulary (YAML key ``machine_log:``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_types: list[str] = Field(default_factory=lambda: list(DEFAULT_EVENT_TYPES), min_length=1)


class ValidateParams(_Strict):
    """Input validation thresholds (YAML key ``validate:``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_missing_shifts: int = Field(default=3, ge=1)  # consecutive empty shifts per asset before a warning
    min_monitor_days: int = Field(default=14, ge=0)  # monitoring days required after the reference period
    operator_id_pattern: str = r"^OP-[A-Z0-9]+$"
    pii_tokens: list[str] = Field(
        default_factory=lambda: [
            "name",
            "fullname",
            "email",
            "phone",
            "tel",
            "mobile",
            "address",
            "birth",
            "birthday",
            "dob",
            "cccd",
            "cmnd",
        ]
    )

    @field_validator("operator_id_pattern")
    @classmethod
    def _pattern_compiles(cls, v: str) -> str:
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"operator_id_pattern is not a valid regex: {e}") from e
        return v


HALT_REASON_CODES = (
    "insufficient_evidence",
    "rollback_declined",
    "max_total_rollbacks_reached",
    "max_rollbacks_reached",
    "max_revisions_reached",
    "max_rejections_reached",
    "max_questions_reached",
)

# Placeholders each template may use (checked at load time so a typo fails with the key name).
_MESSAGE_PLACEHOLDERS: dict[str, set[str]] = {
    "question_no_hypothesis": set(),
    "question_unsupported_hypothesis": {"group", "description", "confidence"},
    "question_low_confidence": {"group", "description", "confidence", "threshold"},
    "halt_question_finish": {"reason"},
    "halt_question_investigate": {"reason"},
    "evidence_wait_question": {"n_after", "n_unit", "kpi", "needed"},
    "rollback_change_sop": {"sop_id", "previous_version"},
    "rollback_change_no_sop": set(),
    "rollback_rationale": {"kpi", "after", "target", "tolerance"},
    "not_applied_no_sop": set(),
    "not_applied_no_action": set(),
    "sop_conflict": {"sop_id", "base_version", "current_version"},
}


class Messages(_Strict):
    """User-facing sentences (YAML key ``messages:``), templates with ``{placeholder}``. All keys are required."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_no_hypothesis: str
    question_unsupported_hypothesis: str
    question_low_confidence: str
    halt_question_finish: str
    halt_question_investigate: str
    halt_reasons: dict[str, str]
    evidence_wait_question: str
    rollback_change_sop: str
    rollback_change_no_sop: str
    rollback_rationale: str
    not_applied_no_sop: str
    not_applied_no_action: str
    sop_conflict: str

    @model_validator(mode="after")
    def _templates_ok(self) -> Messages:
        for key, allowed in _MESSAGE_PLACEHOLDERS.items():
            used = {f for _, f, _, _ in string.Formatter().parse(getattr(self, key)) if f}
            if used - allowed:
                raise ValueError(f"messages.{key} uses unknown placeholder(s) {sorted(used - allowed)}; allowed {sorted(allowed)}")
        missing = [c for c in HALT_REASON_CODES if c not in self.halt_reasons]
        if missing:
            raise ValueError(f"messages.halt_reasons is missing key(s) {missing}")
        return self

    def render(self, key: str, **params: object) -> str:
        """Fill the template ``messages.<key>`` with the given placeholder values."""
        return getattr(self, key).format(**params)

    def halt_reason_label(self, code: str) -> str:
        return self.halt_reasons.get(code, code)


UNSOURCED = "giả định, chờ D3"


class Assumption(_Strict):
    """A parameter the data does not produce (YAML key ``assumptions:``). ``alternatives`` feed the sensitivity table."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: float
    unit: str = ""
    source: str = ""  # empty = not sourced yet; shown as UNSOURCED
    alternatives: list[float] = Field(default_factory=list)  # other values tried for sensitivity (two)

    @property
    def source_label(self) -> str:
        return self.source.strip() or UNSOURCED


class DomainConfig(_Strict):
    domain: str = Field(min_length=1)
    assumptions: dict[str, Assumption] = Field(default_factory=dict)
    plant: PlantParams
    machine_log: MachineLogParams = Field(default_factory=MachineLogParams)
    validate_: ValidateParams = Field(default_factory=ValidateParams, alias="validate")
    signals: SignalNames
    demo: DemoParams
    messages: Messages
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

    @model_validator(mode="after")
    def _event_types_cover_setpoint(self) -> DomainConfig:
        if self.signals.setpoint_event not in self.machine_log.event_types:
            raise ValueError("machine_log.event_types must contain signals.setpoint_event")
        return self

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
    cfg = DomainConfig.model_validate(data)
    if Path(path) == DEFAULT_PROFILE_PATH:  # SME_DATASET: the base SOP comes from the dataset (R10b1 dev-06)
        from backend.dataset_store import apply_to_config

        cfg = apply_to_config(cfg)
    return cfg
