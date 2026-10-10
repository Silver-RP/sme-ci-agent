"""R10c/dev-06 (H-38): every decision leaves exactly one audit_log row (run_id, actor, action): the answers of a
person, the halts (raised and decided, with reason and options) and a Measure that gives no verdict."""

import json

from sqlalchemy import select

from backend.agent.llm import ScriptedLLM
from backend.agent.nodes.act import make_measure_node
from backend.agent.state import new_state
from backend.db.models import AuditLog
from tests.test_act import (
    CFG,
    HUMAN,
    _tables,
    approve,
    improve_answer,
    investigate_script,
    make_ctx,
    wrong_improve_answer,
)
from tests.test_api import make_client, start
from tests.test_api_limits_r9 import LATE, REJECT, client_with, with_loop
from tests.test_ask import final
from tests.test_engine_pool_r10c import own_db_url  # noqa: F401 - fixture used by env_db
from tests.test_persist_r10c import _approve, _to_approval, env_db  # noqa: F401 - fixture


def rows(db_session, action, run_id=None):
    q = select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)
    if run_id:
        q = q.where(AuditLog.run_id == run_id)
    return list(db_session.scalars(q))


def test_answer_to_ask_is_one_audit_row(db_session):
    client = make_client(db_session, [[final(0.1, gap=True), *investigate_script(), improve_answer()]])
    run = start(client)
    rid, qid = run["run_id"], run["pending"]["question_id"]
    assert rows(db_session, "answer_received") == []
    assert client.post(f"/runs/{rid}/answer", json={"answer": "Setpoint was changed on M02"}).status_code == 200
    [row] = rows(db_session, "answer_received", rid)
    assert row.actor == "human" and row.run_id == rid
    assert row.params["answer"] == "Setpoint was changed on M02" and row.params["question_id"] == qid
    assert row.params["attempt"] == 1


def test_refused_answer_writes_no_row(db_session):
    client = make_client(db_session, [[final(0.1, gap=True), *investigate_script(), improve_answer()]])
    rid = start(client)["run_id"]
    client.post(f"/runs/{rid}/answer", json={"answer": "x", "question_id": "stale"})  # 409
    client.post(f"/runs/{rid}/answer", json={"answer": ""})  # 422
    assert rows(db_session, "answer_received") == []


def test_measure_insufficient_evidence_and_its_answer_one_row_each(db_session):
    client = client_with(db_session, ScriptedLLM([*investigate_script(), improve_answer()]), tables=_tables())
    rid = start(client, change_time=LATE)["run_id"]
    got = approve(client, rid, HUMAN).json()
    assert got["pending"]["type"] == "answer"
    [m] = rows(db_session, "kpi_not_measured", rid)
    assert m.actor == "system" and m.params["status"] == "insufficient_evidence" and m.params["kpi"]
    assert rows(db_session, "answer_received", rid) == []
    client.post(f"/runs/{rid}/answer", json={"answer": "wait for more data"})
    [a] = rows(db_session, "answer_received", rid)
    assert a.actor == "human" and a.params["answer"] == "wait for more data"
    assert len(rows(db_session, "kpi_not_measured", rid)) == 2  # the second Measure is a second decision
    assert len(rows(db_session, "approval_decided", rid)) == 1


def test_measure_not_applied_is_one_row_and_repeated_call_adds_one_more(db_session):
    ctx = make_ctx(db_session, _tables())
    node = make_measure_node(CFG, ctx)
    s = new_state("run_m", "manufacturing")
    s["anomaly"] = {"machine": "M02", "kpi": "defect_rate"}
    s["applied"] = None
    out = node(s)["measurement"]
    assert out["status"] == "not_applied"
    [row] = rows(db_session, "kpi_not_measured", "run_act")
    assert row.actor == "system" and row.params["status"] == "not_applied" and row.params["reason"]
    node(s)
    assert len(rows(db_session, "kpi_not_measured")) == 2  # one per call, nothing leaks between calls


def test_measure_with_verdict_still_one_threshold_row_and_no_not_measured(db_session):
    client = client_with(db_session, ScriptedLLM([*investigate_script(), improve_answer()]), tables=_tables())
    rid = start(client)["run_id"]
    approve(client, rid, HUMAN)
    assert len(rows(db_session, "kpi_threshold_check", rid)) == 1
    assert rows(db_session, "kpi_not_measured", rid) == []


def test_halt_has_one_row_when_raised_and_one_when_decided(db_session):
    cfg = with_loop(max_rejections=1)
    client = client_with(db_session, ScriptedLLM([*investigate_script(), improve_answer()]), cfg)
    rid = start(client)["run_id"]
    halt = approve(client, rid, REJECT).json()["pending"]
    assert halt["kind"] == "halt"
    [raised] = rows(db_session, "halt_raised", rid)
    assert raised.actor == "system" and raised.params["reason"] == halt["reason"]
    assert raised.params["options"] == halt["options"]
    assert rows(db_session, "halt_decided", rid) == []
    approve(client, rid, {"decision": "finish", "decided_by": "alice", "reason": "stop"})
    [decided] = rows(db_session, "halt_decided", rid)
    assert decided.actor == "alice" and decided.params["decision"] == "finish"
    assert decided.params["options"] == halt["options"] and decided.params["halt_reason"] == halt["reason"]
    assert len(rows(db_session, "halt_raised", rid)) == 1


def test_ask_limit_halt_is_raised_once(db_session):
    script = [final(0.1, gap=True)] * 3
    client = make_client(db_session, [script])
    run = start(client)
    rid = run["run_id"]
    for _ in range(5):
        pend = client.get(f"/runs/{rid}").json()["pending"]
        if pend["type"] != "answer":
            break
        client.post(f"/runs/{rid}/answer", json={"answer": "no idea"})
    assert client.get(f"/runs/{rid}").json()["pending"]["kind"] == "halt"
    [raised] = rows(db_session, "halt_raised", rid)
    assert raised.params["reason"] == "max_questions_reached" and raised.params["options"]
    assert len(rows(db_session, "answer_received", rid)) >= 1


def test_restoring_a_run_after_restart_adds_no_audit_row(env_db):  # noqa: F811
    """A restart rebuilds the run from the checkpointer; it must not write the decisions again."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text

    from backend.api.app import create_app

    def counts():
        eng = create_engine(env_db)
        with eng.connect() as c:
            out = list(c.execute(text("select action, count(*) from audit_log group by action order by action")))
        eng.dispose()
        return out

    with TestClient(create_app(CFG)) as a:
        rid, before = _to_approval(a)
        n_answers = dict(counts()).get("answer_received", 0)
    after_first = counts()
    with TestClient(create_app(CFG)) as b:  # a restart: lifespan restores the unfinished run
        assert b.get(f"/runs/{rid}").json()["pending"] == before["pending"]
        assert counts() == after_first
        b.get(f"/runs/{rid}")
    assert counts() == after_first
    assert n_answers <= 1  # the scripted run asks at most once; the answer is one row

    with TestClient(create_app(CFG)) as c:
        done = _approve(c, rid, before["pending"])
        assert done.status_code == 200, done.text
    final_counts = dict(counts())
    assert final_counts["approval_decided"] == 1


def test_wrong_proposal_run_json_safe(db_session):
    """Audit params are plain JSON (they go to a JSON column)."""
    client = client_with(db_session, ScriptedLLM([*investigate_script(), wrong_improve_answer()]), tables=_tables())
    rid = start(client)["run_id"]
    approve(client, rid, HUMAN)
    for r in db_session.scalars(select(AuditLog).where(AuditLog.run_id == rid)):
        json.dumps(r.params)
