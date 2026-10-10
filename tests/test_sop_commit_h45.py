"""R10ch/dev-01 (H-45, H-31): the SOP version written by Act and by a rollback is committed (with its audit row)
before the run goes on, so a later failure (Measure, the next LLM call) does not erase it. All reads use a
second session on the real database."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.agent.demo_llm import DemoLLM
from backend.agent.nodes import act as act_mod
from backend.api.app import create_app
from backend.db.models import AuditLog, SopVersion
from backend.db.session import get_shared_engine
from backend.domain_config import load_domain_config
from tests.test_engine_pool_r10c import (  # noqa: F401 - fixture: a private migrated DB
    ANSWER,
    own_db_url,
)

CFG = load_domain_config()


def other_session_versions():
    with Session(get_shared_engine()) as s:
        return [(r.sop_id, r.version, r.content) for r in s.scalars(select(SopVersion).order_by(SopVersion.id))]


def other_session_audit(action):
    with Session(get_shared_engine()) as s:
        return list(s.scalars(select(AuditLog.id).where(AuditLog.action == action)))


class SwitchLLM:
    """DemoLLM that raises (a transient 429) on every call while ``broken`` is set."""

    def __init__(self, inner):
        self.inner, self.broken = inner, False

    def complete(self, system, messages, tools):
        if self.broken:
            raise RuntimeError("429 overloaded")
        return self.inner.complete(system, messages, tools)


@pytest.fixture
def make_client(own_db_url, monkeypatch):  # noqa: F811
    monkeypatch.setenv("DATABASE_URL", own_db_url)
    monkeypatch.delenv("SME_LLM", raising=False)
    made = []

    def build(rollback):
        def factory(run_id):
            llm = SwitchLLM(DemoLLM(CFG, rollback=rollback))
            made.append(llm)
            return llm

        return TestClient(create_app(CFG, llm_factory=factory))

    build.made = made
    return build


def decide(c, rid, decision, by="alice"):
    p = c.get(f"/runs/{rid}").json()["pending"]
    r = c.post(f"/runs/{rid}/approval", json={"proposal_id": p["proposal_id"], "kind": p["kind"], "decision": decision, "decided_by": by, "reason": "r"})
    assert r.status_code == 200, r.text
    return r.json()


def start(c):
    run = c.post("/runs", json={}).json()
    if run["pending"] and run["pending"]["type"] == "answer":
        run = c.post(f"/runs/{run['run_id']}/answer", json=ANSWER).json()
    assert run["pending"]["kind"] == "proposal", run
    return run["run_id"]


def test_sop_version_survives_a_measure_failure_and_retry(make_client, monkeypatch):
    real = act_mod.build_post_change_tables
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk gone")
        return real(*a, **k)

    monkeypatch.setattr(act_mod, "build_post_change_tables", boom)
    with make_client(rollback=False) as c:
        rid = start(c)
        run = decide(c, rid, "approved")
        assert run["state"] == "error"
        versions = other_session_versions()
        written = [v for v in versions if v[1] > 1]
        assert len(written) == 1, versions
        assert other_session_audit("apply_sop")
        assert c.post(f"/runs/{rid}/retry").status_code == 200
        run = c.get(f"/runs/{rid}").json()
        assert run["state"] == "finished", run
        after = other_session_versions()
        assert after == versions  # the retry did not write the SOP a second time
        events = c.get(f"/runs/{rid}/export").json()["events"]
        lesson = next(e for e in events if e["type"] == "learning_saved")["payload"]["content"]
        assert (lesson["sop_id"], lesson["sop_version"]) in {(s, v) for s, v, _ in after}


def test_rolled_back_sop_survives_a_failing_llm_call(make_client):
    with make_client(rollback=True) as c:
        rid = start(c)
        run = decide(c, rid, "approved")
        assert run["pending"]["kind"] == "rollback", run
        before = other_session_versions()
        original = next(v for v in before if v[1] == min(x[1] for x in before))[2]
        bad = before[-1][2]
        assert bad != original
        for llm in make_client.made:
            llm.broken = True  # the first LLM call after the rollback fails
        run = decide(c, rid, "approved")
        assert run["state"] == "error", run
        after = other_session_versions()
        assert len(after) == len(before) + 1
        assert after[-1][2] == original  # the SOP in force is the restored one
        assert other_session_audit("apply_sop")

