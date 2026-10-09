"""R5/dev-03: FastAPI + SSE with TestClient, scripted LLM, seed 42 (no API key, no network)."""

import json

import pytest
from fastapi.testclient import TestClient

from backend.agent.llm import ScriptedLLM
from backend.api.app import create_app
from backend.domain_config import load_domain_config
from backend.tools.readonly import ToolContext
from tests.test_act import (
    CFG,
    CHANGE,
    HUMAN,
    SCHEMA,
    _fixed_tables,
    _tables,
    approve,
    improve_answer,
    investigate_script,
    valid_event,
    wrong_improve_answer,
)
from tests.test_ask import final


def make_client(db_session, scripts, tables=None):
    """`scripts`: one script per run, in start order."""
    queue = list(scripts)

    def llm_factory(run_id):
        return ScriptedLLM(queue.pop(0))

    def ctx_factory(run_id):
        return ToolContext(tables=tables or _fixed_tables(), session=db_session, run_id=run_id)

    return TestClient(create_app(CFG, llm_factory=llm_factory, ctx_factory=ctx_factory))


def sse_events(client, run_id, **params):
    out = []
    with client.stream("GET", f"/runs/{run_id}/events", params=params) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        cur = {}
        for line in r.iter_lines():
            if line.startswith("id:"):
                cur["id"] = line.split(":", 1)[1].strip()
            elif line.startswith("event:"):
                cur["event"] = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                cur["data"] = json.loads(line.split(":", 1)[1])
            elif line == "" and cur:
                out.append(cur)
                cur = {}
    return [m for m in out if "data" in m]


def start(client, change_time=CHANGE):
    r = client.post("/runs", json={"change_time": change_time})
    assert r.status_code == 201, r.text
    return r.json()


def test_start_then_sse_has_anomaly_detected_and_valid_schema(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    assert run["state"] == "waiting" and run["pending"]["type"] == "approval"
    assert run["pending"]["kind"] == "proposal" and run["pending"]["proposal"]["change"]
    msgs = sse_events(client, run["run_id"])
    types = [m["event"] for m in msgs]
    assert "anomaly_detected" in types and types[-1] == "proposal_created"
    for m in msgs:
        valid_event(m["data"])
        assert m["data"]["type"] == m["event"] and m["data"]["run_id"] == run["run_id"]
        assert set(m["data"]) == set(SCHEMA["required"])
    assert [m["id"] for m in msgs] == [str(i) for i in range(1, len(msgs) + 1)]


def test_sse_resume_from_last_event_id(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    allm = sse_events(client, run["run_id"])
    with client.stream("GET", f"/runs/{run['run_id']}/events", headers={"Last-Event-ID": "2"}) as r:
        ids = [ln.split(":", 1)[1].strip() for ln in r.iter_lines() if ln.startswith("id:")]
    assert ids == [m["id"] for m in allm[2:]]
    assert sse_events(client, run["run_id"], after=len(allm)) == []


def test_approval_moves_graph_to_completion(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    r = approve(client, run['run_id'], HUMAN)
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "finished" and body["status"] == "completed" and body["pending"] is None
    types = [m["event"] for m in sse_events(client, run["run_id"], follow=True)]
    assert types[-5:] == ["approval_decided", "sop_applied", "kpi_measured", "learning_saved", "run_finished"]
    for m in sse_events(client, run["run_id"]):
        valid_event(m["data"])
    assert client.get(f"/runs/{run['run_id']}").json()["state"] == "finished"


def test_rejection_goes_back_to_improve_and_waits_again(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer(), improve_answer()]])
    run = start(client)
    r = approve(client, run['run_id'], {"decision": "rejected", "decided_by": "alice", "reason": "risky"})
    assert r.status_code == 200 and r.json()["state"] == "waiting"
    types = [m["event"] for m in sse_events(client, run["run_id"])]
    assert types.count("proposal_created") == 2 and "sop_applied" not in types


def test_rollback_confirmation_goes_through_approval_endpoint(db_session):
    wrong = investigate_script("sensor calibration drift")  # a cause the simulator does not fix: KPI stays high
    script = [*wrong, wrong_improve_answer(), *wrong, wrong_improve_answer()]
    client = make_client(db_session, [script], tables=_tables())
    run = start(client)
    r = approve(client, run['run_id'], HUMAN).json()
    assert r["pending"]["type"] == "approval" and r["pending"]["kind"] == "rollback"
    r = approve(client, run['run_id'], {"decision": "approved", "decided_by": "bob"}).json()
    types = [m["event"] for m in sse_events(client, run["run_id"])]
    assert "rollback_done" in types and r["pending"]["kind"] == "proposal"


def test_answer_resumes_graph(db_session):
    low = final(0.1, gap=True)
    script = [low, *investigate_script(), improve_answer()]
    client = make_client(db_session, [script])
    run = start(client)
    assert run["state"] == "waiting" and run["pending"]["type"] == "answer" and run["pending"]["question"]
    types = [m["event"] for m in sse_events(client, run["run_id"])]
    assert types[-1] == "question_asked"
    r = client.post(f"/runs/{run['run_id']}/answer", json={"answer": "Setpoint was changed on M02"})
    assert r.status_code == 200 and r.json()["pending"]["type"] == "approval"
    types = [m["event"] for m in sse_events(client, run["run_id"])]
    assert "answer_received" in types and types[-1] == "proposal_created"


# ---- bad requests ----


def test_unknown_run_is_404(db_session):
    client = make_client(db_session, [])
    for method, path, body in [
        ("get", "/runs/nope", None),
        ("get", "/runs/nope/events", None),
        ("post", "/runs/nope/answer", {"answer": "x"}),
        ("post", "/runs/nope/approval", {**HUMAN, "proposal_id": "x", "kind": "proposal"}),
    ]:
        r = client.request(method, path, json=body)
        assert r.status_code == 404 and "nope" in r.json()["detail"]


def test_approval_when_not_waiting_for_it_is_409(db_session):
    client = make_client(db_session, [[final(0.1, gap=True)], [*investigate_script(), improve_answer()]])
    asking = start(client)
    r = approve(client, asking['run_id'], HUMAN)
    assert r.status_code == 409 and "approval" in r.json()["detail"]
    done = start(client)
    approve(client, done['run_id'], HUMAN)
    r = approve(client, done['run_id'], HUMAN)  # already finished: no second approval
    assert r.status_code == 409
    r = client.post(f"/runs/{done['run_id']}/answer", json={"answer": "x"})
    assert r.status_code == 409 and "answer" in r.json()["detail"]


def test_answer_when_waiting_for_approval_is_409(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    r = client.post(f"/runs/{run['run_id']}/answer", json={"answer": "x"})
    assert r.status_code == 409


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"decision": "maybe", "decided_by": "a"},
        {"decision": "approved"},
        {"decision": "approved", "decided_by": ""},
    ],
)
def test_invalid_approval_body_is_422_and_applies_nothing(db_session, bad):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    assert approve(client, run['run_id'], bad).status_code == 422
    assert client.get(f"/runs/{run['run_id']}").json()["state"] == "waiting"
    assert "sop_applied" not in [m["event"] for m in sse_events(client, run["run_id"])]


@pytest.mark.parametrize("who", ["agent", "llm", "bot", "claude", "system", "mallory"])
def test_approval_by_non_listed_name_is_422_with_message(db_session, who):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    r = approve(client, run['run_id'], {"decision": "approved", "decided_by": who})
    assert r.status_code == 422 and "not a valid approver" in r.json()["detail"]
    assert client.get(f"/runs/{run['run_id']}").json()["state"] == "waiting"
    assert "sop_applied" not in [m["event"] for m in sse_events(client, run["run_id"])]


def test_config_approvers_endpoint(db_session):
    client = make_client(db_session, [[final(0.1, gap=True)]])
    assert client.get("/config/approvers").json() == {"approvers": list(load_domain_config().approvers)}


def test_approval_by_agent_or_llm_is_rejected(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    r = approve(client, run['run_id'], {"decision": "approved", "decided_by": "agent"})
    assert r.status_code == 422
    assert client.get(f"/runs/{run['run_id']}").json()["state"] == "waiting"


def test_empty_answer_is_422(db_session):
    client = make_client(db_session, [[final(0.1, gap=True)]])
    run = start(client)
    assert client.post(f"/runs/{run['run_id']}/answer", json={"answer": ""}).status_code == 422


def test_start_with_empty_change_time_is_422(db_session):
    client = make_client(db_session, [])
    assert client.post("/runs", json={"change_time": ""}).status_code == 422


def test_start_without_change_time_runs_to_measure(db_session):
    """change_time is optional: it defaults to the end of the detected anomaly; repeated runs stay isolated."""
    client = make_client(
        db_session,
        [[*investigate_script(), improve_answer()], [*investigate_script(), improve_answer()]],
    )
    for _ in range(2):
        r = client.post("/runs", json={})
        assert r.status_code == 201, r.text
        run = r.json()
        assert run["pending"]["type"] == "approval"
        done = approve(client, run['run_id'], {"decision": "approved", "decided_by": "alice"})
        assert done.status_code == 200, done.text
        assert done.json()["state"] == "finished"
        types = [m["event"] for m in sse_events(client, run["run_id"])]
        assert "kpi_measured" in types and types[-1] == "run_finished"


def test_graph_valueerror_is_422(db_session):
    class Boom(ScriptedLLM):
        def complete(self, *a, **k):
            raise ValueError("change_time is required: boom")

    def llm_factory(run_id):
        return Boom([])

    def ctx_factory(run_id):
        return ToolContext(tables=_fixed_tables(), session=db_session, run_id=run_id)

    client = TestClient(create_app(CFG, llm_factory=llm_factory, ctx_factory=ctx_factory))
    r = client.post("/runs", json={"change_time": CHANGE})
    assert r.status_code == 422 and "change_time" in r.json()["detail"]


# ---- injection / isolation ----


def test_two_runs_are_isolated_and_repeatable(db_session):
    s = [*investigate_script(), improve_answer()]
    client = make_client(db_session, [s, s])
    a, b = start(client), start(client)
    assert a["run_id"] != b["run_id"]
    approve(client, a['run_id'], HUMAN)
    assert client.get(f"/runs/{b['run_id']}").json()["state"] == "waiting"
    ids_a = [m["data"]["event_id"] for m in sse_events(client, a["run_id"])]
    ids_b = [m["data"]["event_id"] for m in sse_events(client, b["run_id"])]
    assert all(a["run_id"] in i for i in ids_a) and all(b["run_id"] in i for i in ids_b)
    assert [i.rsplit("_", 1)[1] for i in ids_b] == [f"{n:04d}" for n in range(1, len(ids_b) + 1)]


def test_default_factories_do_not_need_a_key_until_a_run_starts(monkeypatch):
    monkeypatch.delenv("MODEL_REASONING", raising=False)
    app = create_app(load_domain_config())  # building the app touches neither LLM nor DB
    assert app.title


# ---- R8/dev-02: failures stop cleanly, retry continues ----


class FlakyLLM:
    """Scripted LLM that raises (e.g. a 429) on call number `fail_at`, once."""

    def __init__(self, script, fail_at):
        self.inner = ScriptedLLM(script)
        self.fail_at = fail_at
        self.n = 0

    def complete(self, system, messages, tools):
        self.n += 1
        if self.n == self.fail_at:
            raise RuntimeError("429 overloaded")
        return self.inner.complete(system, messages, tools)


def make_flaky_client(db_session, script, fail_at):
    def ctx_factory(run_id):
        return ToolContext(tables=_fixed_tables(), session=db_session, run_id=run_id)

    return TestClient(create_app(CFG, llm_factory=lambda rid: FlakyLLM(script, fail_at), ctx_factory=ctx_factory))


def _audit_actions(db_session, run_id):
    from sqlalchemy import select

    from backend.db.models import AuditLog

    return [r.action for r in db_session.scalars(select(AuditLog).where(AuditLog.run_id == run_id))]


def test_llm_error_midway_marks_run_failed_and_keeps_audit(db_session):
    client = make_flaky_client(db_session, [*investigate_script(), improve_answer()], fail_at=2)
    run = start(client)
    rid = run["run_id"]
    assert run["state"] == "error" and run["status"] == "error" and "429" in run["error"]
    got = client.get(f"/runs/{rid}").json()
    assert got["state"] == "error" and "429" in got["error"]
    msgs = sse_events(client, rid, follow=True)  # must terminate
    last = msgs[-1]
    assert last["event"] == "run_finished" and last["data"]["payload"]["status"] == "error"
    valid_event(last["data"])
    assert "correlate" in _audit_actions(db_session, rid)  # the step before the failure is still logged
    # nothing else can be done on a failed run except retry
    assert client.post(f"/runs/{rid}/answer", json={"answer": "x"}).status_code == 409


def test_retry_after_transient_error_continues(db_session):
    inv = investigate_script()
    # the failed Investigate step is replayed from its start, so the script has a second tool call
    client = make_flaky_client(db_session, [inv[0], inv[0], inv[1], improve_answer()], fail_at=2)
    rid = start(client)["run_id"]
    r = client.post(f"/runs/{rid}/retry")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "waiting" and body["pending"]["type"] == "approval" and "error" not in body
    types = [m["event"] for m in sse_events(client, rid)]
    assert types[-1] == "proposal_created" and "run_finished" not in types  # error event removed
    done = approve(client, rid, HUMAN).json()
    assert done["state"] == "finished" and done["status"] == "completed"


def test_retry_on_healthy_run_is_409_and_unknown_is_404(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    rid = start(client)["run_id"]
    assert client.post(f"/runs/{rid}/retry").status_code == 409
    assert client.post("/runs/nope/retry").status_code == 404


def test_error_during_approval_step_then_retry(db_session):
    # fail at the 3rd call (Improve after approval is not called; use the Improve call = 3rd)
    client = make_flaky_client(db_session, [*investigate_script(), improve_answer()], fail_at=3)
    run = start(client)
    assert run["state"] == "error"
    r = client.post(f"/runs/{run['run_id']}/retry").json()
    assert r["state"] == "waiting" and r["pending"]["type"] == "approval"
    assert client.post(f"/runs/{run['run_id']}/retry").status_code == 409  # repeat call: no stale error
