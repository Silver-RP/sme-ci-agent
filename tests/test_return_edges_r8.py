"""R8/dev-05 (T-040): return edges (revise, reject, rollback) and resumable halts (scripted LLM, seed 42).

The reject -> Improve and rollback -> Investigate edges are also covered in tests/test_act.py
(test_rejected_proposal_returns_to_improve_and_applies_nothing, test_rollback_confirmed_creates_new_version_and_returns_to_investigate).
"""

import json

import pytest
from langgraph.types import Command
from sqlalchemy import select

from backend.agent.nodes.act import DecisionError, parse_decision
from backend.db.models import AuditLog
from backend.domain_config import LoopParams
from tests.test_act import (
    CFG,
    HUMAN,
    _tables,
    approve,
    cfg_run,
    improve_answer,
    investigate_script,
    make,
    rollback_script,
    start,
    types,
    versions,
)
from tests.test_api import make_client, sse_events
from tests.test_api import start as api_start

REVISE = {"decision": "revise", "decided_by": "alice", "reason": "M02 was serviced on 3/18, check the calibration"}
CONTINUE = {"decision": "investigate", "decided_by": "alice", "reason": "please look at the shift log"}
FINISH = {"decision": "finish", "decided_by": "alice", "reason": "enough for today"}


def audits(db_session, action):
    return [a.params for a in db_session.scalars(select(AuditLog).where(AuditLog.action == action))]


# ---- 1: revise (dispute the hypothesis / add information) -> Investigate ----


def test_revise_returns_to_investigate_with_feedback_in_evidence(db_session):
    graph, llm = make(db_session, [*investigate_script(), improve_answer(), *investigate_script(), improve_answer()])
    cfg = cfg_run()
    start(graph, cfg)
    assert len(llm.calls) == 3
    out = graph.invoke(Command(resume=REVISE), cfg)
    assert len(llm.calls) == 6  # Investigate (2 calls) and Improve ran again, not just Improve
    assert "calibration" in json.dumps(llm.calls[3]["messages"])  # the new investigation saw the feedback
    fb = [e for e in out["evidence"] if e.get("source") == "human_feedback"]
    assert len(fb) == 1 and fb[0]["feedback"] == REVISE["reason"]
    assert out["revision_count"] == 1 and out.get("rejection_count", 0) == 0  # not a rejection
    assert graph.get_state(cfg).next == ("wait_approval",)
    assert versions(db_session) == {}  # nothing applied
    ev = next(e for e in out["events"] if e["type"] == "approval_decided")
    assert ev["payload"]["decision"] == "revise" and ev["payload"]["reason"] == REVISE["reason"]
    assert types(out).count("hypothesis_updated") == 2
    assert graph.invoke(Command(resume=HUMAN), cfg)["status"] == "completed"


def test_revise_is_not_limited_by_max_rejections(db_session):
    cfg_l = CFG.model_copy(update={"loop": LoopParams(max_rejections=1, max_rollbacks=2)})
    graph, _ = make(db_session, [*investigate_script(), improve_answer()] * 3, cfg=cfg_l)
    cfg = cfg_run()
    start(graph, cfg)
    for _ in range(2):
        graph.invoke(Command(resume=REVISE), cfg)
        assert graph.get_state(cfg).next == ("wait_approval",)


@pytest.mark.parametrize(
    "bad,kind",
    [
        ({"decision": "revise", "decided_by": "alice"}, "proposal"),  # no feedback
        ({"decision": "revise", "decided_by": "alice", "reason": "  "}, "proposal"),
        ({"decision": "revise", "decided_by": "alice", "reason": "x"}, "rollback"),  # only for proposals
        ({"decision": "finish", "decided_by": "alice"}, "proposal"),
        ({"decision": "approved", "decided_by": "alice"}, "halt"),
    ],
)
def test_decision_is_validated_per_kind(bad, kind):
    with pytest.raises(DecisionError):
        parse_decision(bad, CFG, kind)


def test_default_kind_is_proposal_and_halt_decisions_parse():
    assert parse_decision(REVISE, CFG)["decision"] == "revise"
    assert parse_decision(CONTINUE, CFG, "halt")["decision"] == "investigate"


# ---- 2: limits -> interrupt, resumable ----


def halted_by_rejections(db_session):
    cfg_l = CFG.model_copy(update={"loop": LoopParams(max_rejections=1, max_rollbacks=2)})
    graph, llm = make(db_session, [*investigate_script(), improve_answer(), *investigate_script(), improve_answer()], cfg=cfg_l)
    cfg = cfg_run()
    start(graph, cfg)
    out = graph.invoke(Command(resume={"decision": "rejected", "decided_by": "alice", "reason": "no"}), cfg)
    assert graph.get_state(cfg).next == ("wait_halt",)
    return graph, cfg, out, llm


def test_rejection_limit_interrupts_and_continues_with_investigate(db_session):
    graph, cfg, out, llm = halted_by_rejections(db_session)
    snap = graph.get_state(cfg)
    pending = snap.tasks[0].interrupts[0].value
    assert pending["kind"] == "halt" and pending["reason"] == "max_rejections_reached" and pending["proposal_id"]
    assert pending["options"] == ["investigate", "finish"]
    assert out["status"] == "awaiting_human" and "run_finished" not in types(out)
    calls = len(llm.calls)
    out = graph.invoke(Command(resume=CONTINUE), cfg)
    assert len(llm.calls) == calls + 3  # Investigate (2) + Improve
    assert "shift log" in json.dumps(llm.calls[calls]["messages"])
    assert out["rejection_count"] == 0 and out["status"] == ""  # the person chose to go on: counters restart
    assert graph.get_state(cfg).next == ("wait_approval",)
    assert graph.invoke(Command(resume=HUMAN), cfg)["status"] == "completed"


def test_rejection_limit_finish_ends_the_run_without_changes(db_session):
    graph, cfg, _, _ = halted_by_rejections(db_session)
    out = graph.invoke(Command(resume=FINISH), cfg)
    assert graph.get_state(cfg).next == ()
    assert out["status"] == "closed"
    last = out["events"][-1]
    assert last["type"] == "run_finished" and last["payload"]["status"] == "closed"
    assert last["payload"]["halt_reason"] == "max_rejections_reached"
    assert versions(db_session) == {}
    [row] = audits(db_session, "halt_decided")
    assert row["decision"] == "finish" and row["decided_by"] == "alice" and row["halt_reason"] == "max_rejections_reached"


def test_halt_resume_with_wrong_proposal_id_is_refused(db_session):
    from backend.agent.nodes.act import DecisionError as DE

    graph, cfg, _, _ = halted_by_rejections(db_session)
    with pytest.raises(DE):
        graph.invoke(Command(resume={**CONTINUE, "proposal_id": "halt_99", "kind": "halt"}), cfg)


def test_max_rollbacks_interrupts_and_continues(db_session):
    cfg_l = CFG.model_copy(update={"loop": LoopParams(max_rejections=3, max_rollbacks=1)})
    graph, _ = make(db_session, [*rollback_script(), *investigate_script("wear"), improve_answer()], tables=_tables(), cfg=cfg_l)
    cfg = cfg_run()
    start(graph, cfg)
    graph.invoke(Command(resume=HUMAN), cfg)
    out = graph.invoke(Command(resume=HUMAN), cfg)  # rollback confirmed -> limit reached
    assert graph.get_state(cfg).next == ("wait_halt",)
    assert out["events"][-1]["payload"]["reason"] == "max_rollbacks_reached"
    out = graph.invoke(Command(resume=CONTINUE), cfg)
    assert out["rollback_count"] == 0
    assert graph.get_state(cfg).next == ("wait_approval",)


def test_question_limit_interrupts_and_continues(db_session):
    from backend.agent.graph import build_graph
    from backend.agent.llm import ScriptedLLM
    from tests.test_act import make_ctx
    from tests.test_ask import cfg_with, final, tool_step

    ctx = make_ctx(db_session, _tables())
    graph = build_graph(cfg_with(max_questions=1), llm=ScriptedLLM([final(0.1), final(0.1), tool_step(), final(0.9)]), tool_ctx=ctx)
    cfg = cfg_run()
    graph.invoke({"run_id": "r", "domain": CFG.domain, "evidence": [], "events": [], "hypotheses": [], "anomaly": None, "proposal": None}, cfg)
    graph.invoke(Command(resume="a1"), cfg)
    assert graph.get_state(cfg).next == ("wait_halt",)
    out = graph.invoke(Command(resume=CONTINUE), cfg)
    assert graph.get_state(cfg).next == ()  # ends after Investigate (no full loop), concluded this time
    assert out["hypotheses"][0].confidence == 0.9 and out["status"] == ""


def test_second_halt_gets_a_new_id(db_session):
    graph, cfg, _, _ = halted_by_rejections(db_session)
    first = graph.get_state(cfg).tasks[0].interrupts[0].value["proposal_id"]
    graph.invoke(Command(resume={**CONTINUE, "proposal_id": first, "kind": "halt"}), cfg)
    graph.invoke(Command(resume={"decision": "rejected", "decided_by": "alice"}), cfg)  # max_rejections=1 again
    assert graph.get_state(cfg).next == ("wait_halt",)
    second = graph.get_state(cfg).tasks[0].interrupts[0].value["proposal_id"]
    assert second != first and first == "halt_1" and second == "halt_2"


# ---- 3: rollback declined -> the applied SOP stays in force, said in event and audit ----


def test_declined_rollback_records_that_the_sop_is_still_in_force(db_session):
    graph, _ = make(db_session, rollback_script(), tables=_tables())
    cfg = cfg_run()
    start(graph, cfg)
    graph.invoke(Command(resume=HUMAN), cfg)
    out = graph.invoke(Command(resume={"decision": "rejected", "decided_by": "bob", "reason": "keep it"}), cfg)
    ev = next(e for e in out["events"] if e["type"] == "approval_decided" and e["payload"]["kind"] == "rollback")
    assert ev["payload"]["sop_still_in_force"] is True and ev["payload"]["sop_version"] == 2
    assert ev["payload"]["sop_id"] == CFG.sop[0].id
    row = next(p for p in audits(db_session, "approval_decided") if p["kind"] == "rollback")
    assert row["sop_still_in_force"] is True and row["sop_version"] == 2
    halt = out["events"][-1]["payload"]
    assert halt["reason"] == "rollback_declined" and halt["sop_still_in_force"] is True and halt["sop_version"] == 2
    assert sorted(versions(db_session)) == [1, 2]


def test_confirmed_rollback_does_not_claim_the_sop_is_in_force(db_session):
    graph, _ = make(db_session, rollback_script(), tables=_tables())
    cfg = cfg_run()
    start(graph, cfg)
    graph.invoke(Command(resume=HUMAN), cfg)
    out = graph.invoke(Command(resume={"decision": "approved", "decided_by": "bob"}), cfg)
    ev = next(e for e in out["events"] if e["type"] == "approval_decided" and e["payload"]["kind"] == "rollback")
    assert "sop_still_in_force" not in ev["payload"]


# ---- 4: API ----


def test_api_revise_goes_back_to_investigate(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer(), *investigate_script("wear"), improve_answer()]])
    run = api_start(client)
    r = approve(client, run["run_id"], REVISE)
    assert r.status_code == 200 and r.json()["pending"]["kind"] == "proposal"
    msgs = sse_events(client, run["run_id"])
    assert [m["event"] for m in msgs].count("hypothesis_updated") == 2
    assert next(m for m in msgs if m["event"] == "approval_decided")["data"]["payload"]["decision"] == "revise"


@pytest.mark.parametrize(
    "bad",
    [{"decision": "revise", "decided_by": "alice"}, {"decision": "finish", "decided_by": "alice"}],
)
def test_api_invalid_decision_for_kind_is_422_and_run_keeps_waiting(db_session, bad):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = api_start(client)
    assert approve(client, run["run_id"], bad).status_code == 422
    assert client.get(f"/runs/{run['run_id']}").json()["state"] == "waiting"
    assert approve(client, run["run_id"], HUMAN).status_code == 200


def test_api_halt_is_a_pending_approval_that_can_continue_or_finish(db_session):
    cfg_l = CFG.model_copy(update={"loop": LoopParams(max_rejections=1, max_rollbacks=2)})
    from fastapi.testclient import TestClient

    from backend.agent.llm import ScriptedLLM
    from backend.api.app import create_app
    from backend.tools.readonly import ToolContext
    from tests.test_act import _fixed_tables

    scripts = [[*investigate_script(), improve_answer(), *investigate_script(), improve_answer()]]
    app = create_app(
        cfg_l,
        llm_factory=lambda rid: ScriptedLLM(scripts.pop(0)),
        ctx_factory=lambda rid: ToolContext(tables=_fixed_tables(), session=db_session, run_id=rid),
    )
    client = TestClient(app)
    run = api_start(client)
    rid = run["run_id"]
    r = approve(client, rid, {"decision": "rejected", "decided_by": "alice", "reason": "no"})
    pending = r.json()["pending"]
    assert r.json()["state"] == "waiting" and pending["type"] == "approval" and pending["kind"] == "halt"
    assert pending["reason"] == "max_rejections_reached" and pending["options"] == ["investigate", "finish"]
    # stale / wrong binding -> 409; the halt is still waiting
    assert approve(client, rid, CONTINUE, kind="proposal").status_code == 409
    assert approve(client, rid, CONTINUE, proposal_id="halt_99").status_code == 409
    assert approve(client, rid, {"decision": "approved", "decided_by": "alice"}).status_code == 422
    r = approve(client, rid, CONTINUE)
    assert r.status_code == 200 and r.json()["pending"]["kind"] == "proposal"
    r = approve(client, rid, HUMAN)
    assert r.json()["state"] == "finished" and r.json()["status"] == "completed"


def test_api_halt_finish_closes_the_run(db_session):
    cfg_l = CFG.model_copy(update={"loop": LoopParams(max_rejections=1, max_rollbacks=2)})
    from fastapi.testclient import TestClient

    from backend.agent.llm import ScriptedLLM
    from backend.api.app import create_app
    from backend.tools.readonly import ToolContext
    from tests.test_act import _fixed_tables

    script = [*investigate_script(), improve_answer()]
    app = create_app(
        cfg_l,
        llm_factory=lambda rid: ScriptedLLM(script),
        ctx_factory=lambda rid: ToolContext(tables=_fixed_tables(), session=db_session, run_id=rid),
    )
    client = TestClient(app)
    rid = api_start(client)["run_id"]
    approve(client, rid, {"decision": "rejected", "decided_by": "alice"})
    r = approve(client, rid, FINISH)
    assert r.json()["state"] == "finished" and r.json()["status"] == "closed"
    assert [m["event"] for m in sse_events(client, rid)][-1] == "run_finished"


# ---- 5: scripts/run_scenario.py options ----


def _scenario(db_session, **kw):
    import importlib.util
    from pathlib import Path

    from backend.agent.demo_llm import scripted_demo_llm

    path = Path(__file__).resolve().parents[1] / "scripts" / "run_scenario.py"
    spec = importlib.util.spec_from_file_location("run_scenario_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    then = mod.SEND_BACK_SCRIPT[kw.get("on_proposal", "approve")]
    return mod.run_scenario(scripted_demo_llm(CFG, then=then), CFG, db_session, **kw)


@pytest.mark.parametrize("branch,decision", [("revise", "revise"), ("reject", "rejected")])
def test_run_scenario_can_send_the_first_proposal_back(db_session, branch, decision):
    events = _scenario(db_session, on_proposal=branch)
    decided = [e["payload"]["decision"] for e in events if e["type"] == "approval_decided" and e["payload"]["kind"] == "proposal"]
    assert decided[0] == decision and "approved" in decided[1:]  # then it approves the next one
    assert events[-1]["type"] == "run_finished"


def test_run_scenario_halt_branches_are_reachable_and_default_is_unchanged(db_session):
    default = _scenario(db_session)
    assert not [e for e in default if e["type"] == "approval_decided" and e["payload"]["decision"] in ("revise", "investigate")]
    assert default[-1]["type"] == "run_finished"
