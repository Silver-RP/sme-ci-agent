"""R10c/dev-04 (H-14): apply_sop compares the proposal's base_version with the SOP in force; two runs that saw the
same version cannot both write on top of it, and a run can still roll back the version it applied itself."""

import pytest
from langgraph.types import Command
from sqlalchemy import text

from backend.db import repo
from backend.tools.actions import SopConflict, apply_sop, propose_sop
from tests.test_act import (
    CFG,
    HUMAN,
    KPI,
    SOP_ID,
    _fixed_tables,
    _tables,
    cfg_run,
    improve_answer,
    investigate_script,
    make,
    make_ctx,
    rollback_script,
    start,
    types,
    versions,
)

APPROVAL = {"decision": "approved", "approved_by": "alice", "sop_id": SOP_ID}


def _pending(graph, cfg):
    return graph.get_state(cfg).tasks[0].interrupts[0].value


def test_two_runs_same_base_second_approval_does_not_overwrite(db_session):
    # run B gets a second chance: Improve runs again after the conflict
    graph_a, _ = make(db_session, [*investigate_script(), improve_answer()])
    graph_b, _ = make(db_session, [*investigate_script(), improve_answer(), improve_answer()])
    ca, cb = cfg_run(), cfg_run()
    start(graph_a, ca, "run_a")
    start(graph_b, cb, "run_b")
    assert _pending(graph_a, ca)["proposal"]["sop_proposal"]["base_version"] == 1
    assert _pending(graph_b, cb)["proposal"]["sop_proposal"]["base_version"] == 1

    graph_a.invoke(Command(resume=HUMAN), ca)  # A applies v2 and finishes
    assert set(versions(db_session)) == {1, 2}
    out = graph_b.invoke(Command(resume=HUMAN), cb)  # B approved on a stale base

    assert set(versions(db_session)) == {1, 2}  # no overwrite, no duplicate number
    conflicts = [e for e in out["events"] if e["payload"].get("decision") == "sop_conflict"]
    assert len(conflicts) == 1
    msg = conflicts[0]["payload"]["message"]
    assert "version 1" in msg and "version 2" in msg and conflicts[0]["payload"]["current_version"] == 2
    assert "sop_applied" not in types(out)
    assert graph_b.get_state(cb).next == ("wait_approval",)  # proposed again, now on the SOP in force
    assert _pending(graph_b, cb)["proposal"]["sop_proposal"]["base_version"] == 2


def test_conflict_is_bounded_then_halts(db_session):
    n = CFG.loop.max_rejections
    graph, _ = make(db_session, [*investigate_script(), *[improve_answer()] * (n + 1)])
    c = cfg_run()
    start(graph, c, "run_b")
    for i in range(n):
        # another run keeps changing the SOP, so every proposal of this run is stale when approved
        apply_sop(make_ctx(db_session, _fixed_tables()), sop_id=SOP_ID, new_content=f"other {i}", approval=APPROVAL)
        graph.invoke(Command(resume=HUMAN), c)
    assert graph.get_state(c).next == ("wait_halt",)
    assert "sop_applied" not in [e["type"] for e in graph.get_state(c).values["events"]]


def test_run_rolls_back_its_own_version_is_not_a_conflict(db_session):
    graph, _ = make(db_session, rollback_script(), tables=_tables())
    cfg = cfg_run()
    start(graph, cfg)
    graph.invoke(Command(resume=HUMAN), cfg)  # applies v2, Measure fails
    pending = _pending(graph, cfg)
    assert pending["kind"] == "rollback"
    out = graph.invoke(Command(resume={"decision": "approved", "decided_by": "bob"}), cfg)
    done = [e for e in out["events"] if e["type"] == "rollback_done"][-1]["payload"]
    assert done["rolled_back"] is True and "conflict" not in done
    v = versions(db_session)
    assert set(v) == {1, 2, 3} and v[3] == v[1]


def test_rollback_does_not_overwrite_a_newer_version_from_another_run(db_session):
    graph, _ = make(db_session, rollback_script(), tables=_tables())
    cfg = cfg_run()
    start(graph, cfg)
    graph.invoke(Command(resume=HUMAN), cfg)  # this run applied v2
    apply_sop(make_ctx(db_session, _tables()), sop_id=SOP_ID, new_content="another run's SOP", approval=APPROVAL)
    out = graph.invoke(Command(resume={"decision": "approved", "decided_by": "bob"}), cfg)
    done = [e for e in out["events"] if e["type"] == "rollback_done"][-1]["payload"]
    assert done["rolled_back"] is False and "version 2" in done["conflict"]
    v = versions(db_session)
    assert set(v) == {1, 2, 3} and v[3] == "another run's SOP"


def test_apply_sop_base_version_checks(db_session):
    ctx = make_ctx(db_session, _tables())
    p = propose_sop(ctx, sop_id=SOP_ID, new_content="new", rationale="r", kpi=KPI)
    assert p["base_version"] == 1
    assert apply_sop(ctx, sop_id=SOP_ID, new_content="a", approval=APPROVAL, base_version=1)["version"] == 2
    with pytest.raises(SopConflict) as exc:
        apply_sop(ctx, sop_id=SOP_ID, new_content="b", approval=APPROVAL, base_version=1)
    assert exc.value.current_version == 2
    assert set(versions(db_session)) == {1, 2}
    # without base_version the old behaviour stays (callers that do not pass it)
    assert apply_sop(ctx, sop_id=SOP_ID, new_content="c", approval=APPROVAL)["version"] == 3


def test_concurrent_write_taking_same_number_is_a_conflict_not_a_duplicate(db_session, monkeypatch):
    ctx = make_ctx(db_session, _tables())
    apply_sop(ctx, sop_id=SOP_ID, new_content="a", approval=APPROVAL, base_version=1)

    def racing(session, sop_id, content, created_by="system", run_id=None):
        # the other run committed version 3 between our check and our write: we try the same number
        session.execute(
            text("INSERT INTO sop_versions (sop_id, version, content, created_by) VALUES (:s, 2, 'dup', 'x')"),
            {"s": sop_id},
        )

    monkeypatch.setattr(repo, "add_sop_version", racing)
    with pytest.raises(SopConflict):
        apply_sop(ctx, sop_id=SOP_ID, new_content="b", approval=APPROVAL, base_version=2)
    monkeypatch.undo()
    assert set(versions(db_session)) == {1, 2}
