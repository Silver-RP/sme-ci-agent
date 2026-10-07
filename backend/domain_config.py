"""Loader + validation for the domain config (data/context_profile.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

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


class DomainConfig(_Strict):
    domain: str = Field(min_length=1)
    detect: DetectParams = Field(default_factory=DetectParams)
    kpis: list[KPI] = Field(min_length=1)
    hypothesis_groups: dict[str, list[str]] = Field(min_length=1)
    sop: list[SOP]


def load_domain_config(path: str | Path = DEFAULT_PROFILE_PATH) -> DomainConfig:
    """Load and validate the domain config. Raises pydantic.ValidationError on bad input."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return DomainConfig.model_validate(data)
