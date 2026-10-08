"""Robust parsing of LLM answers: find a JSON object inside free text, and read booleans correctly."""

from __future__ import annotations

import json
from typing import Any

_DECODER = json.JSONDecoder()
_TRUE = {"true", "yes", "y", "1"}
_FALSE = {"false", "no", "n", "0", ""}


def extract_json_object(text: str, required_key: str | None = None) -> dict[str, Any] | None:
    """First JSON object in ``text`` (balanced braces, string-aware), or None.

    Text and stray braces around the object are ignored. When ``required_key`` is given, objects without
    that key are skipped (so a ``{...}`` in the prose before the real answer does not win).
    """
    text = text or ""
    found: dict[str, Any] | None = None
    pos = text.find("{")
    while pos != -1:
        try:
            obj, end = _DECODER.raw_decode(text, pos)
        except json.JSONDecodeError:
            obj, end = None, pos + 1
        if isinstance(obj, dict) and (required_key is None or required_key in obj):
            found = obj  # keep going: the LAST matching object is the final answer
            pos = text.find("{", end)  # skip nested objects inside this one
        else:
            pos = text.find("{", pos + 1)
    return found


def parse_bool(value: Any, default: bool = False) -> bool:
    """``"false"`` is False, ``"true"`` is True. Raises ValueError for anything unclear."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v == "":
            return True  # nothing stated = unsure: safe direction (ask the human)
        if v in _TRUE:
            return True
        if v in _FALSE:
            return False
    raise ValueError(f"cannot read {value!r} as a boolean (use true or false)")
