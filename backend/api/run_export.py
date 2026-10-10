"""Build the export of one run in the fixture format of docs/schema/examples/ (T-041, GET /runs/{id}/export).

Only what a client already saw is exported (the HTTP steps and the SSE events). Internal details are removed:
tracebacks, raw exception messages (an error keeps only the exception class) and any ``sim`` key (simulator truth).
"""

from __future__ import annotations

import copy
import json
from typing import Any

HIDDEN_KEYS = {"sim"}
REDACTED_ERROR = "step failed (details are in the server log)"


def _error_text(value: str) -> str:
    """'RuntimeError: 529 overloaded' -> 'RuntimeError: step failed (...)'; only a plain class name is kept."""
    head = value.split(":", 1)[0].strip()
    if head.isidentifier():
        return f"{head}: {REDACTED_ERROR}"
    return REDACTED_ERROR


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in HIDDEN_KEYS:
                continue
            out[k] = _error_text(v) if k == "error" and isinstance(v, str) else sanitize(v)
        return out
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str) and "Traceback (most recent call last)" in value:
        return REDACTED_ERROR
    return value


def build_export(run_id: str, llm_kind: str, outcome: str | None, steps: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    data = {
        "note": f"Bản ghi từ run thật, LLM {llm_kind}",
        "branch": f"recorded-{run_id}",
        "description": f"Run {run_id} ghi lại qua API (kết quả: {outcome or 'chưa xong'}).",
        "steps": copy.deepcopy(steps),
        "events": copy.deepcopy(events),
    }
    return sanitize(json.loads(json.dumps(data)))
