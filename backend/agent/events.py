"""Event builder following docs/schema/events.json."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.agent.state import AgentState


def make_event(
    state: AgentState,
    type_: str,
    agent: str,
    payload: dict[str, Any],
    seq: int,
    default_domain: str = "",
) -> dict[str, Any]:
    """Build an event following docs/schema/events.json."""
    return {
        "event_id": f"evt_{state.get('run_id', '')}_{seq:04d}",
        "run_id": state.get("run_id", ""),
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": type_,
        "agent": agent,
        "domain": state.get("domain") or default_domain,
        "payload": payload,
    }
