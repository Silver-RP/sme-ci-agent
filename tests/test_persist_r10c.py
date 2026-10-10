"""R10c/dev-02 (H-15): runs, events and checkpoints survive a backend restart (Postgres)."""

import logging
import os
import signal
import socket
import subprocess
import sys
import time
import warnings
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from langgraph.graph import END, START, StateGraph
from sqlalchemy import create_engine, text

from backend.agent.checkpoint import postgres_checkpointer
from backend.agent.state import AgentState, Hypothesis
from backend.api.app import create_app
from backend.db.session import get_shared_engine
from backend.domain_config import load_domain_config
from tests.test_engine_pool_r10c import ANSWER, own_db_url  # noqa: F401 - fixture

CFG = load_domain_config()
ROOT = Path(__file__).resolve().parent.parent
APPROVER = CFG.approvers[0]


def _approve(c, rid, pending, decision="approved"):
    return c.post(
        f"/runs/{rid}/approval",
        json={"proposal_id": pending["proposal_id"], "kind": pending["kind"], "decision": decision, "decided_by": APPROVER},
    )


def _to_approval(c):
    run = c.post("/runs", json={}).json()
    rid = run["run_id"]
    if run["pending"]["type"] == "answer":
        run = c.post(f"/runs/{rid}/answer", json=ANSWER).json()
    assert run["pending"]["type"] == "approval", run
    return rid, run


@pytest.fixture
def env_db(own_db_url, monkeypatch):  # noqa: F811
    monkeypatch.setenv("DATABASE_URL", own_db_url)
    monkeypatch.setenv("SME_LLM", "scripted")
    return own_db_url


def test_run_survives_new_app_and_continues(env_db):
    with TestClient(create_app(CFG)) as a:
        rid, before = _to_approval(a)
        n_events = len(a.get(f"/runs/{rid}/events").text.split("event:")) - 1
    with TestClient(create_app(CFG)) as b:  # a new app (a restart): nothing in memory
        got = b.get(f"/runs/{rid}")
        assert got.status_code == 200
        assert got.json()["pending"] == before["pending"] and got.json()["state"] == "waiting"
        assert [r["run_id"] for r in b.get("/runs").json()["runs"]] == [rid]
        assert len(b.get(f"/runs/{rid}/events").text.split("event:")) - 1 == n_events
        done = _approve(b, rid, before["pending"])
        assert done.status_code == 200, done.text
        assert done.json()["state"] == "finished"
        assert done.json()["pending"] is None
    with TestClient(create_app(CFG)) as c:  # finished run is still listed with its outcome
        row = c.get("/runs").json()["runs"][0]
        assert row["state"] == "finished" and row["finished_at"] is not None and row["outcome"] == "completed"
        types = [m for m in c.get(f"/runs/{rid}/events").text.split("event:")[1:]]
        assert types[-1].split("\n")[0].strip() == "run_finished"


def test_event_ids_stay_unique_in_db(env_db):
    with TestClient(create_app(CFG)) as a:
        rid, _ = _to_approval(a)
    with TestClient(create_app(CFG)) as b:
        pend = b.get(f"/runs/{rid}").json()["pending"]
        _approve(b, rid, pend)
    eng = create_engine(env_db)
    with eng.connect() as c:
        ids = [r[0] for r in c.execute(text("select event_id from events where run_id = :r"), {"r": rid})]
        status = c.execute(text("select status from runs where run_id = :r"), {"r": rid}).scalar_one()
    eng.dispose()
    assert len(ids) == len(set(ids)) > 3
    assert status == "finished"


def test_two_apps_see_same_list_and_unknown_run_is_404(env_db):
    with TestClient(create_app(CFG)) as a:
        rid, _ = _to_approval(a)
        with TestClient(create_app(CFG)) as b:  # started later, same DB, while A is alive
            assert rid in [r["run_id"] for r in b.get("/runs").json()["runs"]]
            assert b.get("/runs/run_nope0000").status_code == 404


def test_empty_db_lists_no_runs(env_db):
    with TestClient(create_app(CFG)) as a:
        assert a.get("/runs").json() == {"runs": []}


def test_hypothesis_state_roundtrips_through_postgres_saver(own_db_url, caplog):  # noqa: F811
    def node(state):
        return {"status": "x"}

    g = StateGraph(AgentState)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    hyp = Hypothesis(group="machine", description="spindle wear", confidence=0.6)
    cfg = {"configurable": {"thread_id": "t1"}}
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with caplog.at_level(logging.DEBUG), postgres_checkpointer(own_db_url) as saver:
            graph = g.compile(checkpointer=saver)
            graph.invoke({"hypotheses": [hyp]}, cfg)
        with postgres_checkpointer(own_db_url) as saver2:  # a new connection reads it back
            snap = g.compile(checkpointer=saver2).get_state(cfg)
    assert snap.values["hypotheses"] == [hyp]
    assert isinstance(snap.values["hypotheses"][0], Hypothesis)
    assert not [r for r in caplog.records if "unregistered" in r.getMessage().lower()]


def test_failed_and_pending_runs_do_not_leak_sessions(env_db):
    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("llm down")

    with TestClient(create_app(CFG, llm_factory=lambda rid: Boom())) as c:
        r = c.post("/runs", json={})
        assert r.status_code == 201 and r.json()["state"] == "error"
        assert get_shared_engine().pool.checkedout() == 0
        assert c.post(f"/runs/{r.json()['run_id']}/retry").status_code == 200  # fails again, still clean
        assert get_shared_engine().pool.checkedout() == 0
    with TestClient(create_app(CFG)) as c:
        _to_approval(c)  # run left pending
        assert get_shared_engine().pool.checkedout() == 0


# ---- tiêu chí 3: two real uvicorn processes ----


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn(url):
    port = _free_port()
    env = {**os.environ, "DATABASE_URL": url, "SME_LLM": "scripted"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "--factory", "backend.api.app:create_app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    while time.time() < deadline:
        assert proc.poll() is None, "uvicorn exited early"
        try:
            if httpx.get(f"{base}/config/approvers", timeout=2).status_code == 200:
                return proc, base
        except httpx.HTTPError:
            time.sleep(0.2)
    proc.kill()
    raise AssertionError("uvicorn did not start")


def _sse(base, rid):
    out = []
    with httpx.stream("GET", f"{base}/runs/{rid}/events", timeout=30) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if line.startswith("event:"):
                out.append(line.split(":", 1)[1].strip())
    return out


def test_two_uvicorn_processes_share_runs(own_db_url):  # noqa: F811
    p1, base1 = _spawn(own_db_url)
    try:
        c1 = httpx.Client(base_url=base1, timeout=30)
        run = c1.post("/runs", json={}).json()
        rid = run["run_id"]
        if run["pending"]["type"] == "answer":
            run = c1.post(f"/runs/{rid}/answer", json=ANSWER).json()
        pending = run["pending"]
        assert pending["type"] == "approval"
        events1 = _sse(base1, rid)
    finally:
        p1.send_signal(signal.SIGKILL)  # a crash, not a clean stop
        p1.wait(timeout=10)
    p2, base2 = _spawn(own_db_url)
    try:
        c2 = httpx.Client(base_url=base2, timeout=30)
        assert rid in [r["run_id"] for r in c2.get("/runs").json()["runs"]]
        assert _sse(base2, rid) == events1 and len(events1) >= 3
        r = _approve(c2, rid, pending)
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "finished"
        events2 = _sse(base2, rid)
        assert "learning_saved" in events2 and events2[-1] == "run_finished"
    finally:
        p2.terminate()
        p2.wait(timeout=15)
