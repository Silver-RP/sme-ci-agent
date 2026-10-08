"""R9/dev-04: API keeps decisions (H-07), turns post-resume failures into retryable errors (H-08),
treats wait_evidence as an answer (H-09), and bounds revise / rollbacks / retries (H-17)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.agent.llm import ScriptedLLM
from backend.api.app import create_app
from backend.db.models import AuditLog
from backend.domain_config import DomainConfig, LoopParams, load_domain_config
from backend.tools.readonly import ToolContext
from tests.test_act import (
    CFG,
    CHANGE,
    HUMAN,
    _fixed_tables,
    _tables,
    approve,
    improve_answer,
    investigate_script,
    wrong_improve_answer,
)
from tests.test_api import sse_events, start

REVISE = {"decision": "revise", "decided_by": "alice", "reason": "check the material batch first"}
REJECT = {"decision": "rejected", "decided_by": "alice", "reason": "too risky"}


class FailAt:
    """Scripted LLM that raises ``exc`` on call number ``fail_at`` (``always``: on that call and every later one)."""

    def __init__(self, script, fail_at, exc=None, always=False):
        self.inner = ScriptedLLM(script)
        self.fail_at, self.exc, self.always, self.n = fail_at, exc or RuntimeError("429 overloaded"), always, 0

    def complete(self, system, messages, tools):
        self.n += 1
        if self.n == self.fail_at or (self.always and self.n > self.fail_at):
            raise self.exc
        return self.inner.complete(system, messages, tools)


def client_with(db_session, llm, cfg: DomainConfig = CFG, tables=None):
    def ctx_factory(run_id):
        return ToolContext(tables=tables or _fixed_tables(), session=db_session, run_id=run_id)

    return TestClient(create_app(cfg, llm_factory=lambda rid: llm, ctx_factory=ctx_factory))


def with_loop(**kw) -> DomainConfig:
    return CFG.model_copy(update={"loop": LoopParams(**kw)})


def audit_rows(db_session, action):
    return [a.params for a in db_session.scalars(select(AuditLog).where(AuditLog.action == action))]


# ---- H-07: the decision survives a failure in the next step ----


@pytest.mark.parametrize("body,kind", [(REVISE, "revise"), (REJECT, "rejected")])
def test_decision_is_kept_when_the_next_step_fails(db_session, body, kind):
    # call 4 = Investigate after revise / Improve after rejection
    llm = FailAt([*investigate_script(), improve_answer()], fail_at=4)
    client = client_with(db_session, llm)
    rid = start(client)["run_id"]
    r = approve(client, rid, body)
    assert r.status_code == 200 and r.json()["state"] == "error"
    rows = audit_rows(db_session, "approval_decided")
    assert [x["decision"] for x in rows] == [kind]


def test_decision_is_not_written_twice_after_retry(db_session):
    llm = FailAt([*investigate_script(), improve_answer(), *investigate_script(), improve_answer()], fail_at=4)
    client = client_with(db_session, llm)
    rid = start(client)["run_id"]
    approve(client, rid, REVISE)
    assert client.post(f"/runs/{rid}/retry").status_code == 200
    assert len(audit_rows(db_session, "approval_decided")) == 1


# ---- H-08: failures after resume are run errors, not 422 ----


def test_value_error_after_resume_is_a_retryable_error_not_422(db_session):
    llm = FailAt([*investigate_script(), improve_answer()], fail_at=4, exc=ValueError("boom after resume"))
    client = client_with(db_session, llm)
    rid = start(client)["run_id"]
    r = approve(client, rid, REJECT)
    assert r.status_code == 200 and r.json()["state"] == "error" and "boom" in r.json()["error"]
    assert client.get(f"/runs/{rid}").json()["state"] == "error"
    assert client.post(f"/runs/{rid}/retry").status_code == 200


def test_improve_returns_broken_json_after_rejection_is_error_and_retryable(db_session):
    script = [*investigate_script(), improve_answer(), "not json", "still not json", improve_answer()]
    client = client_with(db_session, ScriptedLLM(script))
    rid = start(client)["run_id"]
    r = approve(client, rid, REJECT)
    assert r.status_code == 200 and r.json()["state"] == "error"
    assert client.get(f"/runs/{rid}").json()["state"] == "error"
    assert client.post(f"/runs/{rid}/retry").status_code == 200


def test_bad_approver_is_still_422(db_session):
    client = client_with(db_session, ScriptedLLM([*investigate_script(), improve_answer()]))
    rid = start(client)["run_id"]
    assert approve(client, rid, {"decision": "approved", "decided_by": "mallory"}).status_code == 422
    assert client.get(f"/runs/{rid}").json()["state"] == "waiting"


# ---- H-09: wait_evidence is an answer ----

LATE = "2026-06-29T22:00:00"  # too few KPI points after the change


def test_missing_samples_after_the_change_is_a_pending_answer_and_answer_continues(db_session):
    client = client_with(db_session, ScriptedLLM([*investigate_script(), improve_answer()]), tables=_tables())
    rid = start(client, change_time=LATE)["run_id"]
    got = approve(client, rid, HUMAN).json()
    assert got["state"] == "waiting" and got["pending"]["type"] == "answer" and "not enough" in got["pending"]["question"].lower()
    r = client.post(f"/runs/{rid}/answer", json={"answer": "wait for more data"})
    assert r.status_code == 200, r.text


# ---- H-17: limits ----


def test_revise_over_the_limit_halts(db_session):
    cfg = with_loop(max_revisions=1)
    script = [*investigate_script(), improve_answer(), *investigate_script(), improve_answer(), *investigate_script()]
    client = client_with(db_session, ScriptedLLM(script), cfg)
    rid = start(client)["run_id"]
    first = approve(client, rid, REVISE).json()
    assert first["pending"]["kind"] == "proposal"  # revision 1 of 1 is allowed
    second = approve(client, rid, REVISE).json()
    assert second["pending"]["kind"] == "halt" and second["pending"]["reason"] == "max_revisions_reached"


def test_retry_over_the_limit_is_409_and_not_retryable(db_session):
    cfg = with_loop(max_retries=2)
    llm = FailAt([], fail_at=1, always=True)
    client = client_with(db_session, llm, cfg)
    r = client.post("/runs", json={"change_time": CHANGE})
    assert r.status_code == 201 and r.json()["state"] == "error"
    rid = r.json()["run_id"]
    assert client.post(f"/runs/{rid}/retry").status_code == 200  # 1
    assert client.post(f"/runs/{rid}/retry").status_code == 200  # 2
    assert client.post(f"/runs/{rid}/retry").status_code == 409  # 3
    last = sse_events(client, rid)[-1]["data"]["payload"]
    assert last["status"] == "error" and last["retryable"] is False
    assert client.get(f"/runs/{rid}").json()["retryable"] is False


def test_retry_counter_is_per_run(db_session):
    cfg = with_loop(max_retries=1)
    a = client_with(db_session, FailAt([], fail_at=1, always=True), cfg)
    ra = a.post("/runs", json={"change_time": CHANGE}).json()["run_id"]
    assert a.post(f"/runs/{ra}/retry").status_code == 200
    assert a.post(f"/runs/{ra}/retry").status_code == 409
    b = client_with(db_session, FailAt([], fail_at=1, always=True), cfg)
    rb = b.post("/runs", json={"change_time": CHANGE}).json()["run_id"]
    assert b.post(f"/runs/{rb}/retry").status_code == 200


def test_total_rollbacks_are_bounded_across_halts(db_session):
    cfg = with_loop(max_rollbacks=1, max_total_rollbacks=2)
    wrong = investigate_script("sensor calibration drift")
    cycle = [*wrong, wrong_improve_answer()]
    client = client_with(db_session, ScriptedLLM([*cycle, *cycle, *cycle]), cfg, tables=_tables())
    rid = start(client)["run_id"]
    approve(client, rid, HUMAN)  # proposal -> Measure fails -> rollback prompt
    halt = approve(client, rid, HUMAN).json()  # rollback 1 -> per-run limit 1 -> halt
    assert halt["pending"]["kind"] == "halt" and halt["pending"]["options"] == ["investigate", "finish"]
    assert approve(client, rid, {"decision": "investigate", "decided_by": "alice"}).status_code == 200
    approve(client, rid, HUMAN)  # proposal -> rollback prompt again
    halt2 = approve(client, rid, HUMAN).json()  # rollback 2 -> total limit
    assert halt2["pending"]["kind"] == "halt" and halt2["pending"]["options"] == ["finish"]
    assert approve(client, rid, {"decision": "investigate", "decided_by": "alice"}).status_code == 422
    done = approve(client, rid, {"decision": "finish", "decided_by": "alice"}).json()
    assert done["state"] == "finished"


def test_loop_defaults_come_from_yaml():
    cfg = load_domain_config()
    assert cfg.loop.max_revisions >= 1 and cfg.loop.max_retries >= 1
    assert cfg.loop.max_total_rollbacks >= cfg.loop.max_rollbacks
