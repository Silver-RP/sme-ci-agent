"""R10ch/dev-02 (H-48): change_time is checked when the run starts (422, no LLM call);
a run in a non-retryable error can be closed by a person."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.api.app import create_app
from backend.db.models import AuditLog, SopVersion
from backend.domain_config import load_domain_config
from backend.tools.readonly import ToolContext
from tests.test_act import (
    CFG,
    CHANGE,
    HUMAN,
    _fixed_tables,
    approve,
    improve_answer,
    investigate_script,
)
from tests.test_api import sse_events
from tests.test_api_limits_r9 import FailAt, client_with, with_loop


class CountingLLM:
    def __init__(self):
        self.calls = 0

    def complete(self, *a, **k):
        self.calls += 1
        raise AssertionError("LLM must not be called")

    def __getattr__(self, name):
        def f(*a, **k):
            self.calls += 1
            raise AssertionError("LLM must not be called")

        return f


def _client(db_session, llm):
    def ctx_factory(run_id):
        return ToolContext(tables=_fixed_tables(), session=db_session, run_id=run_id)

    return TestClient(create_app(CFG, llm_factory=lambda rid: llm, ctx_factory=ctx_factory))


def _anomaly_start():
    from backend.detect.statistical import detect

    return detect(_fixed_tables(), CFG)[0]["payload"]["start"]


@pytest.mark.parametrize(
    "bad",
    ["2026-03-20T00:00:00Z", "2099-01-01", "abc", "2026-03-20T00:00:00+09:00", "2000-01-01"],
)
def test_bad_change_time_is_422_at_start_without_llm(db_session, bad):
    llm = CountingLLM()
    client = _client(db_session, llm)
    r = client.post("/runs", json={"change_time": bad})
    assert r.status_code == 422, r.text
    assert llm.calls == 0
    assert client.get("/runs").json()["runs"] == []


def test_just_before_anomaly_start_is_422_and_repeat_is_clean(db_session):
    import pandas as pd

    before = (pd.Timestamp(_anomaly_start()) - pd.Timedelta(days=1)).isoformat()
    llm = CountingLLM()
    client = _client(db_session, llm)
    for _ in range(2):  # no state leaks between calls
        assert client.post("/runs", json={"change_time": before}).status_code == 422
    assert llm.calls == 0


def test_valid_change_time_and_default_still_start(db_session):
    from tests.test_api import make_client

    client = make_client(db_session, [investigate_script(), investigate_script()])
    assert client.post("/runs", json={"change_time": CHANGE}).status_code == 201
    assert client.post("/runs", json={}).status_code == 201


def _dead_run(db_session):
    cfg = with_loop(max_retries=1)
    client = client_with(db_session, FailAt([], fail_at=1, always=True), cfg)
    rid = client.post("/runs", json={"change_time": CHANGE}).json()["run_id"]
    assert client.post(f"/runs/{rid}/retry").status_code == 200
    assert client.post(f"/runs/{rid}/retry").status_code == 409
    assert client.get(f"/runs/{rid}").json()["retryable"] is False
    return client, rid


def _closes(db_session, rid):
    return [r for r in db_session.scalars(select(AuditLog).where(AuditLog.run_id == rid)) if r.action == "run_closed"]


def test_close_dead_run_emits_run_finished_closed_and_one_audit_row(db_session):
    client, rid = _dead_run(db_session)
    versions_before = len(list(db_session.scalars(select(SopVersion))))
    r = client.post(f"/runs/{rid}/close", json={"reason": "LLM outage, give up", "closed_by": "alice"})
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "finished" and r.json()["status"] == "closed"
    last = sse_events(client, rid, follow=True)[-1]["data"]
    assert last["type"] == "run_finished" and last["payload"]["status"] == "closed"
    assert last["payload"]["closed_by"] == "alice" and last["payload"]["reason"] == "closed_by_human"
    rows = _closes(db_session, rid)
    assert len(rows) == 1 and rows[0].actor == "alice"
    assert len(list(db_session.scalars(select(SopVersion)))) == versions_before
    # closing twice, or retrying a closed run, is refused and adds no audit row
    assert client.post(f"/runs/{rid}/close", json={"reason": "again", "closed_by": "alice"}).status_code == 409
    assert client.post(f"/runs/{rid}/retry").status_code == 409
    assert len(_closes(db_session, rid)) == 1


def test_close_needs_reason_and_a_listed_person(db_session):
    client, rid = _dead_run(db_session)
    assert client.post(f"/runs/{rid}/close", json={"closed_by": "alice"}).status_code == 422
    assert client.post(f"/runs/{rid}/close", json={"reason": "", "closed_by": "alice"}).status_code == 422
    assert client.post(f"/runs/{rid}/close", json={"reason": "x", "closed_by": "mallory"}).status_code == 422
    assert client.post(f"/runs/{rid}/close", json={"reason": "x", "closed_by": "claude"}).status_code == 422
    assert _closes(db_session, rid) == []
    assert client.get(f"/runs/{rid}").json()["state"] == "error"


def test_close_retryable_error_is_409(db_session):
    client = client_with(db_session, FailAt([], fail_at=1, always=True), with_loop(max_retries=3))
    rid = client.post("/runs", json={"change_time": CHANGE}).json()["run_id"]
    body = {"reason": "x", "closed_by": "alice"}
    assert client.post(f"/runs/{rid}/close", json=body).status_code == 409


def test_close_waiting_run_is_409_and_changes_nothing(db_session):
    from tests.test_api import make_client

    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    rid = client.post("/runs", json={"change_time": CHANGE}).json()["run_id"]
    body = {"reason": "skip approval", "closed_by": "alice"}
    st = client.get(f"/runs/{rid}").json()
    assert st["state"] == "waiting"
    assert client.post(f"/runs/{rid}/close", json=body).status_code == 409
    assert client.get(f"/runs/{rid}").json()["state"] == "waiting"
    assert _closes(db_session, rid) == []
    assert client.post("/runs/run_nope/close", json=body).status_code == 404


def test_close_run_waiting_for_rollback_is_409(db_session):
    from tests.test_act import _tables, wrong_improve_answer
    from tests.test_api import make_client

    wrong = investigate_script("sensor calibration drift")
    client = make_client(db_session, [[*wrong, wrong_improve_answer(), *wrong]], tables=_tables())
    rid = client.post("/runs", json={"change_time": CHANGE}).json()["run_id"]
    st = approve(client, rid, HUMAN).json()
    assert st["pending"]["kind"] == "rollback"
    body = {"reason": "dodge rollback", "closed_by": "alice"}
    assert client.post(f"/runs/{rid}/close", json=body).status_code == 409
    assert client.get(f"/runs/{rid}").json()["pending"]["kind"] == "rollback"


def test_default_config_has_approvers():
    assert load_domain_config().approvers
