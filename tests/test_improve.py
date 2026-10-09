"""R5/dev-01: Improve node (scripted LLM, seed 42, no network)."""

import json
from functools import cache
from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.agent.llm import ScriptedLLM
from backend.agent.nodes.improve import ProposalError, run_improvement
from backend.agent.state import Hypothesis, new_state
from backend.db.models import AuditLog, SopVersion
from backend.domain_config import load_domain_config
from backend.sandbox import generate_dataset
from backend.tools.readonly import ToolContext

CFG = load_domain_config()
KPI = CFG.kpis[0].name
SOP_ID = CFG.sop[0].id
SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "docs" / "schema" / "events.json").read_text())


@cache
def _tables():
    return generate_dataset(seed=42).tables


@pytest.fixture
def ctx(db_session):
    return ToolContext(tables=_tables(), session=db_session, run_id="run_imp")


def state():
    s = new_state("run_imp", CFG.domain)
    s["anomaly"] = {"kpi": KPI, "machine": "M02"}
    s["hypotheses"] = [
        Hypothesis(group="machine", description="wrong_setpoint", confidence=0.8),
        Hypothesis(group="people", description="new_operator", confidence=0.3),
    ]
    s["evidence"] = [{"source": "tool", "tool": "correlate", "result": {"r": 0.9}}]
    return s


def answer(**over):
    d = {
        "change": "Restore setpoint and add check step",
        "rationale": "Evidence 0 shows strong correlation with setpoint",
        "evidence_refs": [0],
        "expected_kpi": {"kpi": KPI, "direction": "decrease", "target": 0.02},
        "sop_change": {"sop_id": SOP_ID, "new_content": "step 1\nstep 2 verify setpoint"},
        "action": {"parameter": CFG.actions.parameters[0], "machine_id": "M02", "value": 180},
    }
    d.update(over)
    return json.dumps(d)


def drop(key):
    d = json.loads(answer())
    del d[key]
    return json.dumps(d)


def test_proposal_fields_and_sop_proposed(ctx):
    out = run_improvement(state(), CFG, ScriptedLLM([answer()]), ctx)
    p = out["proposal"]
    assert p["change"] and p["rationale"] and p["evidence_refs"] == [0]
    assert p["expected_kpi"]["kpi"] == KPI
    assert p["hypothesis"]["description"] == "wrong_setpoint"  # top by confidence
    assert p["sop_proposal"]["sop_id"] == SOP_ID and p["sop_proposal"]["status"] == "pending_approval"


def test_no_sop_change_is_rejected_and_makes_no_propose_call(ctx, db_session):
    # R9i: a proposal needs both sop_change and action; a rejected one proposes nothing
    d = json.loads(answer())
    del d["sop_change"]
    with pytest.raises(ProposalError, match="sop_change"):
        run_improvement(state(), CFG, ScriptedLLM([json.dumps(d)] * 2), ctx)
    n = db_session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "propose_sop"))
    assert n == 0


@pytest.mark.parametrize("key", ["change", "rationale", "evidence_refs", "expected_kpi"])
def test_missing_field_clear_error(ctx, key):
    with pytest.raises(ProposalError, match=key):
        run_improvement(state(), CFG, ScriptedLLM([drop(key)] * 2), ctx)


@pytest.mark.parametrize(
    "bad",
    [
        "not json at all",
        answer(evidence_refs=[]),
        answer(evidence_refs=[5]),
        answer(change=""),
        answer(expected_kpi={"kpi": "nope", "direction": "decrease", "target": 1}),
        answer(sop_change={"sop_id": "SOP-X", "new_content": "x"}),
    ],
)
def test_invalid_answers_raise(ctx, bad):
    with pytest.raises(ProposalError):
        run_improvement(state(), CFG, ScriptedLLM([bad, bad]), ctx)


def test_no_hypothesis_raises(ctx):
    s = state()
    s["hypotheses"] = []
    with pytest.raises(ProposalError):
        run_improvement(s, CFG, ScriptedLLM([answer()]), ctx)


def test_event_matches_schema_and_domain_from_config(ctx):
    s = state()
    s["domain"] = ""  # missing in state: domain must come from config
    out = run_improvement(s, CFG, ScriptedLLM([answer()]), ctx)
    (ev,) = out["events"]
    assert set(ev) == set(SCHEMA["required"])
    assert ev["type"] == "proposal_created" and ev["agent"] == "improvement"
    assert ev["domain"] == CFG.domain
    assert ev["type"] in SCHEMA["properties"]["type"]["enum"]
    assert ev["agent"] in SCHEMA["properties"]["agent"]["enum"]


def test_only_proposes_never_applies(ctx, db_session):
    run_improvement(state(), CFG, ScriptedLLM([answer()]), ctx)
    assert db_session.scalar(select(func.count()).select_from(SopVersion)) == 0
    tools = set(db_session.scalars(select(AuditLog.action)))
    assert "apply_sop" not in tools and "propose_sop" in tools


def test_repeat_calls_do_not_leak_state(ctx):
    s = state()
    a = run_improvement(s, CFG, ScriptedLLM([answer()]), ctx)
    b = run_improvement(s, CFG, ScriptedLLM([answer()]), ctx)
    assert a["proposal"]["sop_proposal"]["proposal_id"] != b["proposal"]["sop_proposal"]["proposal_id"]
    assert s["events"] == [] and s["proposal"] is None  # input state untouched
    assert a["events"][0]["event_id"] == b["events"][0]["event_id"]
