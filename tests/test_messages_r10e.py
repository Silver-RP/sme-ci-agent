"""R10e/dev-01: user-facing sentences come from messages.* in the domain config (Vietnamese templates)."""

from pathlib import Path

import pytest
import yaml
from langgraph.types import Command
from pydantic import ValidationError

from backend.agent.nodes.act import (
    make_ask_evidence_node,
    make_loop_halt_node,
    make_measure_node,
    make_rollback_propose_node,
)
from backend.agent.nodes.ask import halt_options, halt_payload, make_ask_node
from backend.agent.state import Hypothesis, new_state
from backend.domain_config import (
    DEFAULT_PROFILE_PATH,
    HALT_REASON_CODES,
    LoopParams,
    load_domain_config,
)
from tests.test_act import (
    CFG,
    GROWING,
    HUMAN,
    KPI,
    SOP_ID,
    _fixed_tables,
    cfg_run,
    make,
    make_ctx,
    start,
    to_rollback_prompt,
)
from tests.test_measure_r8 import run_to_measure, script_with

MSG = CFG.messages


def _event(out, type_):
    return [e for e in out["events"] if e["type"] == type_]


# ---- 1: every branch uses the template from the config ----


def test_ask_questions_use_config_templates():
    ask = make_ask_node(CFG)
    s = new_state("run_msg", CFG.domain)
    s["hypotheses"] = []
    q = ask(s)["events"][0]["payload"]["question"]
    assert q == MSG.question_no_hypothesis
    s["hypotheses"] = [Hypothesis(group="machine", description="d1", confidence=0.9)]
    q = ask(s)["events"][0]["payload"]["question"]
    assert q == MSG.render("question_unsupported_hypothesis", group="machine", description="d1", confidence=0.9)
    s["hypotheses"] = [Hypothesis(group="machine", description="d2", confidence=0.3)]
    q = ask(s)["events"][0]["payload"]["question"]
    assert q == MSG.render(
        "question_low_confidence", group="machine", description="d2", confidence=0.3,
        threshold=CFG.ask.confidence_threshold,
    )
    assert "0.30" in q and "d2" in q


@pytest.mark.parametrize("reason", HALT_REASON_CODES)
def test_halt_payload_keeps_code_and_uses_vietnamese_label(reason):
    both = halt_payload(CFG, reason)
    only = halt_payload(CFG, reason, options=["finish"])
    label = MSG.halt_reasons[reason]
    assert both["reason"] == reason and only["reason"] == reason  # the code stays English
    assert both["question"] == MSG.render("halt_question_investigate", reason=label)
    assert only["question"] == MSG.render("halt_question_finish", reason=label)
    assert both["options"] == ["investigate", "finish"] and only["options"] == ["finish"]


def test_halt_payload_unknown_code_falls_back_to_the_code():
    assert "weird_code" in halt_payload(CFG, "weird_code")["question"]


def test_insufficient_evidence_question_and_halt(db_session):
    late = "2026-06-29T22:00:00"
    graph, c, out = run_to_measure(db_session, script_with("wrong_setpoint"), change_time=late, cfg=GROWING)
    m = out["measurement"]
    q =_event(out, "question_asked")[-1]["payload"]["question"]
    assert q == MSG.render(
        "evidence_wait_question", n_after=m["n_after"], n_unit=m["n_unit"], kpi=m["kpi"], needed=m["min_units_after"]
    )
    for _ in range(CFG.ask.max_questions):
        out = graph.invoke(Command(resume="wait"), c)
    halt = out["events"][-1]["payload"]
    assert halt["reason"] == "insufficient_evidence"
    assert halt["question"] == MSG.render(
        "halt_question_investigate", reason=MSG.halt_reasons["insufficient_evidence"]
    )


def test_ask_evidence_node_is_bounded_and_repeatable():
    node = make_ask_evidence_node(CFG)
    s = new_state("run_msg", CFG.domain)
    s["measurement"] = {"kpi": KPI, "n_after": 3, "n_unit": "points", "min_samples_after": 6}
    a = node(s)["events"][0]["payload"]["question"]
    b = node(s)["events"][0]["payload"]["question"]
    assert a == b == MSG.render("evidence_wait_question", n_after=3, n_unit="points", kpi=KPI, needed=6)


def test_rollback_proposal_uses_templates(db_session):
    _, _, out, _ = to_rollback_prompt(db_session)
    prop = _event(out, "proposal_created")[-1]["payload"]["proposal"]
    m = out["measurement"]
    applied = out["applied"]
    assert prop["kind"] == "rollback"
    assert prop["change"] == MSG.render(
        "rollback_change_sop", sop_id=applied["sop_id"], previous_version=applied["previous_version"]
    )
    assert prop["rationale"] == MSG.render(
        "rollback_rationale", kpi=m["kpi"], after=f"{m['after']:.4f}", target=m["target"], tolerance=m["tolerance"]
    )


def test_rollback_without_sop_version_uses_the_other_template(db_session):
    node = make_rollback_propose_node(CFG, make_ctx(db_session, _fixed_tables()))
    s = new_state("run_msg", CFG.domain)
    s["measurement"] = {"kpi": KPI, "after": None}
    s["applied"] = {"sop_id": SOP_ID, "previous_version": 1}  # no previous_content -> no SOP proposal
    prop = node(s)["proposal"]
    assert prop["change"] == MSG.render("rollback_change_no_sop")
    assert "n/a" in prop["rationale"]


def test_max_rollbacks_halt_uses_template(db_session):
    from tests.test_act import rollback_script

    cfg_l = CFG.model_copy(update={"loop": LoopParams(max_rejections=3, max_rollbacks=1)})
    from tests.test_act import _tables

    graph, _ = make(db_session, rollback_script(), tables=_tables(), cfg=cfg_l)
    cfg = cfg_run()
    start(graph, cfg)
    graph.invoke(Command(resume=HUMAN), cfg)
    out = graph.invoke(Command(resume=HUMAN), cfg)
    p = out["events"][-1]["payload"]
    assert p["reason"] == "max_rollbacks_reached"
    assert p["question"] == MSG.render("halt_question_investigate", reason=MSG.halt_reasons["max_rollbacks_reached"])


def test_loop_halt_node_covers_each_reason_with_a_label():
    node = make_loop_halt_node(CFG)
    s = new_state("run_msg", CFG.domain)
    s["rejection_count"] = 3
    p = node(s)["events"][0]["payload"]
    assert p["reason"] == "max_rejections_reached"
    assert p["question"] == MSG.render("halt_question_investigate", reason=MSG.halt_reasons[p["reason"]])
    s["rollback_total"] = CFG.loop.max_total_rollbacks
    assert halt_options(s, CFG) == ["finish"]
    p = node(s)["events"][0]["payload"]
    assert p["question"] == MSG.render("halt_question_finish", reason=MSG.halt_reasons["max_total_rollbacks_reached"])


def test_not_applied_reasons_use_templates(db_session):
    ctx = make_ctx(db_session, _fixed_tables())
    measure = make_measure_node(CFG, ctx)
    s = new_state("run_msg", CFG.domain)
    s["anomaly"] = {"kpi": KPI, "machine_id": "M02", "start": "2026-03-01T00:00:00", "end": "2026-03-10T00:00:00"}
    s["applied"] = None  # no SOP changed
    out = measure(s)
    assert out["measurement"]["status"] == "not_applied"
    assert out["measurement"]["reason"] == MSG.render("not_applied_no_sop")
    s["applied"] = {"sop_id": SOP_ID, "version": 2, "previous_version": 1, "sim": {"machine_id": "M02"}}  # no action
    out = measure(s)
    assert out["measurement"]["reason"] == MSG.render("not_applied_no_action")


def test_sop_conflict_message_uses_template(db_session):
    from backend.agent.nodes.act import _conflict_text
    from backend.tools.actions import SopConflict

    assert _conflict_text(CFG, SopConflict(SOP_ID, 1, 3)) == MSG.render(
        "sop_conflict", sop_id=SOP_ID, base_version=1, current_version=3
    )


# ---- 2: no English display literal left in backend/ ----

ENGLISH_LITERALS = [
    "Evidence is insufficient to form a hypothesis",
    "Top hypothesis (",
    "Can you confirm",
    "The agent stopped (",
    "Not enough evidence yet",
    "Wait for more data and confirm",
    "Roll back SOP",
    "Roll back the change",
    "outside the limit",
    "the proposal changed no SOP",
    "the proposal has no structured action, so no machine",
]


def test_no_english_display_literal_left_in_backend():
    root = Path(__file__).resolve().parents[1] / "backend"
    hits = []
    for f in root.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        hits += [(f.name, lit) for lit in ENGLISH_LITERALS if lit in text]
    assert hits == []


# ---- 3: missing / bad keys fail at load, naming the key ----


def _raw():
    return yaml.safe_load(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))


def _write(tmp_path, data):
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return p


@pytest.mark.parametrize(
    "key",
    [k for k in _raw()["messages"] if k != "halt_reasons"],
)
def test_missing_message_key_names_the_key(tmp_path, key):
    data = _raw()
    del data["messages"][key]
    with pytest.raises(ValidationError, match=key):
        load_domain_config(_write(tmp_path, data))


def test_missing_messages_block_and_halt_reason_fail(tmp_path):
    data = _raw()
    del data["messages"]
    with pytest.raises(ValidationError, match="messages"):
        load_domain_config(_write(tmp_path, data))
    data = _raw()
    del data["messages"]["halt_reasons"]["max_rejections_reached"]
    with pytest.raises(ValidationError, match="max_rejections_reached"):
        load_domain_config(_write(tmp_path, data))


def test_unknown_placeholder_names_the_key(tmp_path):
    data = _raw()
    data["messages"]["rollback_change_sop"] = "Hoàn tác {nope}"
    with pytest.raises(ValidationError, match="rollback_change_sop"):
        load_domain_config(_write(tmp_path, data))
