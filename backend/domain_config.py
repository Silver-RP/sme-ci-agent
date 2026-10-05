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


class DomainConfig(_Strict):
    domain: str = Field(min_length=1)
    kpis: list[KPI] = Field(min_length=1)
    hypothesis_groups: dict[str, list[str]] = Field(min_length=1)
    sop: list[SOP]


def load_domain_config(path: str | Path = DEFAULT_PROFILE_PATH) -> DomainConfig:
    """Load and validate the domain config. Raises pydantic.ValidationError on bad input."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return DomainConfig.model_validate(data)
