"""dev-04 (R4): action tools, T-023. Seed 42 sandbox data + Postgres."""

from functools import cache

import pytest
from sqlalchemy import func, select

from backend.db.models import AuditLog, LearningEntry, SopVersion
from backend.domain_config import load_domain_config
from backend.sandbox import generate_dataset
from backend.tools.actions import TOOLS, apply_sop, measure, propose_sop, save_learning
from backend.tools.readonly import ToolContext

CFG = load_domain_config()
KPI = CFG.kpis[0].name
SOP_ID = CFG.sop[0].id
A1_START = "2026-03-10T22:00:00"
APPROVAL = {"decision": "approved", "approved_by": "alice"}


@cache
def _tables():
    return generate_dataset(seed=42).tables


@pytest.fixture
def ctx(db_session):
    return ToolContext(tables=_tables(), session=db_session, run_id=None)


def n(s, model):
    return s.scalar(select(func.count()).select_from(model))


def versions(s, sop_id=SOP_ID):
    rows = s.scalars(select(SopVersion).where(SopVersion.sop_id == sop_id)).all()
    return {r.version: r.content for r in rows}


# 1. apply_sop needs approval
@pytest.mark.parametrize(
    "approval",
    [
        None,
        {},
        {"decision": "rejected", "approved_by": "alice"},
        {"decision": "approved"},
        {"decision": "approved", "approved_by": "agent"},
        {"decision": "approved", "approved_by": "llm"},
        {"decision": "approved", "approved_by": "bot"},
        {"decision": "approved", "approved_by": "claude"},
        {"decision": "approved", "approved_by": "system"},
        {"decision": "approved", "approved_by": "  "},
        {"decision": "approved", "approved_by": "mallory"},
        {"decision": "approved", "approved_by": "alice", "sop_id": "OTHER"},
        {"decision": "approved", "approved_by": "alice"},  # no sop_id: not accepted
        {"decision": "approved", "approved_by": "alice", "sop_id": None},
    ],
)
def test_apply_without_valid_approval_refused(ctx, approval):
    before = versions(ctx.session)
    with pytest.raises(PermissionError):
        apply_sop(ctx, sop_id=SOP_ID, new_content="x", approval=approval)
    assert versions(ctx.session) == before


def test_apply_accepts_listed_name_case_insensitive(ctx):
    r = apply_sop(ctx, sop_id=SOP_ID, new_content="x", approval={"decision": "approved", "approved_by": " Bob ", "sop_id": SOP_ID})
    assert r["approved_by"] == "bob"


def test_apply_without_approval_argument_refused(ctx):
    with pytest.raises(PermissionError):
        apply_sop(ctx, sop_id=SOP_ID, new_content="x")
    assert versions(ctx.session) == {}


def test_apply_with_approval_bumps_version_and_keeps_old(ctx):
    r1 = apply_sop(ctx, sop_id=SOP_ID, new_content="step A", approval={**APPROVAL, "sop_id": SOP_ID})
    assert r1["version"] == 2 and r1["approved_by"] == "alice"  # config has v1
    v = versions(ctx.session)
    assert set(v) == {1, 2} and v[2] == "step A"
    assert v[1] == "\n".join(CFG.sop[0].steps)  # old version intact
    r2 = apply_sop(ctx, sop_id=SOP_ID, new_content="step B", approval={**APPROVAL, "sop_id": SOP_ID})
    assert r2["version"] == 3
    v = versions(ctx.session)
    assert v[2] == "step A" and v[3] == "step B"


def test_apply_new_sop_id_starts_at_one_and_empty_content_rejected(ctx):
    assert apply_sop(ctx, sop_id="NEW", new_content="a", approval={**APPROVAL, "sop_id": "NEW"})["version"] == 1
    with pytest.raises(ValueError):
        apply_sop(ctx, sop_id="NEW", new_content="  ", approval={**APPROVAL, "sop_id": "NEW"})


# 2. propose_sop does not change sop_versions
def test_propose_does_not_touch_sop_versions(ctx):
    r = propose_sop(ctx, sop_id=SOP_ID, new_content="new", rationale="why", kpi=KPI)
    assert r["status"] == "pending_approval" and r["base_version"] == 1
    assert r["proposal_id"]
    assert n(ctx.session, SopVersion) == 0
    again = propose_sop(ctx, sop_id=SOP_ID, new_content="new", rationale="why")
    assert again["proposal_id"] != r["proposal_id"] and n(ctx.session, SopVersion) == 0
    with pytest.raises(ValueError):
        propose_sop(ctx, sop_id=SOP_ID, new_content="", rationale="r")
    with pytest.raises(ValueError):
        propose_sop(ctx, sop_id=SOP_ID, new_content="x", rationale="r", kpi="nope")


# 3. measure
def test_measure_a1_direction_and_mttd_mttr(ctx):
    r = measure(
        ctx,
        kpi=KPI,
        change_time=A1_START,
        window_days=5,
        machine_id="M02",
        started_at=A1_START,
        detected_at="2026-03-11T02:00:00",
        resolved_at="2026-03-11T10:30:00",
    )
    assert r["after"] > r["before"] * 2 and r["delta"] == pytest.approx(r["after"] - r["before"])
    assert r["mttd_hours"] == pytest.approx(4.0)
    assert r["mttr_hours"] == pytest.approx(8.5)
    assert r["n_before"] > 0 and r["n_after"] > 0


def test_measure_defaults_and_missing_times(ctx):
    r = measure(ctx, kpi=KPI, change_time=A1_START)  # default window, all machines
    assert r["mttd_hours"] is None and r["mttr_hours"] is None
    r2 = measure(ctx, kpi=KPI, change_time=A1_START, started_at=A1_START, detected_at=A1_START)
    assert r2["mttd_hours"] == 0 and r2["mttr_hours"] is None
    assert measure(ctx, kpi=KPI, change_time=A1_START) == r  # repeat call: same result


def test_measure_bad_params(ctx):
    with pytest.raises(ValueError):
        measure(
            ctx, kpi=KPI, change_time=A1_START, started_at="2026-03-11", detected_at="2026-03-10"
        )
    with pytest.raises(ValueError):
        measure(
            ctx, kpi=KPI, change_time=A1_START, detected_at="2026-03-11", resolved_at="2026-03-10"
        )
    with pytest.raises(ValueError):
        measure(ctx, kpi=KPI, change_time=A1_START, window_days=0)
    with pytest.raises(ValueError):
        measure(ctx, kpi="nope", change_time=A1_START)
    with pytest.raises(ValueError):  # no data in windows
        measure(ctx, kpi=KPI, change_time="2030-01-01")


def test_measure_uses_only_kpi_log(ctx):
    tables = {"kpi_log": _tables()["kpi_log"]}  # nothing else, in particular no ground truth
    c = ToolContext(tables=tables, session=ctx.session)
    assert measure(c, kpi=KPI, change_time=A1_START)["after"] > 0


# save_learning
def test_save_learning_uses_config_domain(ctx):
    r = save_learning(ctx, content={"lesson": "check setpoint"})
    assert r["domain"] == CFG.domain
    row = ctx.session.get(LearningEntry, r["id"])
    assert row.content == {"lesson": "check setpoint"}
    with pytest.raises(ValueError):
        save_learning(ctx, content={})


# 4. exactly one audit row per call (including refused / failed calls)
def test_one_audit_row_per_call(ctx):
    calls = [
        lambda: propose_sop(ctx, sop_id=SOP_ID, new_content="n", rationale="r"),
        lambda: apply_sop(ctx, sop_id=SOP_ID, new_content="n", approval={**APPROVAL, "sop_id": SOP_ID}),
        lambda: apply_sop(ctx, sop_id=SOP_ID, new_content="n"),  # refused
        lambda: measure(ctx, kpi=KPI, change_time=A1_START),
        lambda: measure(ctx, kpi=KPI, change_time=A1_START, window_days=-1),  # error
        lambda: save_learning(ctx, content={"a": 1}),
    ]
    expected = ["propose_sop", "apply_sop", "apply_sop", "measure", "measure", "save_learning"]
    for call in calls:
        before = n(ctx.session, AuditLog)
        try:
            call()
        except (PermissionError, ValueError):
            pass
        assert n(ctx.session, AuditLog) == before + 1
    rows = ctx.session.scalars(select(AuditLog).order_by(AuditLog.id)).all()
    assert [r.action for r in rows] == expected


# 5. no hidden "defect"
def test_no_hardcoded_defect_name():
    import inspect

    from backend.tools import actions

    assert "defect" not in inspect.getsource(actions).lower()
    assert set(TOOLS) == {"propose_sop", "apply_sop", "measure", "save_learning"}
