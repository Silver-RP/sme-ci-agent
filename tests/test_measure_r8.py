"""R8/dev-01: Measure on simulated post-change data (H1, H2); seed 42, scripted LLM, no network."""

import json

import pandas as pd
import pytest
from langgraph.types import Command
from sqlalchemy import select

from backend.agent.nodes.act import make_act_node, make_measure_node, resolve_change_time
from backend.agent.state import new_state
from backend.db.models import LearningEntry
from backend.domain_config import MeasureParams
from backend.sandbox.post_change import build_post_change_tables, fix_addresses_cause
from tests.test_act import (
    CFG,
    CHANGE,
    HUMAN,
    KPI,
    SOP_ID,
    _fixed_tables,
    _tables,
    audit_actions,
    cfg_run,
    improve_answer,
    investigate_script,
    make,
    make_ctx,
    start,
    types,
    versions,
)
from tests.test_api import make_client


def script_with(description="wrong_setpoint", improve=None):
    s = investigate_script()
    d = json.loads(s[1])
    d["hypotheses"][0]["description"] = description
    return [s[0], json.dumps(d), improve or improve_answer()]


def run_to_measure(db_session, script, tables=None, change_time=CHANGE, cfg=CFG):
    graph, _ = make(db_session, script, tables=tables or _tables(), cfg=cfg)
    c = cfg_run()
    s = new_state("run_r8", CFG.domain)
    s["change_time"] = change_time
    graph.invoke(s, c)
    out = graph.invoke(Command(resume=HUMAN), c)
    return graph, c, out


# ---- 1: right cause passes, wrong cause fails (raw data keeps the anomaly: only the simulator can fix it) ----


def test_fix_for_the_right_cause_brings_kpi_back_to_baseline(db_session):
    _, _, out = run_to_measure(db_session, script_with("wrong_setpoint"))
    m = out["measurement"]
    assert m["passed"] is True and m["status"] == "measured"
    assert m["before"] > 0.04 and abs(m["after"] - CFG.kpis[0].target) < 0.005
    assert out["status"] == "completed"


def test_fix_for_the_wrong_cause_does_not_pass(db_session):
    graph, c, out = run_to_measure(db_session, script_with("sensor calibration drift"))
    m = out["measurement"]
    assert m["passed"] is False and m["after"] > 0.04
    assert graph.get_state(c).next == ("wait_rollback",)
    assert "learning_saved" not in types(out)


def test_fix_addresses_cause_uses_hypothesis_text_only():
    assert fix_addresses_cause({"description": "wrong_setpoint"})
    assert fix_addresses_cause({"description": "Operator set the zone 3 setpoint to 195C"})
    assert not fix_addresses_cause({"description": "calibration drift"})
    assert not fix_addresses_cause({})
    assert not fix_addresses_cause(None)


def test_same_inputs_give_same_post_change_data():
    kw = {"kpi": KPI, "change_time": CHANGE, "machine_id": "M02", "fixed": True, "baseline": 0.02, "noise_sd": 0.004, "run_id": "r"}
    a = build_post_change_tables(_tables(), **kw)["kpi_log"]
    b = build_post_change_tables(_tables(), **kw)["kpi_log"]
    pd.testing.assert_frame_equal(a, b)


# ---- 2: the LLM cannot change the verdict (H2) ----


@pytest.mark.parametrize("hyp,expected", [("wrong_setpoint", True), ("sensor calibration drift", False)])
def test_llm_direction_and_kpi_do_not_change_the_verdict(db_session, hyp, expected):
    d = json.loads(improve_answer())
    d["expected_kpi"] = {"kpi": "rework_rate", "direction": "increase", "target": 0.9}
    _, _, out = run_to_measure(db_session, script_with(hyp, json.dumps(d)))
    m = out["measurement"]
    assert m["passed"] is expected
    assert m["kpi"] == KPI and m["direction"] == "decrease"  # anomaly KPI + config direction
    assert m["target"] == CFG.kpis[0].target


def test_direction_comes_from_the_kpi_config(db_session):
    inc = CFG.model_copy(update={"kpis": [CFG.kpis[0].model_copy(update={"direction": "increase", "target": 0.02}), *CFG.kpis[1:]]})
    _, _, out = run_to_measure(db_session, script_with("wrong_setpoint"), cfg=inc)
    assert out["measurement"]["direction"] == "increase"


# ---- 3: not enough samples after the change (H1) ----


def test_too_few_samples_is_not_enough_evidence_not_a_failure(db_session):
    late = "2026-06-29T22:00:00"
    graph, c, out = run_to_measure(db_session, script_with("wrong_setpoint"), change_time=late)
    m = out["measurement"]
    assert m["status"] == "insufficient_evidence" and m["passed"] is None
    assert m["n_after"] < CFG.measure.min_samples_after
    assert graph.get_state(c).next == ("wait_evidence",)  # waits for a person, no rollback
    assert "rollback" not in json.dumps([e["payload"] for e in out["events"] if e["type"] == "proposal_created"])
    q = [e for e in out["events"] if e["type"] == "question_asked"]
    assert q and "not enough" in q[-1]["payload"]["question"].lower()
    assert sorted(versions(db_session)) == [1, 2] and "learning_saved" not in types(out)


def test_insufficient_evidence_questions_are_bounded_then_halt(db_session):
    late = "2026-06-29T22:00:00"
    graph, c, out = run_to_measure(db_session, script_with("wrong_setpoint"), change_time=late)
    for _ in range(CFG.ask.max_questions):
        out = graph.invoke(Command(resume="wait for more data"), c)
    assert out["status"] == "awaiting_human"
    assert out["events"][-1]["payload"]["reason"] == "insufficient_evidence"
    assert graph.get_state(c).next == ("wait_halt",)


def test_min_samples_comes_from_config(db_session):
    late = "2026-06-29T22:00:00"
    easy = CFG.model_copy(update={"measure": MeasureParams(min_samples_after=1)})
    _, _, out = run_to_measure(db_session, script_with("wrong_setpoint"), change_time=late, cfg=easy)
    assert out["measurement"]["status"] == "measured"


def test_measure_node_with_empty_after_window_does_not_raise(db_session):
    node = make_measure_node(CFG, make_ctx(db_session, _tables()))
    s = new_state("run_m", CFG.domain)
    s["anomaly"] = {"machine": "M02", "kpi": KPI}
    s["change_time"] = "2026-07-30T00:00:00"  # beyond the data: only the Act/approval validation rejects this
    s["applied"] = {"change_time": s["change_time"], "sim": {"fixed": True, "machine_id": "M02"}}
    s["proposal"] = {"expected_kpi": {"kpi": KPI, "direction": "decrease", "target": 0.02}}
    m = node(s)["measurement"]
    assert m["status"] == "insufficient_evidence" and m["passed"] is None


# ---- 4: source data untouched ----


def test_source_tables_are_not_modified_by_a_run(db_session):
    tables = _tables()
    before = {n: df.copy() for n, df in tables.items()}
    ctx = make_ctx(db_session, tables)
    for hyp in ("wrong_setpoint", "sensor calibration drift"):
        graph, _ = make(db_session, script_with(hyp), tables=tables)
        c = cfg_run()
        graph.invoke({**new_state("run_src", CFG.domain), "change_time": CHANGE}, c)
        graph.invoke(Command(resume=HUMAN), c)
    for n, df in before.items():
        pd.testing.assert_frame_equal(tables[n], df)
    assert ctx.tables is tables


def test_repeated_runs_give_the_same_result(db_session):
    res = []
    for _ in range(2):
        _, _, out = run_to_measure(db_session, script_with("wrong_setpoint"))
        res.append(out["measurement"]["after"])
    assert res[0] == res[1]


# ---- change_time validation ----


def test_change_time_in_the_future_is_a_clear_error(db_session):
    graph, _ = make(db_session, script_with(), tables=_tables())
    s = {**new_state("run_f", CFG.domain), "change_time": "2027-01-01"}
    with pytest.raises(ValueError, match="future"):
        graph.invoke(s, cfg_run())
    assert versions(db_session) == {}


def test_change_time_before_the_anomaly_is_a_clear_error(db_session):
    graph, _ = make(db_session, script_with(), tables=_tables())
    s = {**new_state("run_f", CFG.domain), "change_time": "2026-02-01"}
    with pytest.raises(ValueError, match="before the anomaly"):
        graph.invoke(s, cfg_run())
    assert versions(db_session) == {}


def test_api_answers_422_for_a_bad_change_time(db_session):
    client = make_client(db_session, [script_with(), script_with()], tables=_tables())
    for bad in ("2027-01-01", "2026-02-01"):
        r = client.post("/runs", json={"change_time": bad})
        assert r.status_code == 422 and "change_time" in r.json()["detail"]


def test_default_change_time_leaves_room_for_the_after_window(db_session):
    s = new_state("run_d", CFG.domain)
    s["anomaly"] = {"machine": "M02", "kpi": KPI, "start": "2026-03-10T22:00:00", "end": "2026-06-30T22:00:00"}
    ct = pd.Timestamp(resolve_change_time(s, make_ctx(db_session, _tables())))
    last = _tables()["kpi_log"]["timestamp"].max()
    assert pd.Timestamp("2026-03-10T22:00:00") <= ct <= last - pd.Timedelta(days=CFG.measure.window_days)


# ---- no SOP change: never a "success" lesson ----


def test_proposal_without_sop_change_is_not_saved_as_success(db_session):
    graph, _ = make(db_session, script_with(improve=improve_answer(sop=False)), tables=_tables())
    c = cfg_run()
    start(graph, c)
    out = graph.invoke(Command(resume=HUMAN), c)
    assert out["measurement"]["status"] == "not_applied" and out["measurement"]["passed"] is None
    rows = db_session.scalars(select(LearningEntry)).all()
    assert all(r.content.get("outcome") != "success" for r in rows)
    assert "rollback_done" not in types(out)
    assert "apply_sop" not in audit_actions(db_session)


def test_act_records_what_the_simulator_needs(db_session):
    ctx = make_ctx(db_session, _fixed_tables())
    s = new_state("run_act", CFG.domain)
    s["change_time"] = CHANGE
    s["anomaly"] = {"machine": "M02", "kpi": KPI, "start": "2026-03-10T22:00:00"}
    s["proposal"] = json.loads(improve_answer()) | {
        "hypothesis": {"description": "wrong_setpoint"},
        "sop_proposal": {"sop_id": SOP_ID, "new_content": "Verify setpoint 180 again."},
    }
    s["approval"] = {"decision": "approved", "decided_by": "alice"}
    sim = make_act_node(CFG, ctx)(s)["applied"]["sim"]
    assert sim["fixed"] is True and sim["machine_id"] == "M02"
