"""R10e/dev-04 (H-32): Learn separates "the action worked" from "the cause was confirmed"."""

import json

import pytest
from langgraph.types import Command
from sqlalchemy import select

from backend.agent.lessons import cause_status, lessons_text, relevant_lessons
from backend.db import repo
from backend.db.models import LearningEntry
from backend.domain_config import LearnParams
from tests.test_act import (
    CFG,
    HUMAN,
    KPI,
    _fixed_tables,
    cfg_run,
    improve_answer,
    investigate_script,
    make,
    make_ctx,
    start,
)

# _fixed_tables() overwrites the KPI after the change, which weakens the setpoint correlation (|r| ~ 0.19 there,
# vs ~0.95 on the real sandbox data: scripts/eval_rootcause.py covers that). The threshold is lowered for this
# fixture only; material_batch (|r| ~ 0.03) stays below it.
FIXTURE_CFG = CFG.model_copy(update={"learn": LearnParams(min_cause_evidence=0.1, cause_parameters=CFG.learn.cause_parameters, unconfirmed_label=CFG.learn.unconfirmed_label)})


def run_to_lesson(db_session, description):
    graph, _ = make(db_session, [*investigate_script(description), improve_answer()], cfg=FIXTURE_CFG)
    cfg = cfg_run()
    start(graph, cfg)
    out = graph.invoke(Command(resume=HUMAN), cfg)
    assert out["measurement"]["passed"]  # the action is right either way
    lesson = db_session.scalars(select(LearningEntry)).all()[-1].content
    return lesson, out


def test_right_diagnosis_right_action_is_confirmed(db_session):
    lesson, out = run_to_lesson(db_session, "wrong_setpoint")
    assert lesson["outcome"] == "success" and lesson["cause_status"] == "confirmed"
    saved = next(e for e in out["events"] if e["type"] == "learning_saved")
    assert saved["payload"]["content"]["cause_status"] == "confirmed"


def test_wrong_diagnosis_right_action_is_not_learned_as_confirmed_cause(db_session):
    # KPI passes (the action fixes the real cause), but the diagnosis names material_batch
    lesson, _ = run_to_lesson(db_session, "material_batch")
    assert lesson["outcome"] == "success"
    assert lesson["cause_status"] == "unconfirmed"


def _state(description, tool_hypothesis_results, parameter="zone3_setpoint_c", machine="M02"):
    return {
        "anomaly": {"kpi": KPI, "machine": machine},
        "proposal": {
            "hypothesis": {"group": "machine", "description": description, "confidence": 0.8},
            "action": {"parameter": parameter, "machine_id": machine, "value": 180},
        },
        "evidence": [
            {"source": "tool", "tool": "correlate", "arguments": {},
             "result": {"machine_id": machine, "correlations": tool_hypothesis_results}}
        ],
    }


def corr(name, r, status="ok"):
    return {"hypothesis": name, "r": r, "strength": abs(r), "n": 50, "status": status}


def test_tool_result_for_another_signal_does_not_confirm():
    # the "wrong" scenario shape: a correlate result exists, but only the other signal is strong
    st = _state("material_batch", [corr("wrong_setpoint", 0.95), corr("material_batch", 0.01)])
    assert cause_status(st, CFG) == "unconfirmed"


@pytest.mark.parametrize("desc", ["material_batch, not wrong_setpoint", "not wrong_setpoint", "wrong_setpoint or wear", "Nguyên nhân là wrong_setpoint"])
def test_free_text_mentioning_a_signal_does_not_claim_it(desc):
    assert cause_status(_state(desc, [corr("wrong_setpoint", 0.95)]), CFG) == "unconfirmed"


def test_structured_signal_field_claims_the_signal():
    st = _state("Lò đặt sai nhiệt độ vùng 3", [corr("wrong_setpoint", 0.95)])
    assert cause_status(st, CFG) == "unconfirmed"
    st["proposal"]["hypothesis"]["signal"] = "wrong_setpoint"
    assert cause_status(st, CFG) == "confirmed"


def test_own_signal_below_threshold_does_not_confirm():
    st = _state("wrong_setpoint", [corr("wrong_setpoint", 0.2)])
    assert cause_status(st, CFG) == "unconfirmed"
    st = _state("wrong_setpoint", [corr("wrong_setpoint", 0.2)])
    assert cause_status(st, CFG.model_copy(update={"learn": LearnParams(min_cause_evidence=0.1, cause_parameters={"wrong_setpoint": ["zone3_setpoint_c"]})})) == "confirmed"


def test_negative_correlation_counts_by_strength():
    assert cause_status(_state("wrong_setpoint", [corr("wrong_setpoint", -0.9)]), CFG) == "confirmed"


def test_action_not_linked_to_the_cause_does_not_confirm():
    st = _state("wrong_setpoint", [corr("wrong_setpoint", 0.95)], parameter="other_parameter_c")
    assert cause_status(st, CFG) == "unconfirmed"


def test_no_tool_evidence_missing_action_or_no_data_is_unconfirmed():
    assert cause_status(_state("wrong_setpoint", []), CFG) == "unconfirmed"
    assert cause_status(_state("wrong_setpoint", [corr("wrong_setpoint", 0.0, "no_data")]), CFG) == "unconfirmed"
    st = _state("wrong_setpoint", [corr("wrong_setpoint", 0.95)])
    st["proposal"]["action"] = None
    assert cause_status(st, CFG) == "unconfirmed"
    assert cause_status({}, CFG) == "unconfirmed"
    st = _state("wrong_setpoint", [corr("wrong_setpoint", 0.95)])
    st["evidence"][0]["result"] = {"error": "x"}
    assert cause_status(st, CFG) == "unconfirmed"


def test_tool_result_of_another_machine_does_not_confirm():
    st = _state("wrong_setpoint", [corr("wrong_setpoint", 0.95)])
    st["evidence"][0]["result"]["machine_id"] = "M01"
    assert cause_status(st, CFG) == "unconfirmed"


def test_threshold_and_link_table_come_from_config():
    st = _state("wrong_setpoint", [corr("wrong_setpoint", 0.95)])
    empty = CFG.model_copy(update={"learn": LearnParams()})
    assert cause_status(st, empty) == "unconfirmed"  # no link table -> nothing confirms
    high = CFG.model_copy(update={"learn": LearnParams(min_cause_evidence=0.99, cause_parameters=CFG.learn.cause_parameters)})
    assert cause_status(st, high) == "unconfirmed"


def test_repeated_calls_do_not_leak():
    ok = _state("wrong_setpoint", [corr("wrong_setpoint", 0.95)])
    bad = _state("material_batch", [corr("material_batch", 0.95)])
    assert [cause_status(s, CFG) for s in (ok, bad, ok, bad)] == ["confirmed", "unconfirmed", "confirmed", "unconfirmed"]


def test_config_rejects_link_to_unknown_names():
    base = CFG.model_dump(by_alias=True)
    base["learn"] = {"cause_parameters": {"wrong_setpoint": ["no_such_param"]}}
    with pytest.raises(ValueError, match="no_such_param"):
        type(CFG).model_validate(base)


def test_next_investigate_prompt_labels_unconfirmed_lesson(db_session):
    lesson, _ = run_to_lesson(db_session, "material_batch")
    assert lesson["cause_status"] == "unconfirmed"
    graph, llm = make(db_session, [*investigate_script(), improve_answer()])
    from tests.test_lessons_r10b2 import start_a2

    start_a2(graph, cfg_run())
    prompt = llm.calls[0]["messages"][0]["content"]
    assert CFG.learn.unconfirmed_label in prompt
    shown = relevant_lessons(make_ctx(db_session, _fixed_tables()), {"kpi": KPI}, 5)
    assert shown[0]["cause_status"] == "unconfirmed"


def test_confirmed_lesson_has_no_unconfirmed_label(db_session):
    repo.save_learning(db_session, CFG.domain, {
        "anomaly": {"kpi": KPI, "machine": "M01"}, "kpi": KPI, "root_cause": {"group": "machine", "description": "wrong_setpoint"},
        "outcome": "success", "cause_status": "confirmed",
    })
    text = lessons_text(relevant_lessons(make_ctx(db_session, _fixed_tables()), {"kpi": KPI}, 5), CFG.learn.unconfirmed_label)
    assert "wrong_setpoint" in text and CFG.learn.unconfirmed_label not in text
    assert json.loads(text[text.index("["):])[0]["cause_status"] == "confirmed"
