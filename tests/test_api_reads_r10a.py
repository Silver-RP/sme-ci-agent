"""R10a/dev-01: read-only GET /runs, /audit, /sop/{id}/versions (scripted LLM, seed 42, no network)."""

from sqlalchemy import func, select

from backend.db.models import AuditLog, SopVersion
from tests.test_act import HUMAN, SOP_ID, approve, improve_answer, investigate_script
from tests.test_api import make_client, start

RUN_KEYS = {"run_id", "state", "started_at", "finished_at", "outcome", "pending"}
AUDIT_KEYS = {"id", "ts", "run_id", "actor", "action", "params"}
VERSION_KEYS = {"version", "created_by", "run_id", "created_at", "content"}


def finished_run(client):
    run = start(client)
    r = approve(client, run["run_id"], HUMAN)
    assert r.status_code == 200 and r.json()["state"] == "finished", r.text
    return run["run_id"]


def counts(session):
    return (
        session.scalar(select(func.count()).select_from(AuditLog)),
        session.scalar(select(func.count()).select_from(SopVersion)),
    )


def test_runs_lists_finished_run_with_outcome_newest_first(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]] * 2)
    assert client.get("/runs").json() == {"runs": []}  # empty app
    first = finished_run(client)
    second = start(client)["run_id"]  # still waiting for approval
    runs = client.get("/runs").json()["runs"]
    assert [r["run_id"] for r in runs] == [second, first]  # newest first
    done = runs[1]
    assert set(done) == RUN_KEYS
    assert done["state"] == "finished" and done["outcome"] == "completed"
    assert done["started_at"] and done["finished_at"] and done["pending"] is None
    waiting = runs[0]
    assert set(waiting) == RUN_KEYS
    assert waiting["state"] == "waiting" and waiting["outcome"] is None and waiting["finished_at"] is None
    assert waiting["pending"]["type"] == "approval" and waiting["pending"]["kind"] == "proposal"
    assert "proposal" not in waiting["pending"]  # a summary, not the whole card
    assert client.get("/runs").json() == {"runs": runs}  # repeated call: same answer


def test_audit_has_human_approval_row_for_run(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run_id = finished_run(client)
    rows = client.get("/audit", params={"run_id": run_id}).json()["rows"]
    assert rows and all(set(r) == AUDIT_KEYS and r["run_id"] == run_id for r in rows)
    approval = [r for r in rows if r["action"] == "approval_decided"]
    assert approval and approval[0]["actor"] == HUMAN["decided_by"]
    assert [r["id"] for r in rows] == sorted((r["id"] for r in rows), reverse=True)  # newest first
    assert client.get("/audit", params={"run_id": "run_nope"}).json()["rows"] == []
    assert len(client.get("/audit", params={"limit": 1}).json()["rows"]) == 1
    assert len(client.get("/audit").json()["rows"]) >= len(rows)


def test_sop_versions_has_new_version_and_keeps_old(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run_id = finished_run(client)
    body = client.get(f"/sop/{SOP_ID}/versions").json()
    assert body["sop_id"] == SOP_ID
    versions = body["versions"]
    assert all(set(v) == VERSION_KEYS for v in versions)
    assert [v["version"] for v in versions] == [1, 2]  # oldest first
    assert versions[0]["created_by"] == "config" and "Verify" in versions[0]["content"]
    assert versions[1]["run_id"] == run_id and versions[1]["created_by"] == HUMAN["decided_by"]
    assert "Check the setpoint again" in versions[1]["content"]
    assert versions[1]["created_at"]


def test_sop_versions_before_any_run_is_the_config_version(db_session):
    client = make_client(db_session, [])
    versions = client.get(f"/sop/{SOP_ID}/versions").json()["versions"]
    assert len(versions) == 1 and versions[0]["created_by"] == "config" and versions[0]["run_id"] is None


def test_unknown_sop_is_404(db_session):
    client = make_client(db_session, [])
    assert client.get("/sop/SOP-NOPE/versions").status_code == 404


def test_audit_limit_is_validated(db_session):
    client = make_client(db_session, [])
    for bad in (-1, 0, 10**6, "abc"):
        assert client.get("/audit", params={"limit": bad}).status_code == 422, bad


def test_read_apis_do_not_write_the_db(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run_id = finished_run(client)
    before = counts(db_session)
    for _ in range(2):
        assert client.get("/runs").status_code == 200
        assert client.get("/audit", params={"run_id": run_id}).status_code == 200
        assert client.get("/audit").status_code == 200
        assert client.get(f"/sop/{SOP_ID}/versions").status_code == 200
    assert counts(db_session) == before
    for method in (client.post, client.put, client.delete):
        assert method("/audit").status_code in (404, 405)
        assert method(f"/sop/{SOP_ID}/versions").status_code in (404, 405)
