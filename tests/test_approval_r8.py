"""R8/dev-04: approval bound to the proposal and kind that were shown (H5); apply_sop needs a matching sop_id."""

import pytest
from sqlalchemy import select

from backend.agent.nodes.act import proposal_fingerprint
from backend.db.models import AuditLog
from tests.test_act import HUMAN, _tables, approve, improve_answer, investigate_script
from tests.test_api import make_client, sse_events, start


def rollback_run(db_session):
    wrong = investigate_script("sensor calibration drift")  # the simulator does not fix this: KPI stays high
    client = make_client(db_session, [[*wrong, improve_answer(), *wrong, improve_answer()]], tables=_tables())
    return client, start(client)


def audits(db_session, action):
    return [a.params for a in db_session.scalars(select(AuditLog).where(AuditLog.action == action))]


def test_pending_approval_has_proposal_id_kind_and_hash(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    p = run["pending"]
    assert p["kind"] == "proposal" and p["proposal_id"] and len(p["proposal_hash"]) == 64
    assert p["proposal_hash"] == proposal_fingerprint(p["proposal"])["proposal_hash"]
    assert client.get(f"/runs/{run['run_id']}").json()["pending"]["proposal_id"] == p["proposal_id"]  # stable


def test_second_approval_after_graph_moved_to_rollback_is_409_and_rollback_not_decided(db_session):
    client, run = rollback_run(db_session)
    rid = run["run_id"]
    first = run["pending"]
    stale = {**HUMAN, "proposal_id": first["proposal_id"], "kind": first["kind"]}
    r = client.post(f"/runs/{rid}/approval", json=stale)
    assert r.status_code == 200 and r.json()["pending"]["kind"] == "rollback"
    again = client.post(f"/runs/{rid}/approval", json=stale)  # a double click with the same body
    assert again.status_code == 409
    now = client.get(f"/runs/{rid}").json()
    assert now["pending"]["kind"] == "rollback" and now["state"] == "waiting"
    types = [m["event"] for m in sse_events(client, rid)]
    assert "rollback_done" not in types and types.count("approval_decided") == 1
    assert [a["kind"] for a in audits(db_session, "approval_decided")] == ["proposal"]


@pytest.mark.parametrize("override", [{"kind": "rollback"}, {"proposal_id": "someoneelse"}, {"proposal_id": "x", "kind": "rollback"}])
def test_wrong_kind_or_proposal_id_is_409_and_changes_nothing(db_session, override):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    r = approve(client, run["run_id"], HUMAN, **override)
    assert r.status_code == 409
    assert client.get(f"/runs/{run['run_id']}").json()["state"] == "waiting"
    assert "sop_applied" not in [m["event"] for m in sse_events(client, run["run_id"])]
    assert audits(db_session, "approval_decided") == []
    ok = approve(client, run["run_id"], HUMAN)  # the right one still works afterwards
    assert ok.status_code == 200 and ok.json()["state"] == "finished"


@pytest.mark.parametrize("missing", ["proposal_id", "kind"])
def test_approval_body_requires_proposal_id_and_kind(db_session, missing):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    body = {**HUMAN, "proposal_id": run["pending"]["proposal_id"], "kind": "proposal"}
    del body[missing]
    assert client.post(f"/runs/{run['run_id']}/approval", json=body).status_code == 422


def test_audit_and_event_record_proposal_id_and_hash(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    p = run["pending"]
    assert approve(client, run["run_id"], HUMAN).status_code == 200
    [row] = audits(db_session, "approval_decided")
    assert row["proposal_id"] == p["proposal_id"] and row["proposal_hash"] == p["proposal_hash"] and row["kind"] == "proposal"
    ev = next(m["data"] for m in sse_events(client, run["run_id"]) if m["event"] == "approval_decided")
    assert ev["payload"]["proposal_id"] == p["proposal_id"] and ev["payload"]["proposal_hash"] == p["proposal_hash"]


def test_rollback_approval_records_its_own_proposal_id(db_session):
    client, run = rollback_run(db_session)
    rid = run["run_id"]
    approve(client, rid, HUMAN)
    rb = client.get(f"/runs/{rid}").json()["pending"]
    assert rb["kind"] == "rollback" and rb["proposal_id"] != run["pending"]["proposal_id"]
    assert approve(client, rid, HUMAN, kind="proposal").status_code == 409  # right id, wrong kind
    assert approve(client, rid, HUMAN).status_code == 200
    rows = audits(db_session, "approval_decided")
    assert [r["kind"] for r in rows] == ["proposal", "rollback"] and rows[1]["proposal_id"] == rb["proposal_id"]


def test_fingerprint_changes_with_content_and_is_repeatable():
    a = {"change": "x", "sop_proposal": None}
    assert proposal_fingerprint(a) == proposal_fingerprint(dict(a))
    assert proposal_fingerprint(a)["proposal_hash"] != proposal_fingerprint({**a, "change": "y"})["proposal_hash"]
    assert proposal_fingerprint({"proposal_id": "p1"})["proposal_id"] == "p1"
    assert proposal_fingerprint({"sop_proposal": {"proposal_id": "s1"}})["proposal_id"] == "s1"


def test_pending_shows_the_sop_now_in_force_for_old_to_new(db_session):
    client, run = rollback_run(db_session)
    rid = run["run_id"]
    p = run["pending"]
    sop = p["proposal"]["sop_proposal"]
    assert p["current_sop"]["sop_id"] == sop["sop_id"] and p["current_sop"]["content"]
    assert p["current_sop"]["content"] != sop["new_content"]
    approve(client, rid, HUMAN)
    rb = client.get(f"/runs/{rid}").json()["pending"]
    assert rb["current_sop"]["content"] == sop["new_content"]  # the failed version is what a rollback replaces
    assert rb["current_sop"]["version"] > p["current_sop"]["version"]
