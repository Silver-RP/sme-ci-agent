"""R10d/dev-03 (#115): GET /learnings is read only, per domain, newest first."""

import pytest
from sqlalchemy import text

from tests.test_act import HUMAN, approve, improve_answer, investigate_script
from tests.test_api import make_client, start


def full_run(client):
    run = start(client)
    assert approve(client, run["run_id"], HUMAN).json()["state"] == "finished"
    return run["run_id"]


def saved_content(client, rid):
    events = client.get(f"/runs/{rid}/export").json()["events"]
    return next(e for e in events if e["type"] == "learning_saved")["payload"]["content"]


def two_runs(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]] * 2)
    r1, r2 = full_run(client), full_run(client)
    return client, r1, r2


def test_two_runs_newest_first_and_content_matches(db_session):
    client, r1, r2 = two_runs(db_session)
    r = client.get("/learnings")
    assert r.status_code == 200
    rows = [x for x in r.json()["learnings"] if x["run_id"] in (r1, r2)]
    assert [x["run_id"] for x in rows] == [r2, r1]
    for x in rows:
        assert set(x) == {"learning_id", "run_id", "created_at", "content"}
        assert x["content"] == saved_content(client, x["run_id"])
    assert len(client.get("/learnings", params={"limit": 1}).json()["learnings"]) == 1
    assert client.get("/learnings", params={"limit": 1}).json()["learnings"][0]["run_id"] == r2


@pytest.mark.parametrize("bad", [0, 501, -1])
def test_limit_out_of_range_is_422(db_session, bad):
    client = make_client(db_session, [])
    assert client.get("/learnings", params={"limit": bad}).status_code == 422
    assert client.get("/learnings", params={"limit": 500}).status_code == 200


def counts(db_session):
    return {
        t: db_session.execute(text(f"select count(*) from {t}")).scalar()
        for t in ("learning_store", "audit_log", "sop_versions", "runs", "events")
    }


def test_other_domain_hidden_and_read_does_not_write(db_session):
    client = two_runs(db_session)[0]
    db_session.execute(
        text("insert into learning_store (run_id, domain, content) values ('other_run', 'other_domain', cast('{\"x\": 1}' as jsonb))")
    )
    db_session.commit()
    before = counts(db_session)
    for _ in range(2):
        rows = client.get("/learnings", params={"limit": 500}).json()["learnings"]
        assert "other_run" not in {x["run_id"] for x in rows}
    assert counts(db_session) == before


def test_lessons_survive_app_restart(db_session):
    client, r1, r2 = two_runs(db_session)
    content = saved_content(client, r2)
    fresh = make_client(db_session, [])
    assert fresh.get(f"/runs/{r2}").status_code == 404
    rows = fresh.get("/learnings").json()["learnings"]
    assert {r1, r2} <= {x["run_id"] for x in rows}
    assert next(x for x in rows if x["run_id"] == r2)["content"] == content


def test_no_database_url_returns_empty(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.api.app import create_app
    from backend.domain_config import load_domain_config

    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(create_app(load_domain_config())) as c:
        r = c.get("/learnings")
    assert r.status_code == 200 and r.json() == {"learnings": []}
