"""R10b2/dev-03: a new run picks an anomaly without a lesson; Investigate reads earlier lessons as context only."""

import json

import pytest
from langgraph.types import Command
from sqlalchemy import select

from backend.agent.graph import build_graph
from backend.agent.llm import ScriptedLLM
from backend.agent.state import new_state
from backend.db import repo
from backend.db.models import LearningEntry
from backend.detect.statistical import detect
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


@pytest.fixture(autouse=True)
def skip_handled_on(monkeypatch):
    monkeypatch.delenv("SME_SKIP_HANDLED", raising=False)  # product default: on


def script():
    return [*investigate_script(), improve_answer()]


def script_m01():
    d = json.loads(improve_answer())
    d["action"]["machine_id"] = "M01"
    return [*investigate_script(), json.dumps(d)]


def start_a2(graph, cfg):
    s = new_state("run_act", CFG.domain)
    s["change_time"] = "2026-06-20"  # after the M01 anomaly started
    return graph.invoke(s, cfg)


def anomaly_of(graph, cfg):
    return graph.get_state(cfg).values["anomaly"]


def run_first_to_learning(db_session):
    graph, _ = make(db_session, script())
    cfg = cfg_run()
    start(graph, cfg)
    a1 = anomaly_of(graph, cfg)
    graph.invoke(Command(resume=HUMAN), cfg)
    assert graph.get_state(cfg).values["status"] == "completed"
    return a1


def first_user_text(llm):
    return llm.calls[0]["messages"][0]["content"]


def test_next_run_after_learning_picks_another_anomaly(db_session):
    a1 = run_first_to_learning(db_session)
    saved = db_session.scalars(select(LearningEntry)).all()
    assert len(saved) == 1 and saved[0].content["anomaly"]["start"] == a1["start"]

    graph, _ = make(db_session, script_m01())
    cfg = cfg_run()
    start_a2(graph, cfg)
    a2 = anomaly_of(graph, cfg)
    assert a2 is not None and (a2["machine"], a2["start"]) != (a1["machine"], a1["start"])

    # a third run, still without a new lesson, picks the same A2 again (nothing leaks between runs)
    graph3, _ = make(db_session, script_m01())
    cfg3 = cfg_run()
    start_a2(graph3, cfg3)
    assert anomaly_of(graph3, cfg3) == a2


def test_first_run_with_empty_store_picks_first_detected(db_session):
    graph, _ = make(db_session, script())
    cfg = cfg_run()
    start(graph, cfg)
    assert db_session.scalars(select(LearningEntry)).all() == []
    first = detect(_fixed_tables(), CFG)[0]["payload"]
    assert anomaly_of(graph, cfg) == first


def test_all_anomalies_handled_finishes_without_llm(db_session):
    for ev in detect(_fixed_tables(), CFG):
        repo.save_learning(db_session, CFG.domain, {"anomaly": ev["payload"], "kpi": KPI, "outcome": "no_change"})
    graph, llm = make(db_session, [])
    out = start(graph, cfg_run())
    assert out["status"] == "no_anomaly" and llm.calls == []


def test_investigate_prompt_of_a2_contains_a1_lesson_and_not_machine(db_session):
    run_first_to_learning(db_session)
    graph, llm = make(db_session, script_m01())
    start_a2(graph, cfg_run())
    text = first_user_text(llm)
    assert "Lessons from earlier runs" in text and "wrong_setpoint" in text
    assert "zone3_setpoint_c" in text
    lesson_part = text.split("Lessons from earlier runs", 1)[1]
    assert "M02" not in lesson_part  # matched by KPI, group and parameter, not by machine


def test_no_lessons_block_when_store_is_empty(db_session):
    graph, llm = make(db_session, script())
    start(graph, cfg_run())
    assert "Lessons" not in first_user_text(llm)


def test_lessons_of_another_kpi_are_not_shown(db_session):
    repo.save_learning(
        db_session,
        CFG.domain,
        {"anomaly": {"kpi": "other_kpi", "machine": "M09", "start": "x"}, "kpi": "other_kpi",
         "root_cause": {"group": "machine", "description": "zzz"}},
    )
    graph, llm = make(db_session, script())
    start(graph, cfg_run())
    assert "zzz" not in first_user_text(llm)


def test_max_lessons_zero_turns_the_block_off(db_session):
    run_first_to_learning(db_session)
    cfg_domain = CFG.model_copy(update={"investigate": CFG.investigate.model_copy(update={"max_lessons": 0})})
    llm = ScriptedLLM(script_m01())
    graph = build_graph(cfg_domain, llm=llm, tool_ctx=make_ctx(db_session, _fixed_tables()), full_loop=True)
    start_a2(graph, cfg_run())
    assert "Lessons" not in first_user_text(llm)


def test_lesson_does_not_send_run_to_improve_without_tool_result(db_session):
    run_first_to_learning(db_session)
    confident = json.dumps(
        {"hypotheses": [{"group": "machine", "description": "wrong_setpoint", "confidence": 0.95}],
         "insufficient_evidence": False}
    )
    graph, llm = make(db_session, [confident])  # no tool call at all, and no Improve answer scripted
    cfg = cfg_run()
    start(graph, cfg)
    snap = graph.get_state(cfg)
    assert snap.next == ("wait_answer",)  # asks a person; Improve was not reached
    assert snap.values.get("proposal") is None
    assert len(llm.calls) == 1


def test_env_switch_off_always_takes_first_anomaly(db_session, monkeypatch):
    run_first_to_learning(db_session)
    monkeypatch.setenv("SME_SKIP_HANDLED", "0")
    graph, _ = make(db_session, script())
    cfg = cfg_run()
    start(graph, cfg)
    assert anomaly_of(graph, cfg) == detect(_fixed_tables(), CFG)[0]["payload"]
