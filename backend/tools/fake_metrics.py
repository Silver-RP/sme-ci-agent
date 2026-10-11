"""Fake read-only tool returning fixed data (no network, no DB). Replaced by real tools later."""

from __future__ import annotations

from typing import Any

_FIXED_BREAKDOWN = {"machine": "mock-machine", "shift": "mock-shift"}  # neutral placeholders, not tied to the sandbox data


def fetch_kpi_breakdown(kpi: str, start: str, end: str) -> dict[str, Any]:
    """Return a fixed KPI observation for the given KPI name and period (ISO dates)."""
    return {
        "kpi": kpi,
        "start": start,
        "end": end,
        "value": 0.062,
        "baseline": 0.02,
        "breakdown": dict(_FIXED_BREAKDOWN),
    }
