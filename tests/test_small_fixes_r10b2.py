"""R10b2/dev-07: H-33 (revision_count reset after a halt), H-39 (no model names in backend), parse_bool, dead code."""

import re
from pathlib import Path

import pytest

from backend.agent.jsonutil import parse_bool
from backend.agent.llm import ScriptedLLM
from tests.test_api_limits_r9 import (
    REVISE,
    approve,
    client_with,
    improve_answer,
    investigate_script,
    start,
    with_loop,
)

ROOT = Path(__file__).resolve().parents[1]


def test_h33_investigate_after_revise_halt_resets_revision_count(db_session):
    cfg = with_loop(max_revisions=1)
    cycle = [*investigate_script(), improve_answer()]
    client = client_with(db_session, ScriptedLLM([*cycle, *cycle, *cycle, *cycle]), cfg)
    rid = start(client)["run_id"]
    assert approve(client, rid, REVISE).json()["pending"]["kind"] == "proposal"  # revise 1 of 1
    halt = approve(client, rid, REVISE).json()  # revise 2 > limit
    assert halt["pending"]["kind"] == "halt" and halt["pending"]["reason"] == "max_revisions_reached"
    back = approve(client, rid, {"decision": "investigate", "decided_by": "alice"}).json()
    assert back["pending"]["kind"] == "proposal"
    # the person chose to continue: a new revise is accepted, not an instant halt
    again = approve(client, rid, REVISE).json()
    assert again["pending"]["kind"] == "proposal", again["pending"]


def test_h39_no_model_name_in_backend():
    hits = [str(f) for f in (ROOT / "backend").rglob("*.py") if re.search(r"claude-", f.read_text(encoding="utf-8"))]
    assert hits == []


def test_effort_support_comes_from_env(monkeypatch):
    from backend.agent import llm

    monkeypatch.delenv("LLM_NO_EFFORT_MODELS", raising=False)
    assert llm.supports_effort("any-model") is True
    monkeypatch.setenv("LLM_NO_EFFORT_MODELS", "small-a, small-b")
    assert llm.supports_effort("small-a-20260101") is False
    assert llm.supports_effort("small-b") is False
    assert llm.supports_effort("big-model") is True
    monkeypatch.setenv("LLM_NO_EFFORT_MODELS", "")
    assert llm.supports_effort("small-a") is True


def test_env_example_declares_no_effort_models_and_not_model_cheap():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "LLM_NO_EFFORT_MODELS" in text
    assert "MODEL_CHEAP" not in text  # nothing in backend/ reads it: removed


@pytest.mark.parametrize("bad", ["maybe", "yess", "2", 2, [], {}])
def test_parse_bool_unclear_values_raise(bad):
    with pytest.raises(ValueError):
        parse_bool(bad)


def test_parse_bool_clear_values():
    assert parse_bool("true") is True and parse_bool("No") is False and parse_bool(None, default=True) is True


def test_dead_helper_and_fixed_machine_removed():
    from backend.sandbox import post_change

    assert not hasattr(post_change, "fix_addresses_cause")
    text = (ROOT / "backend/tools/fake_metrics.py").read_text(encoding="utf-8")
    assert '"M02"' not in text
