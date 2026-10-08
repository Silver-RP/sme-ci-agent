"""R9/dev-03 (H-12): the root-cause eval compares the final hypothesis with the hidden ground truth."""

import importlib.util
import sys
from pathlib import Path

from backend.agent.llm import ScriptedLLM
from backend.domain_config import load_domain_config
from tests.test_e2e import e2e_db_url  # noqa: F401  (fixture)

PATH = Path(__file__).resolve().parents[1] / "scripts" / "eval_rootcause.py"
spec = importlib.util.spec_from_file_location("eval_rootcause", PATH)
EV = importlib.util.module_from_spec(spec)
sys.modules["eval_rootcause"] = EV  # dataclasses look the module up by name
spec.loader.exec_module(EV)

CFG = load_domain_config()


def by_name(results):
    return {r.name: r for r in results}


def test_scripted_scenarios_right_wrong_unsure(db_session):
    res = by_name(EV.evaluate(EV.SCRIPTED, CFG, db_session, seeds=[42, 43]))
    assert res["right"].accuracy == 1.0
    assert res["wrong"].accuracy == 0.0
    assert res["unsure"].ask_rate > 0
    assert res["unsure"].accuracy == 0.0
    # nobody got to Improve on weak evidence: right/wrong have a tool result and high confidence, unsure halts
    assert all(r.improve_no_evidence == 0 for r in res.values())
    assert all(run.reached_improve for run in res["right"].runs + res["wrong"].runs)
    assert not any(run.reached_improve for run in res["unsure"].runs)
    assert res["right"].tokens > 0


def test_repeated_calls_do_not_leak_state(db_session):
    a = EV.evaluate({"right": EV.SCRIPTED["right"]}, CFG, db_session, seeds=[42])
    b = EV.evaluate({"right": EV.SCRIPTED["right"]}, CFG, db_session, seeds=[42])
    assert a[0].accuracy == b[0].accuracy == 1.0


def test_empty_seed_list_gives_zero_rates(db_session):
    res = EV.evaluate({"right": EV.SCRIPTED["right"]}, CFG, db_session, seeds=[])
    assert res[0].runs == [] and res[0].accuracy == 0.0 and res[0].ask_rate == 0.0


def test_judge_needs_group_and_cause():
    assert EV.is_correct({"group": "machine", "description": "wrong_setpoint on M02"}, "wrong_setpoint", CFG)
    assert not EV.is_correct({"group": "material", "description": "wrong_setpoint"}, "wrong_setpoint", CFG)
    assert not EV.is_correct({"group": "machine", "description": "wear"}, "wrong_setpoint", CFG)
    assert not EV.is_correct(None, "wrong_setpoint", CFG)


def test_human_answers_are_neutral():
    cause_words = {"setpoint", "m02", "night", "wrong"}
    assert not any(w in EV.NEUTRAL_ANSWER.lower() for w in cause_words)


def test_scripted_factories_give_fresh_llms():
    assert isinstance(EV.SCRIPTED["right"](CFG), ScriptedLLM)
    assert EV.SCRIPTED["right"](CFG) is not EV.SCRIPTED["right"](CFG)


def test_main_prints_table_and_exits_zero(e2e_db_url, monkeypatch, capsys):  # noqa: F811
    # main() COMMITS, so it runs in its own throwaway database, not the shared test one
    monkeypatch.setenv("DATABASE_URL", e2e_db_url)
    assert EV.main(["--seeds", "1"]) == 0
    out = capsys.readouterr().out
    assert "right" in out and "wrong" in out and "unsure" in out and "accuracy" in out
