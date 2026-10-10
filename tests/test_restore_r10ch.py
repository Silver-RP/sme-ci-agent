"""R10ch/dev-03 (H-47, H-50, H-51): runs restored after a restart never get stuck."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from backend.api.app import create_app
from backend.domain_config import load_domain_config
from tests.test_engine_pool_r10c import ANSWER, own_db_url  # noqa: F401 - fixture
from tests.test_persist_r10c import APPROVER, _approve, _to_approval, env_db  # noqa: F401 - fixture

CFG = load_domain_config()
MAX = CFG.loop.max_retries


class Boom:
    def complete(self, *a, **k):
        raise RuntimeError("llm down")


def _sql(url, stmt, **params):
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text(stmt), params)
    eng.dispose()


def _failed_run(c):
    r = c.post("/runs", json={})
    assert r.status_code == 201 and r.json()["state"] == "error"
    return r.json()["run_id"]


def test_run_killed_between_steps_becomes_retryable_error_and_continues(env_db):  # noqa: F811
    with TestClient(create_app(CFG, llm_factory=lambda rid: Boom())) as a:
        stuck = _failed_run(a)
    # fake a SIGKILL inside the step: no error event, the row still says "running"
    _sql(env_db, "delete from events where run_id = :r and event_id like '%\\_err%'", r=stuck)
    _sql(env_db, "update runs set status = 'running' where run_id = :r", r=stuck)
    with TestClient(create_app(CFG)) as b:  # scripted LLM from SME_LLM
        waiting_id, pending_run = _to_approval(b)
        st = b.get(f"/runs/{stuck}").json()
        assert st["state"] == "error" and st["retryable"] is True and "Interrupted" in st["error"]
        r = b.post(f"/runs/{stuck}/retry")
        assert r.status_code == 200 and r.json()["state"] in ("waiting", "finished"), r.text
    with TestClient(create_app(CFG)) as c:  # restart again: the interrupted run is not marked twice
        assert c.get(f"/runs/{stuck}").json()["state"] == "waiting"
        assert c.get(f"/runs/{waiting_id}").json()["pending"] == pending_run["pending"]  # waiting run unchanged
        assert c.get(f"/runs/{waiting_id}").json()["state"] == "waiting"


def test_run_at_interrupt_is_not_marked_error(env_db):  # noqa: F811
    with TestClient(create_app(CFG)) as a:
        rid, before = _to_approval(a)
    _sql(env_db, "update runs set status = 'running' where run_id = :r", r=rid)  # stale status in the row
    with TestClient(create_app(CFG)) as b:
        got = b.get(f"/runs/{rid}").json()
        assert got["state"] == "waiting" and got["pending"] == before["pending"]
        assert _approve(b, rid, got["pending"]).json()["state"] == "finished"


def test_retry_limit_survives_restart_and_flag_matches(env_db):  # noqa: F811
    with TestClient(create_app(CFG, llm_factory=lambda rid: Boom())) as a:
        rid = _failed_run(a)
        for _ in range(MAX):
            assert a.post(f"/runs/{rid}/retry").status_code == 200
        assert a.get(f"/runs/{rid}").json()["retryable"] is False
        assert a.post(f"/runs/{rid}/retry").status_code == 409
    for _ in range(2):  # repeated restarts keep it the same
        with TestClient(create_app(CFG, llm_factory=lambda rid: Boom())) as b:
            assert b.get(f"/runs/{rid}").json()["retryable"] is False
            assert b.post(f"/runs/{rid}/retry").status_code == 409


def test_partly_used_retries_are_not_reset_by_restart(env_db):  # noqa: F811
    if MAX < 2:
        pytest.skip("needs max_retries >= 2")
    with TestClient(create_app(CFG, llm_factory=lambda rid: Boom())) as a:
        rid = _failed_run(a)
        assert a.post(f"/runs/{rid}/retry").status_code == 200
    with TestClient(create_app(CFG, llm_factory=lambda rid: Boom())) as b:
        assert b.get(f"/runs/{rid}").json()["retryable"] is True
        for _ in range(MAX - 1):  # one was used before the restart
            assert b.post(f"/runs/{rid}/retry").status_code == 200
        assert b.get(f"/runs/{rid}").json()["retryable"] is False
        assert b.post(f"/runs/{rid}/retry").status_code == 409


def test_closed_run_stays_closed_after_restart(env_db):  # noqa: F811
    with TestClient(create_app(CFG, llm_factory=lambda rid: Boom())) as a:
        rid = _failed_run(a)
        for _ in range(MAX):
            a.post(f"/runs/{rid}/retry")
        r = a.post(f"/runs/{rid}/close", json={"reason": "give up", "closed_by": APPROVER})
        assert r.status_code == 200, r.text
    with TestClient(create_app(CFG, llm_factory=lambda rid: Boom())) as b:
        st = b.get(f"/runs/{rid}").json()
        assert st["state"] == "finished" and st["status"] == "closed"
        assert b.post(f"/runs/{rid}/retry").status_code == 409
        assert b.post(f"/runs/{rid}/close", json={"reason": "again", "closed_by": APPROVER}).status_code == 409
        last = b.get(f"/runs/{rid}/events").text.strip().split("event:")[-1]
        assert last.split("\n")[0].strip() == "run_finished" and '"closed"' in last


def _boom_factory(rid):
    raise RuntimeError("no LLM configured")


def test_llm_factory_error_on_restore_hits_only_that_run(env_db):  # noqa: F811
    with TestClient(create_app(CFG)) as a:
        done, pend = _to_approval(a)
        assert _approve(a, done, pend["pending"]).json()["state"] == "finished"
        waiting, _ = _to_approval(a)
    with TestClient(create_app(CFG, llm_factory=_boom_factory)) as b:  # app still starts
        listed = {r["run_id"]: r for r in b.get("/runs").json()["runs"]}
        assert listed[waiting]["state"] == "error" and listed[done]["state"] == "finished"
        st = b.get(f"/runs/{waiting}").json()
        assert st["state"] == "error" and "no LLM configured" in st["error"]
        assert b.get(f"/runs/{done}/events").status_code == 200
        assert b.get(f"/runs/{done}/export").status_code == 200
        assert b.get(f"/runs/{waiting}/events").status_code == 200
        r = b.post(f"/runs/{waiting}/retry")  # still no LLM: fails again, no crash
        assert r.status_code == 200 and r.json()["state"] == "error"
    with TestClient(create_app(CFG)) as c:  # LLM back: the run can be retried
        assert c.get(f"/runs/{waiting}").json()["state"] == "error"
        r = c.post(f"/runs/{waiting}/retry")
        assert r.status_code == 200 and r.json()["state"] == "waiting", r.text
        assert r.json()["pending"]["type"] == "approval"


def test_stub_run_can_be_closed_once_retries_are_used(env_db):  # noqa: F811
    with TestClient(create_app(CFG)) as a:
        waiting, _ = _to_approval(a)
    with TestClient(create_app(CFG, llm_factory=_boom_factory)) as b:
        for _ in range(MAX):
            assert b.post(f"/runs/{waiting}/retry").status_code == 200
        assert b.post(f"/runs/{waiting}/retry").status_code == 409
        r = b.post(f"/runs/{waiting}/close", json={"reason": "no LLM", "closed_by": APPROVER})
        assert r.status_code == 200 and r.json()["status"] == "closed", r.text
