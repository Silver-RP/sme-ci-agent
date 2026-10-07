"""Synthetic sandbox data: schemas + parameterised simulator (T-010)."""

from backend.sandbox.injector import Dataset, GroundTruth, generate_dataset, inject
from backend.sandbox.schema import TABLE_NAMES, TABLE_SCHEMAS
from backend.sandbox.simulator import (
    SetpointChange,
    SimParams,
    expected_kpi_value,
    params_from_config,
    simulate,
)

__all__ = [
    "TABLE_NAMES",
    "TABLE_SCHEMAS",
    "Dataset",
    "GroundTruth",
    "SetpointChange",
    "SimParams",
    "expected_kpi_value",
    "generate_dataset",
    "inject",
    "params_from_config",
    "simulate",
]
