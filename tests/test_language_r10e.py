"""R10e/dev-02: the LLM writes display fields in ui.language; DemoLLM strings come from demo.texts."""

import json
import re
from functools import cache
from pathlib import Path

import pytest

from backend.agent.demo_llm import DemoLLM, demo_improve, demo_low_confidence
from backend.agent.nodes.improve import run_improvement
from backend.agent.nodes.investigate import run_investigation
from backend.agent.prompts import build_system_prompt
from backend.agent.state import Hypothesis, new_state
from backend.domain_config import load_domain_config
from backend.sandbox import generate_dataset
from backend.tools.readonly import ToolContext

CFG = load_domain_config()
TEXTS = CFG.demo.texts
ROOT = Path(__file__).resolve().parents[1]


@cache
def _tables():
    return generate_dataset(seed=42).tables


@pytest.fixture
def ctx(db_session):
    return ToolContext(tables=_tables(), session=db_session, run_id="run_lang")


def with_language(lang):
    return CFG.model_copy(update={"ui": CFG.ui.model_copy(update={"language": lang})})


def investigate_system(config, ctx):
    llm = DemoLLM(config, ask_first=False)
    run_investigation(new_state("run_lang", config.domain), config, llm, ctx)
    return llm.calls[0]["system"]


def improve_system(config, ctx):
    llm = DemoLLM(config)
    s = new_state("run_lang", config.domain)
    s["hypotheses"] = [Hypothesis(group="machine", description="wrong_setpoint", confidence=0.8)]
    s["evidence"] = [{"source": "tool", "tool": "correlate", "result": {"x": 1}}]
    run_improvement(s, config, llm, ctx)
    return llm.calls[0]["system"]


def test_prompts_carry_language_from_config(ctx):
    assert f'"{CFG.ui.language}"' in investigate_system(CFG, ctx)
    assert f'"{CFG.ui.language}"' in improve_system(CFG, ctx)


def test_changing_language_changes_prompts(ctx):
    other = with_language("zz-test")
    assert '"zz-test"' in investigate_system(other, ctx)
    assert '"zz-test"' in improve_system(other, ctx)
    assert '"zz-test"' not in build_system_prompt(CFG)
    assert build_system_prompt(other) != build_system_prompt(CFG)


def test_prompt_keeps_structure_names_unchanged():
    p = build_system_prompt(CFG)
    assert "JSON keys" in p and "parameter names" in p
    for group in CFG.hypothesis_groups:
        assert f"- {group}:" in p


def test_no_language_name_hardcoded_in_backend():
    banned = re.compile(r"vietnamese|tiếng việt|english|\bin vi\b", re.IGNORECASE)
    hits = []
    for f in (ROOT / "backend").rglob("*.py"):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if banned.search(line):
                hits.append(f"{f.relative_to(ROOT)}:{n}")
    assert hits == []


def test_demo_llm_display_fields_come_from_demo_texts():
    low = json.loads(demo_low_confidence(CFG))
    assert low["hypotheses"][0]["description"] == TEXTS.unclear_cause
    p = json.loads(demo_improve(CFG))
    assert p["change"] == TEXTS.change and p["rationale"] == TEXTS.rationale


def test_demo_texts_follow_config_and_do_not_leak_between_calls():
    custom = CFG.model_copy(update={"demo": CFG.demo.model_copy(update={"texts": TEXTS.model_copy(update={"change": "C2"})})})
    assert json.loads(demo_improve(custom))["change"] == "C2"
    assert json.loads(demo_improve(CFG))["change"] == TEXTS.change


def test_run_output_uses_demo_texts(ctx):
    llm = DemoLLM(CFG)
    s = new_state("run_lang", CFG.domain)
    s["anomaly"] = {"kpi": CFG.kpis[0].name}
    first = run_investigation(s, CFG, llm, ctx)
    assert first["hypotheses"][0].description == TEXTS.unclear_cause
    second = run_investigation(s, CFG, llm, ctx)
    s2 = new_state("run_lang", CFG.domain)
    s2["hypotheses"] = second["hypotheses"]
    s2["evidence"] = second["evidence"]
    out = run_improvement(s2, CFG, llm, ctx)
    assert out["proposal"]["change"] == TEXTS.change
    assert out["proposal"]["rationale"] == TEXTS.rationale


def test_config_without_texts_or_language_is_rejected():
    data = CFG.model_dump(by_alias=True)
    del data["ui"]
    with pytest.raises(Exception, match="ui"):
        type(CFG).model_validate(data)
    data = CFG.model_dump(by_alias=True)
    del data["demo"]["texts"]
    with pytest.raises(Exception, match="texts"):
        type(CFG).model_validate(data)
