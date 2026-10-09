"""R9i/dev-01 (H-42, H-27, H-41): a proposal needs BOTH an action and a SOP proposal, or the LLM must fix it."""

import json

import pytest
from langgraph.types import Command

from backend.agent.nodes.improve import ProposalError
from backend.agent.state import new_state
from tests.test_act import (
    CFG,
    HUMAN,
    SOP_ID,
    _tables,
    cfg_run,
    improve_answer,
    investigate_script,
    make,
    make_act_node,
    make_ctx,
    start,
    types,
    versions,
)
from tests.test_api import make_client


def no_sop():
    """The T-030 first-run shape: a right action, no sop_proposal."""
    return improve_answer(sop=False)


def no_action():
    d = json.loads(improve_answer())
    del d["action"]
    return json.dumps(d)


def blank_content():
    d = json.loads(improve_answer())
    d["sop_change"]["new_content"] = "   "
    return json.dumps(d)


def run_to_end(db_session, improve_replies):
    graph, llm = make(db_session, [*investigate_script(), *improve_replies], tables=_tables())
    c = cfg_run()
    start(graph, c)
    return graph, llm, c


def test_action_without_sop_is_sent_back_then_measured(db_session):
    graph, llm, c = run_to_end(db_session, [no_sop(), improve_answer()])
    assert graph.get_state(c).next == ("wait_approval",)
    sent_back = str(llm.calls[-1]["messages"])
    assert "sop_change" in sent_back and "Rejected" in sent_back
    out = graph.invoke(Command(resume=HUMAN), c)
    kpi = next(e for e in out["events"] if e["type"] == "kpi_measured")["payload"]
    assert kpi["status"] == "measured"


def test_action_without_sop_twice_is_a_retryable_error_not_completed(db_session):
    graph, _ = make(db_session, [*investigate_script(), no_sop(), no_sop()], tables=_tables())
    with pytest.raises(ProposalError, match="sop_change"):
        start(graph, cfg_run())
    assert versions(db_session) == {}


def test_sop_without_action_is_sent_back_then_measured(db_session):
    graph, llm, c = run_to_end(db_session, [no_action(), improve_answer()])
    assert "action" in str(llm.calls[-1]["messages"]) and "Rejected" in str(llm.calls[-1]["messages"])
    out = graph.invoke(Command(resume=HUMAN), c)
    assert next(e for e in out["events"] if e["type"] == "kpi_measured")["payload"]["status"] == "measured"


def test_sop_without_action_twice_makes_no_new_sop_version(db_session):
    graph, _ = make(db_session, [*investigate_script(), no_action(), no_action()], tables=_tables())
    with pytest.raises(ProposalError, match="action"):
        start(graph, cfg_run())
    assert versions(db_session) == {}


def test_blank_new_content_is_sent_back_not_422(db_session):
    graph, llm, c = run_to_end(db_session, [blank_content(), improve_answer()])
    assert graph.get_state(c).next == ("wait_approval",)
    assert "new_content" in str(llm.calls[-1]["messages"])


def test_blank_new_content_through_the_api_is_error_state_after_retries(db_session):
    s = [*investigate_script(), blank_content(), blank_content()]
    client = make_client(db_session, [s], tables=_tables())
    r = client.post("/runs", json={"change_time": "2026-03-20"})
    assert r.status_code == 201, r.text
    assert r.json()["state"] == "error"


def test_prompt_says_both_fields_are_required_and_names_come_from_yaml(db_session):
    _, llm, _ = run_to_end(db_session, [improve_answer()])
    system = llm.calls[-1]["system"]
    assert "sop_change" in system and "action" in system and "required" in system.lower()
    assert all(p in system for p in CFG.actions.parameters)


def test_act_refuses_a_proposal_without_action_and_writes_no_sop(db_session):
    ctx = make_ctx(db_session, _tables())
    s = new_state("run_act", CFG.domain)
    s["change_time"] = "2026-03-20"
    s["anomaly"] = {"machine": "M02", "kpi": CFG.kpis[0].name, "start": "2026-03-10T22:00:00"}
    s["proposal"] = {
        "change": "x", "sop_proposal": {"sop_id": SOP_ID, "new_content": "new text"}, "action": None,
    }
    s["approval"] = {"decision": "approved", "decided_by": "alice"}
    with pytest.raises(ValueError, match="action"):
        make_act_node(CFG, ctx)(s)
    assert versions(db_session) == {}


def test_act_refuses_a_proposal_without_sop(db_session):
    ctx = make_ctx(db_session, _tables())
    s = new_state("run_act", CFG.domain)
    s["proposal"] = {"change": "x", "sop_proposal": None, "action": {"parameter": "p", "machine_id": "M02", "value": 1}}
    s["approval"] = {"decision": "approved", "decided_by": "alice"}
    with pytest.raises(ValueError, match="sop"):
        make_act_node(CFG, ctx)(s)
    assert versions(db_session) == {}


def test_repeat_runs_do_not_leak(db_session):
    for _ in range(2):
        graph, _, c = run_to_end(db_session, [no_sop(), improve_answer()])
        out = graph.invoke(Command(resume=HUMAN), c)
        assert "learning_saved" in types(out)
