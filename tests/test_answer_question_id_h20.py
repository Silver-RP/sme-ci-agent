"""R10c/dev-05 (H-20): a pending question carries question_id + attempt; POST /answer may send question_id
and a stale one is 409 without answering the current question. Without question_id: old behaviour."""

from backend.agent.llm import ScriptedLLM
from tests.test_act import HUMAN, _tables, approve, improve_answer, investigate_script
from tests.test_api import sse_events, start
from tests.test_api_limits_r9 import LATE, client_with


def _waiting_run(db_session):
    client = client_with(db_session, ScriptedLLM([*investigate_script(), improve_answer()]), tables=_tables())
    rid = start(client, change_time=LATE)["run_id"]
    got = approve(client, rid, HUMAN).json()
    assert got["pending"]["type"] == "answer"
    return client, rid, got["pending"]


def test_pending_question_has_id_and_attempt(db_session):
    _, _, pending = _waiting_run(db_session)
    assert isinstance(pending["question_id"], str) and pending["question_id"]
    assert pending["attempt"] == 1


def test_stale_question_id_is_409_and_current_question_stays_open(db_session):
    client, rid, first = _waiting_run(db_session)
    r = client.post(f"/runs/{rid}/answer", json={"answer": "wait", "question_id": first["question_id"]})
    assert r.status_code == 200, r.text
    second = r.json()["pending"]
    assert second["type"] == "answer" and second["attempt"] == 2
    assert second["question_id"] != first["question_id"]
    n_answers = sum(1 for e in sse_events(client, rid) if e["event"] == "answer_received")
    stale = client.post(f"/runs/{rid}/answer", json={"answer": "late click", "question_id": first["question_id"]})
    assert stale.status_code == 409
    after = client.get(f"/runs/{rid}").json()
    assert after["pending"]["question_id"] == second["question_id"]
    n_after = sum(1 for e in sse_events(client, rid) if e["event"] == "answer_received")
    assert n_after == n_answers
    ok = client.post(f"/runs/{rid}/answer", json={"answer": "wait", "question_id": second["question_id"]})
    assert ok.status_code == 200


def test_without_question_id_old_behaviour(db_session):
    client, rid, _ = _waiting_run(db_session)
    assert client.post(f"/runs/{rid}/answer", json={"answer": "wait"}).status_code == 200
    again = client.post(f"/runs/{rid}/answer", json={"answer": "wait"})  # repeated call, no id, still accepted
    assert again.status_code == 200  # a run still waiting on evidence accepts it
