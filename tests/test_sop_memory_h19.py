"""R10c/dev-03 (H-19): after a halt, investigating again keeps the SOP that is in force, so a later rollback
restores the SOP as it was before the run (not the wrong version applied earlier in the same run)."""

from langgraph.types import Command

from tests.test_act import (
    HUMAN,
    SOP_ID,
    _tables,
    cfg_run,
    make,
    rollback_script,
    start,
    versions,
)
from tests.test_measure_r8 import run_to_measure, script_with

DECLINE = {"decision": "rejected", "decided_by": "bob", "reason": "keep it"}
CONTINUE = {"decision": "investigate", "decided_by": "alice", "reason": "look again"}


def test_decline_rollback_investigate_again_wrong_fix_rollback_restores_sop_before_run(db_session):
    graph, _ = make(db_session, [*rollback_script(), *rollback_script()], tables=_tables())
    cfg = cfg_run()
    start(graph, cfg)
    graph.invoke(Command(resume=HUMAN), cfg)  # wrong fix applied (v2), Measure fails, rollback proposed
    graph.invoke(Command(resume=DECLINE), cfg)  # person declines: halt, v2 still in force
    assert graph.get_state(cfg).next == ("wait_halt",)
    original = versions(db_session)[1]
    graph.invoke(Command(resume=CONTINUE), cfg)  # investigate again -> a second wrong proposal
    graph.invoke(Command(resume=HUMAN), cfg)  # applied (v3), Measure fails, rollback proposed
    pending = graph.get_state(cfg).tasks[0].interrupts[0].value
    assert pending["kind"] == "rollback"
    assert pending["proposal"]["sop_proposal"]["new_content"] == original
    graph.invoke(Command(resume={"decision": "approved", "decided_by": "bob"}), cfg)
    v = versions(db_session)
    assert v[max(v)] == original and v[max(v)] != v[2]


def test_halt_after_insufficient_evidence_then_investigate_still_knows_sop_in_force(db_session):
    late = "2026-06-29T22:00:00"
    graph, c, _ = run_to_measure(db_session, [*script_with("wrong_setpoint"), *script_with("wrong_setpoint")], change_time=late)
    for _ in range(3):
        if graph.get_state(c).next != ("wait_evidence",):
            break
        graph.invoke(Command(resume="wait for more data"), c)
    assert graph.get_state(c).next == ("wait_halt",)
    graph.invoke(Command(resume=CONTINUE), c)
    applied = graph.get_state(c).values.get("applied")
    assert applied and applied["sop_id"] == SOP_ID and applied["version"] == 2
