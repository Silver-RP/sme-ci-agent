"""R5/dev-02: approval, Act, Measure, Learn, rollback and conditional edges (scripted LLM, seed 42, no network)."""

import json
import uuid
from functools import cache
from pathlib import Path

import pytest
from langgraph.types import Command
from sqlalchemy import select

from backend.agent.graph import build_graph
from backend.agent.llm import LLMResponse, ScriptedLLM, ToolCall
from backend.agent.nodes.act import (
    DecisionError,
    evaluate_kpi,
    make_act_node,
    make_measure_node,
    parse_decision,
)
from backend.agent.state import new_state
from backend.db.models import AuditLog, LearningEntry, SopVersion
from backend.domain_config import LoopParams, load_domain_config
from backend.sandbox import generate_dataset
from backend.tools.readonly import ToolContext

CFG = load_domain_config()
KPI = CFG.kpis[0].name
SOP_ID = CFG.sop[0].id
CHANGE = "2026-03-20"
SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "docs" / "schema" / "events.json").read_text())
HUMAN = {"decision": "approved", "decided_by": "alice"}


def approve(client, run_id, body, **override):
    """POST /approval, filling proposal_id and kind from the interrupt now waiting (as the dashboard does)."""
    pending = client.get(f"/runs/{run_id}").json().get("pending") or {}
    fill = {"proposal_id": pending.get("proposal_id", "none"), "kind": pending.get("kind", "proposal")}
    if isinstance(body, dict) and not any(k in body for k in ("proposal_id", "kind")):
        body = {**fill, **body}
    return client.post(f"/runs/{run_id}/approval", json={**body, **override} if isinstance(body, dict) else body)


@cache
def _tables():
    return generate_dataset(seed=42).tables


@cache
def _fixed_tables():
    """Same data, but M02 is back at baseline after CHANGE: the fix worked."""
    t = dict(_tables())
    k = t["kpi_log"].copy()
    m = (k["machine_id"] == "M02") & (k["timestamp"] >= CHANGE) & (k["kpi"] == KPI)
    k.loc[m, "value"] = CFG.kpis[0].target
    t["kpi_log"] = k
    return t


def make_ctx(session, tables):
    return ToolContext(tables=tables, session=session, run_id="run_act")


def investigate_script(description="wrong_setpoint"):
    return [
        LLMResponse(tool_calls=[ToolCall(id="t1", name="correlate", arguments={"kpi": KPI, "machine_id": "M02"})]),
        json.dumps(
            {
                "hypotheses": [{"group": "machine", "description": description, "confidence": 0.8}],
                "insufficient_evidence": False,
            }
        ),
    ]


def improve_answer(sop=True):
    d = {
        "change": "Restore setpoint to 180 and add a setpoint check step to the SOP",
        "rationale": "Evidence 0 shows the defect rate follows the setpoint change",
        "evidence_refs": [0],
        "expected_kpi": {"kpi": KPI, "direction": "decrease", "target": 0.02},
        "action": {"parameter": "zone3_setpoint_c", "machine_id": "M02", "value": 180},  # R9: Measure follows this
    }
    if sop:
        d["sop_change"] = {"sop_id": SOP_ID, "new_content": "Verify setpoint 180.\nCheck the setpoint again after the shift change."}
    return json.dumps(d)


def wrong_improve_answer():
    """Same proposal, but the action sets a parameter the simulator does not link to the anomaly: KPI stays high."""
    d = json.loads(improve_answer())
    d["action"]["parameter"] = "other_parameter_c"
    return json.dumps(d)


def cfg_run():
    return {"configurable": {"thread_id": f"t_{uuid.uuid4().hex[:8]}"}}


def start(graph, cfg, run_id="run_act"):
    s = new_state(run_id, CFG.domain)
    s["change_time"] = CHANGE
    return graph.invoke(s, cfg)


def types(out):
    return [e["type"] for e in out["events"]]


def versions(session):
    rows = session.scalars(select(SopVersion).where(SopVersion.sop_id == SOP_ID).order_by(SopVersion.version)).all()
    return {r.version: r.content for r in rows}


def audit_actions(session):
    return [a.action for a in session.scalars(select(AuditLog).order_by(AuditLog.id))]


def valid_event(ev):
    assert set(ev) == set(SCHEMA["required"])
    assert ev["type"] in SCHEMA["properties"]["type"]["enum"]
    assert ev["agent"] in SCHEMA["properties"]["agent"]["enum"]
    assert ev["domain"] == CFG.domain and isinstance(ev["payload"], dict)


def make(db_session, script, tables=None, cfg=CFG):
    llm = ScriptedLLM(script)
    ctx = make_ctx(db_session, tables or _fixed_tables())
    return build_graph(cfg, llm=llm, tool_ctx=ctx, full_loop=True), llm


# ---- branch 1: KPI passes -> learn (also the milestone end-to-end test) ----


def test_end_to_end_approve_apply_measure_learn(db_session):
    graph, llm = make(db_session, [*investigate_script(), improve_answer()])
    cfg = cfg_run()
    out = start(graph, cfg)
    snap = graph.get_state(cfg)
    assert snap.next == ("wait_approval",)  # waits for a person; nothing applied yet
    assert snap.tasks[0].interrupts[0].value["proposal"]["change"]
    assert versions(db_session) == {}
    assert "sop_applied" not in types(out)

    calls_before = len(llm.calls)
    out = graph.invoke(Command(resume=HUMAN), cfg)
    assert len(llm.calls) == calls_before  # Act/Measure/Learn and the edges never call the LLM
    assert graph.get_state(cfg).next == ()
    assert types(out) == [
        "tool_called", "anomaly_detected", "tool_called", "hypothesis_updated", "proposal_created",
        "approval_decided", "sop_applied", "kpi_measured", "learning_saved", "run_finished",
    ]
    for ev in out["events"]:
        valid_event(ev)
    assert len({e["event_id"] for e in out["events"]}) == len(out["events"])
    m = out["measurement"]
    assert m["passed"] and abs(m["after"] - CFG.kpis[0].target) < 0.005 and m["before"] > 0.04
    v = versions(db_session)
    assert sorted(v) == [1, 2] and "Check the setpoint again" in v[2]
    learned = db_session.scalars(select(LearningEntry)).all()
    assert len(learned) == 1 and learned[0].domain == CFG.domain
    assert learned[0].content["root_cause"]["description"] == "wrong_setpoint"
    assert out["status"] == "completed" and out["events"][-1]["payload"]["status"] == "completed"
    acts = audit_actions(db_session)
    for a in ("propose_sop", "approval_decided", "apply_sop", "measure", "kpi_threshold_check", "save_learning"):
        assert a in acts


def test_proposal_without_sop_change_is_sent_back_before_anything_is_applied(db_session):
    # R9i: a proposal with an action but no SOP change never reaches Act; the corrected one does
    graph, _ = make(db_session, [*investigate_script(), improve_answer(sop=False), improve_answer()])
    cfg = cfg_run()
    start(graph, cfg)
    assert versions(db_session) == {} and "apply_sop" not in audit_actions(db_session)
    out = graph.invoke(Command(resume=HUMAN), cfg)
    applied = next(e for e in out["events"] if e["type"] == "sop_applied")
    assert applied["payload"]["applied"] is True
    assert out["status"] == "completed"


def test_repeated_runs_do_not_leak_state(db_session):
    seqs = []
    for i in range(2):
        graph, _ = make(db_session, [*investigate_script(), improve_answer()])
        cfg = cfg_run()
        start(graph, cfg, run_id=f"run_rep{i}")
        out = graph.invoke(Command(resume=HUMAN), cfg)
        seqs.append([e["event_id"].rsplit("_", 1)[1] for e in out["events"]])
        assert out.get("rejection_count", 0) == 0 and out.get("rollback_count", 0) == 0
    assert seqs[0] == seqs[1] and seqs[0][0] == "0001"


# ---- branch 2: KPI fails -> rollback after a person confirms ----


def rollback_script():
    # investigate + improve, then (after rollback) investigate + improve again
    # the fix targets a cause the simulator does not model, so KPI stays high and Measure fails
    wrong = investigate_script("sensor calibration drift")
    return [*wrong, wrong_improve_answer(), *wrong, wrong_improve_answer()]


def to_rollback_prompt(db_session):
    graph, llm = make(db_session, rollback_script(), tables=_tables())  # wrong cause: KPI stays high
    cfg = cfg_run()
    start(graph, cfg)
    calls = len(llm.calls)
    out = graph.invoke(Command(resume=HUMAN), cfg)
    assert len(llm.calls) == calls  # still no LLM after approval
    return graph, cfg, out, llm


def test_kpi_fail_proposes_rollback_and_waits_for_a_person(db_session):
    graph, cfg, out, _ = to_rollback_prompt(db_session)
    assert out["measurement"]["passed"] is False
    snap = graph.get_state(cfg)
    assert snap.next == ("wait_rollback",)
    assert snap.tasks[0].interrupts[0].value["kind"] == "rollback"
    assert "rollback_done" not in types(out) and "learning_saved" not in types(out)
    assert sorted(versions(db_session)) == [1, 2]  # nothing rolled back yet
    last = out["events"][-1]
    assert last["type"] == "proposal_created" and last["payload"]["proposal"]["kind"] == "rollback"


def test_rollback_confirmed_creates_new_version_and_returns_to_investigate(db_session):
    graph, cfg, _, llm = to_rollback_prompt(db_session)
    calls = len(llm.calls)
    out = graph.invoke(Command(resume={"decision": "approved", "decided_by": "bob"}), cfg)
    v = versions(db_session)
    assert sorted(v) == [1, 2, 3]  # old versions are kept
    assert v[3] == v[1] and v[2] != v[1]
    done = next(e for e in out["events"] if e["type"] == "rollback_done")
    assert done["payload"]["version"] == 3 and done["payload"]["restored_from_version"] == 1
    assert done["payload"]["approved_by"] == "bob"
    assert out["rollback_count"] == 1
    assert len(llm.calls) > calls  # went back to Investigate (LLM used there, not in the rollback)
    assert graph.get_state(cfg).next == ("wait_approval",)  # Investigate -> Improve -> approval again
    for ev in out["events"]:
        valid_event(ev)
    assert audit_actions(db_session).count("apply_sop") == 2


def test_rollback_declined_halts_without_changing_sop(db_session):
    graph, cfg, _, _ = to_rollback_prompt(db_session)
    out = graph.invoke(Command(resume={"decision": "rejected", "decided_by": "bob", "reason": "keep it"}), cfg)
    assert sorted(versions(db_session)) == [1, 2]
    assert "rollback_done" not in types(out)
    assert out["status"] == "awaiting_human"
    assert out["events"][-1]["payload"]["reason"] == "rollback_declined"
    assert graph.get_state(cfg).next == ("wait_halt",)  # R8/dev-05: waits for a person, not a dead end


def test_max_rollbacks_halts(db_session):
    cfg_l = CFG.model_copy(update={"loop": LoopParams(max_rejections=3, max_rollbacks=1)})
    graph, _ = make(db_session, rollback_script(), tables=_tables(), cfg=cfg_l)
    cfg = cfg_run()
    start(graph, cfg)
    graph.invoke(Command(resume=HUMAN), cfg)
    out = graph.invoke(Command(resume=HUMAN), cfg)
    assert out["status"] == "awaiting_human" and out["events"][-1]["payload"]["reason"] == "max_rollbacks_reached"


# ---- branch 3: proposal rejected -> Improve again ----


def test_rejected_proposal_returns_to_improve_and_applies_nothing(db_session):
    graph, llm = make(db_session, [*investigate_script(), improve_answer(), improve_answer()])
    cfg = cfg_run()
    start(graph, cfg)
    assert len(llm.calls) == 3
    out = graph.invoke(Command(resume={"decision": "rejected", "decided_by": "alice", "reason": "too risky"}), cfg)
    assert len(llm.calls) == 4  # Improve ran again
    assert graph.get_state(cfg).next == ("wait_approval",)
    assert out["rejection_count"] == 1
    assert versions(db_session) == {} and "apply_sop" not in audit_actions(db_session)
    rej = next(e for e in out["events"] if e["type"] == "approval_decided")
    assert rej["payload"]["decision"] == "rejected" and rej["payload"]["reason"] == "too risky"
    assert any(e.get("source") == "human_rejection" and e["reason"] == "too risky" for e in out["evidence"])
    assert "too risky" in json.dumps(llm.calls[-1]["messages"])  # the LLM sees the feedback
    out = graph.invoke(Command(resume=HUMAN), cfg)  # second proposal approved
    assert out["status"] == "completed"


def test_max_rejections_halts(db_session):
    cfg_l = CFG.model_copy(update={"loop": LoopParams(max_rejections=1, max_rollbacks=2)})
    graph, _ = make(db_session, [*investigate_script(), improve_answer()], cfg=cfg_l)
    cfg = cfg_run()
    start(graph, cfg)
    out = graph.invoke(Command(resume={"decision": "rejected", "decided_by": "alice"}), cfg)
    assert out["status"] == "awaiting_human" and out["events"][-1]["payload"]["reason"] == "max_rejections_reached"
    assert graph.get_state(cfg).next == ("wait_halt",)


# ---- decision validation ----


@pytest.mark.parametrize(
    "bad",
    [None, "yes", {}, {"decision": "maybe", "decided_by": "a"}, {"decision": "approved"},
     {"decision": "approved", "decided_by": "agent"}, {"decision": "approved", "decided_by": "  "},
     {"decision": "approved", "decided_by": "LLM"}, {"decision": "approved", "decided_by": "bot"},
     {"decision": "approved", "decided_by": "Claude"}, {"decision": "approved", "decided_by": "mallory"},
     {"decision": "approved", "decided_by": ""}],
)
def test_invalid_decision_rejected(bad):
    with pytest.raises(DecisionError):
        parse_decision(bad)


@pytest.mark.parametrize("name", [" ALICE ", "Bob", "qa_lead"])
def test_allow_listed_name_accepted_case_and_space_insensitive(name):
    d = parse_decision({"decision": "approved", "decided_by": name})
    assert d["decided_by"] in CFG.approvers


def test_decision_uses_given_config_allow_list():
    cfg = CFG.model_copy(update={"approvers": ["zed"]})
    assert parse_decision({"decision": "approved", "decided_by": "zed"}, cfg)["decided_by"] == "zed"
    with pytest.raises(DecisionError):
        parse_decision({"decision": "approved", "decided_by": "alice"}, cfg)


def test_valid_decision_defaults_reason():
    assert parse_decision(HUMAN) == {"decision": "approved", "decided_by": "alice", "reason": ""}


def test_invalid_resume_does_not_apply(db_session):
    graph, _ = make(db_session, [*investigate_script(), improve_answer()])
    cfg = cfg_run()
    start(graph, cfg)
    with pytest.raises(DecisionError):
        graph.invoke(Command(resume={"decision": "approved", "decided_by": "agent"}), cfg)
    assert versions(db_session) == {}


# ---- threshold decision is code, not LLM ----


def test_evaluate_kpi_boundaries():
    assert evaluate_kpi({"after": 0.025}, "decrease", 0.02, 0.25)  # equal to the limit passes
    assert not evaluate_kpi({"after": 0.0251}, "decrease", 0.02, 0.25)
    assert evaluate_kpi({"after": 0.9}, "increase", 0.9, 0.0)
    assert not evaluate_kpi({"after": 0.8}, "increase", 0.9, 0.05)
    with pytest.raises(ValueError):
        evaluate_kpi({"after": 1}, "sideways", 1, 0)


def test_measure_node_uses_threshold_from_config_and_no_llm(db_session):
    def run(cfg):
        node = make_measure_node(cfg, make_ctx(db_session, _fixed_tables()))
        s = new_state("run_m", CFG.domain)
        s["change_time"] = CHANGE
        s["anomaly"] = {"machine": "M02", "kpi": KPI}
        s["applied"] = {"change_time": CHANGE}  # no "sim": measure the tables as they are
        s["proposal"] = json.loads(improve_answer()) | {"hypothesis": {}}
        return node(s)

    assert run(CFG)["measurement"]["passed"] is True  # the node has no LLM parameter at all
    tight = CFG.model_copy(update={"kpis": [CFG.kpis[0].model_copy(update={"target": 0.001}), *CFG.kpis[1:]]})
    assert run(tight)["measurement"]["passed"] is False  # same data, config changes the verdict


def test_measure_requires_change_time(db_session):
    node = make_measure_node(CFG, make_ctx(db_session, _fixed_tables()))
    s = new_state("run_m", CFG.domain)
    s["proposal"] = json.loads(improve_answer())
    s["applied"] = {"sop_id": SOP_ID}  # applied, but no change_time anywhere
    with pytest.raises(ValueError, match="change_time"):
        node(s)


def test_act_records_change_time_from_anomaly_end_and_measure_uses_it(db_session):
    """No state['change_time']: Act derives it (anomaly end), stores it in applied; Measure reuses it."""
    ctx = make_ctx(db_session, _fixed_tables())
    s = new_state("run_act", CFG.domain)
    assert "change_time" not in s
    s["anomaly"] = {"machine": "M02", "kpi": KPI, "end": CHANGE}
    s["proposal"] = json.loads(improve_answer()) | {
        "hypothesis": {"description": "wrong_setpoint"}, "sop_proposal": {"sop_id": SOP_ID, "new_content": "Verify setpoint 180 again."},
    }
    s["approval"] = {"decision": "approved", "decided_by": "alice"}
    s.update(make_act_node(CFG, ctx)(s))
    assert s["applied"]["change_time"] == CHANGE
    m = make_measure_node(CFG, ctx)(s)["measurement"]
    assert m["change_time"].startswith(CHANGE) and m["passed"] is True


def test_default_state_without_change_time_uses_detected_anomaly_end(db_session):
    """No change_time in the state: the real Detect anomaly supplies its 'end' (resolve_change_time)."""
    graph, _ = make(db_session, [*investigate_script(), improve_answer()])
    cfg = cfg_run()
    s = new_state("run_act", CFG.domain)
    assert "change_time" not in s
    graph.invoke(s, cfg)
    anomaly = graph.get_state(cfg).values["anomaly"]
    out = graph.invoke(Command(resume=HUMAN), cfg)
    assert out["applied"]["change_time"] == anomaly["end"]
    assert "kpi_measured" in types(out) and types(out)[-1] == "run_finished"


def test_act_node_validates_change_time_before_apply_sop(db_session):
    ctx = make_ctx(db_session, _fixed_tables())
    s = new_state("run_act", CFG.domain)
    s["proposal"] = {"sop_proposal": {"sop_id": SOP_ID, "new_content": "x"}, "action": json.loads(improve_answer())["action"]}
    s["approval"] = {"decision": "approved", "decided_by": "alice"}
    with pytest.raises(ValueError, match="change_time"):
        make_act_node(CFG, ctx)(s)
    assert versions(db_session) == {} and "apply_sop" not in audit_actions(db_session)


def test_rollback_propose_survives_missing_after(db_session):
    from backend.agent.nodes.act import make_rollback_propose_node

    node = make_rollback_propose_node(CFG, make_ctx(db_session, _fixed_tables()))
    s = new_state("run_m", CFG.domain)
    s["measurement"] = {"kpi": KPI, "after": None}
    s["applied"] = None
    out = node(s)
    assert out["proposal"]["kind"] == "rollback"


def test_config_defaults_and_yaml_values():
    assert CFG.measure.window_days == 7 and CFG.measure.tolerance == 0.25
    assert CFG.loop.max_rejections == 3 and CFG.loop.max_rollbacks == 2


def test_full_loop_requires_llm_and_ctx():
    with pytest.raises(ValueError):
        build_graph(CFG, full_loop=True)
