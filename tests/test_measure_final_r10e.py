"""R10e/dev-03: Measure does not ask again when the data cannot grow (H-34, #111)."""

import json

import pytest
from langgraph.types import Command

from backend.agent.nodes.act import DecisionError, make_measure_node, route_after_measure
from backend.agent.state import new_state
from tests.test_act import CFG, KPI, _tables, improve_answer, make_ctx, types
from tests.test_measure_r8 import run_to_measure, script_with

LATE = "2026-06-29T22:00:00"  # close to the end of the sandbox data


def _questions(out):
    return [e["payload"] for e in out["events"] if e["type"] == "question_asked"]


def test_sandbox_data_at_the_end_asks_once_and_offers_only_finish(db_session):
    graph, c, out = run_to_measure(db_session, script_with("wrong_setpoint"), change_time=LATE)
    m = out["measurement"]
    assert m["status"] == "insufficient_evidence" and m["more_data_possible"] is False
    qs = _questions(out)
    assert len(qs) == 1  # one question for Measure, no loop up to ask.max_questions
    assert qs[0]["options"] == ["finish"] and qs[0]["kind"] == "halt" and qs[0]["reason"] == "insufficient_evidence"
    assert qs[0]["question"] == CFG.messages.render(
        "evidence_final_question", n_after=m["n_after"], n_unit=m["n_unit"], kpi=KPI, needed=CFG.measure.min_units_after
    )
    assert graph.get_state(c).next == ("wait_halt",)
    done = graph.invoke(Command(resume={"decision": "finish", "decided_by": "alice", "proposal_id": "halt_1"}), c)
    fin = [e for e in done["events"] if e["type"] == "run_finished"][-1]["payload"]
    assert fin["status"] == "closed" and fin["halt_reason"] == "insufficient_evidence"
    assert graph.get_state(c).next == ()


def test_investigate_is_not_offered_when_data_cannot_grow(db_session):
    graph, c, _ = run_to_measure(db_session, script_with("wrong_setpoint"), change_time=LATE)
    with pytest.raises(DecisionError):
        graph.invoke(Command(resume={"decision": "investigate", "decided_by": "alice", "proposal_id": "halt_1"}), c)


def test_not_a_rollback_and_not_a_failed_kpi(db_session):
    _, _, out = run_to_measure(db_session, script_with("wrong_setpoint"), change_time=LATE)
    assert out["measurement"]["passed"] is None
    assert "rollback_applied" not in types(out) and "learning_saved" not in types(out)
    assert not any(e["type"] == "proposal_created" and e["payload"].get("kind") == "rollback" for e in out["events"])


def test_a_source_that_can_grow_keeps_the_old_behaviour(db_session):
    # no simulated data (applied has no "sim"): the data is a real source that may get more points
    node = make_measure_node(CFG, make_ctx(db_session, _tables()))
    s = new_state("run_m", CFG.domain)
    s["anomaly"] = {"machine": "M02", "kpi": KPI}
    s["change_time"] = LATE
    s["applied"] = {"change_time": LATE, "action": json.loads(improve_answer())["action"]}
    s["proposal"] = {"expected_kpi": {"kpi": KPI, "direction": "decrease", "target": 0.02}}
    m = node(s)["measurement"]
    assert m["status"] == "insufficient_evidence" and m["more_data_possible"] is True
    assert route_after_measure({**s, "measurement": m}, CFG) == "ask_evidence"
    assert route_after_measure({**s, "measurement": m, "measure_wait_count": CFG.ask.max_questions}, CFG) == "halt"


def test_repeated_calls_do_not_leak_state(db_session):
    for _ in range(2):
        _, _, out = run_to_measure(db_session, script_with("wrong_setpoint"), change_time=LATE)
        assert len(_questions(out)) == 1
