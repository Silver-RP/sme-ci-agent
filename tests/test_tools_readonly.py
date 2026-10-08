"""dev-03 (M3): read-only tools, T-014. Seed 42 sandbox data + Postgres audit_log."""

import inspect
from functools import cache

import pandas as pd
import pytest
from sqlalchemy import func, select

from backend.db import repo
from backend.db.models import AuditLog
from backend.domain_config import load_domain_config
from backend.sandbox import generate_dataset
from backend.tools import readonly
from backend.tools.readonly import (
    ToolContext,
    correlate,
    get_shift_schedule,
    query_logs,
    read_sop,
)

CFG = load_domain_config()
KPI = CFG.kpis[0].name
OTHER_KPI = CFG.kpis[1].name
A1_START = "2026-03-10T22:00:00"


@cache
def _tables():
    return generate_dataset(seed=42).tables


@pytest.fixture
def ctx(db_session):
    return ToolContext(tables=_tables(), session=db_session, run_id=None)


def audit_count(s):
    return s.scalar(select(func.count()).select_from(AuditLog))


# 1a. query_logs filters by KPI / machine / time
def test_query_logs_filters(ctx):
    r = query_logs(ctx, kpi=KPI, machine_id="M02", start="2026-03-10", end="2026-03-12")
    assert r["count"] == 6 and len(r["rows"]) == 6  # 2 days x 3 shifts
    assert {x["machine_id"] for x in r["rows"]} == {"M02"}
    assert {x["kpi"] for x in r["rows"]} == {KPI}
    assert all("2026-03-10" <= x["timestamp"] < "2026-03-12" for x in r["rows"])
    night = [x for x in r["rows"] if x["shift"] == "night"]
    assert night[0]["timestamp"].startswith(A1_START[:10]) and night[0]["value"] > 0.05


def test_query_logs_other_kpi_and_unfiltered_and_empty(ctx):
    assert query_logs(ctx, kpi=OTHER_KPI, machine_id="M02")["count"] == 0  # none in sandbox
    all_m = query_logs(ctx, kpi=KPI, start="2026-03-10", end="2026-03-11")
    assert {x["machine_id"] for x in all_m["rows"]} == {"M01", "M02", "M03"}
    assert query_logs(ctx, kpi=KPI, machine_id="M99")["rows"] == []
    assert query_logs(ctx, kpi=KPI, start="2030-01-01")["count"] == 0
    with pytest.raises(ValueError):
        query_logs(ctx, kpi="not_a_kpi")


def test_query_logs_machine_log(ctx):
    r = query_logs(ctx, kpi=KPI, source="machine_log", machine_id="M02", end="2026-03-11")
    sp = [x for x in r["rows"] if x["event_type"] == "setpoint_change"]
    assert len(sp) == 1 and sp[0]["old_value"] == 180 and sp[0]["new_value"] == 195
    assert sp[0]["timestamp"] == A1_START
    with pytest.raises(ValueError):
        query_logs(ctx, kpi=KPI, source="inventory")


# 1b. schedule: substitutes around A1
def test_shift_schedule_substitutes_around_a1(ctx):
    r = get_shift_schedule(ctx, machine_id="M02", shift="night", start="2026-03-08", end="2026-03-14")
    assert r["count"] == 6
    subs = r["substitutes"]
    assert [s["date"][:10] for s in subs] == ["2026-03-09", "2026-03-10", "2026-03-11"]
    assert {s["operator_id"] for s in subs} == {"OP-SUB01"}
    far = get_shift_schedule(ctx, machine_id="M02", shift="night", start="2026-05-01", end="2026-05-05")
    assert far["substitutes"] == [] and far["count"] == 4
    assert get_shift_schedule(ctx, machine_id="M01", start="2026-03-09", end="2026-03-12")["substitutes"] == []


# 1c. SOP by id and version
def test_read_sop_by_id_and_version(ctx):
    r = read_sop(ctx, sop_id="SOP-RFL-001", version=1)
    assert r["found"] and r["version"] == 1 and "setpoint" in r["content"].lower()
    assert r["steps"] == CFG.sop[0].steps
    assert read_sop(ctx, sop_id="SOP-RFL-001")["version"] == 1  # default = latest
    assert read_sop(ctx, sop_id="SOP-RFL-001", version=9)["found"] is False
    assert read_sop(ctx, sop_id="NOPE")["found"] is False


def test_read_sop_picks_up_db_versions(ctx, db_session):
    repo.add_sop_version(db_session, "SOP-RFL-001", "step A\nstep B")  # version 1 in DB (overrides)
    repo.add_sop_version(db_session, "SOP-RFL-001", "step A\nstep B\nstep C")
    latest = read_sop(ctx, sop_id="SOP-RFL-001")
    assert latest["version"] == 2 and latest["steps"][-1] == "step C" and latest["source"] == "db"
    v1 = read_sop(ctx, sop_id="SOP-RFL-001", version=1)
    assert v1["steps"] == ["step A", "step B"]
    assert read_sop(ctx, sop_id="SOP-RFL-001", version=1)["available_versions"] == [1, 2]


# 1d. correlate: setpoint beats the distractors
def test_correlate_setpoint_beats_distractors(ctx):
    r = correlate(ctx, kpi=KPI, machine_id="M02", start="2026-03-03", end="2026-03-17")
    by = {c["hypothesis"]: c for c in r["correlations"]}
    assert r["correlations"][0]["hypothesis"] == "wrong_setpoint"
    assert by["wrong_setpoint"]["r"] > 0.9
    for distractor in ("material_batch", "ambient_temperature"):
        assert by[distractor]["strength"] < by["wrong_setpoint"]["strength"]
        assert by[distractor]["strength"] < 0.5
    assert by["ambient_temperature"]["status"] == "no_data"
    assert set(by) == {h for g in CFG.hypothesis_groups.values() for h in g}  # from config


def test_correlate_explicit_hypotheses_and_empty(ctx):
    r = correlate(ctx, kpi=KPI, machine_id="M02", start="2026-03-03", end="2026-03-17",
                  hypotheses=["material_batch"])
    assert [c["hypothesis"] for c in r["correlations"]] == ["material_batch"]
    # machine without setpoint change: no data for wrong_setpoint; empty window: no crash
    r2 = correlate(ctx, kpi=KPI, machine_id="M03", start="2026-03-03", end="2026-03-17",
                   hypotheses=["wrong_setpoint"])
    assert r2["correlations"][0]["status"] == "no_data"
    r3 = correlate(ctx, kpi=KPI, machine_id="M02", start="2030-01-01")
    assert all(c["status"] == "no_data" and c["strength"] == 0.0 for c in r3["correlations"])
    with pytest.raises(ValueError):
        correlate(ctx, kpi="nope", machine_id="M02")


# 2. no change to input data
def test_tools_do_not_modify_source_tables(ctx):
    before = {k: v.copy(deep=True) for k, v in ctx.tables.items()}
    query_logs(ctx, kpi=KPI, machine_id="M02")
    query_logs(ctx, kpi=KPI, source="machine_log")
    get_shift_schedule(ctx, machine_id="M02")
    read_sop(ctx, sop_id="SOP-RFL-001")
    correlate(ctx, kpi=KPI, machine_id="M02", start="2026-03-03", end="2026-03-17")
    assert before.keys() == ctx.tables.keys()
    for k, frame in before.items():
        pd.testing.assert_frame_equal(frame, ctx.tables[k])


def test_tools_leave_db_data_tables_untouched(ctx, db_session):
    repo.add_sop_version(db_session, "SOP-X", "c")
    from backend.db.models import SopVersion

    n = db_session.scalar(select(func.count()).select_from(SopVersion))
    read_sop(ctx, sop_id="SOP-X")
    assert db_session.scalar(select(func.count()).select_from(SopVersion)) == n


# 3. exactly one audit row per call
def test_one_audit_row_per_call(ctx, db_session):
    ctx.run_id = None
    calls = [
        ("query_logs", lambda: query_logs(ctx, kpi=KPI, machine_id="M02", start="2026-03-10")),
        ("get_shift_schedule", lambda: get_shift_schedule(ctx, machine_id="M02")),
        ("read_sop", lambda: read_sop(ctx, sop_id="SOP-RFL-001", version=1)),
        ("correlate", lambda: correlate(ctx, kpi=KPI, machine_id="M02", start="2026-03-03", end="2026-03-17")),
    ]
    for name, call in calls:
        n = audit_count(db_session)
        call()
        assert audit_count(db_session) == n + 1
        row = db_session.scalars(select(AuditLog).order_by(AuditLog.id.desc())).first()
        assert row.action == name and row.actor == "agent"
        assert isinstance(row.params, dict)


def test_audit_params_recorded_and_repeat_calls_logged(ctx, db_session):
    repo.create_run(db_session, "run_t", "manufacturing")
    ctx.run_id = "run_t"
    query_logs(ctx, kpi=KPI, machine_id="M02", start="2026-03-10", end="2026-03-12")
    query_logs(ctx, kpi=KPI, machine_id="M02", start="2026-03-10", end="2026-03-12")
    rows = db_session.scalars(select(AuditLog).where(AuditLog.run_id == "run_t")).all()
    assert len(rows) == 2  # repeated call: no state leak, one row each
    assert rows[0].params == {
        "kpi": KPI, "machine_id": "M02", "start": "2026-03-10", "end": "2026-03-12"
    }
    assert rows[0].params == rows[1].params


def test_failed_call_still_audited_once(ctx, db_session):
    n = audit_count(db_session)
    with pytest.raises(ValueError):
        query_logs(ctx, kpi="nope")
    assert audit_count(db_session) == n + 1


# 4. no hard-coded "defect"
def test_no_defect_naming_in_tools():
    src = inspect.getsource(readonly).lower()
    assert "defect" not in src
    for fn in (query_logs, correlate, get_shift_schedule, read_sop):
        sig = inspect.signature(fn)
        assert not any("defect" in p for p in sig.parameters)
    assert "kpi" in inspect.signature(query_logs).parameters
    assert "kpi" in inspect.signature(correlate).parameters
    assert set(readonly.TOOLS) == {"query_logs", "correlate", "get_shift_schedule", "read_sop"}
