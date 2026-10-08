"""R7/dev-04: end-to-end over real HTTP (uvicorn on a random port, scripted LLM chosen by env var)
and the run_scenario.py command line. No API key, no network beyond localhost."""

import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import httpx
import pytest
import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.agent.demo_llm import llm_from_env, scripted_demo_llm
from backend.api.app import create_app
from backend.domain_config import load_domain_config
from tests.test_act import SCHEMA, approve, valid_event

ROOT = Path(__file__).resolve().parents[1]
CFG = load_domain_config()


@pytest.fixture
def e2e_db_url(shared_db_url):
    """Own throwaway database: the server and the script COMMIT, so they must not touch the shared test DB."""
    base = make_url(shared_db_url)
    name = f"{base.database}_e2e_{uuid.uuid4().hex[:6]}"
    admin = create_engine(base.set(database=base.database), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend/db/migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    yield url
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def server(e2e_db_url, monkeypatch):
    monkeypatch.setenv("SME_LLM", "scripted")
    monkeypatch.setenv("DATABASE_URL", e2e_db_url)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))  # random free port, handed to uvicorn
    port = sock.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(create_app(), log_level="warning"))
    t = threading.Thread(target=srv.run, kwargs={"sockets": [sock]}, daemon=True)
    t.start()
    deadline = time.time() + 15
    while not srv.started:
        assert time.time() < deadline and t.is_alive(), "server did not start"
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.should_exit = True
        t.join(timeout=10)
        sock.close()
        assert not t.is_alive(), "server thread did not stop"


def read_sse(base, run_id, **params):
    out = []
    with httpx.stream("GET", f"{base}/runs/{run_id}/events", params=params, timeout=30) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if line.startswith("data:"):
                out.append(json.loads(line.split(":", 1)[1]))
    return out


def test_full_loop_over_http_with_real_detect(server):
    c = httpx.Client(base_url=server, timeout=30)
    approvers = c.get("/config/approvers").json()["approvers"]
    assert approvers == CFG.approvers

    r = c.post("/runs", json={})  # no change_time, no anomaly: Detect finds it in the seed-42 data
    assert r.status_code == 201, r.text
    run = r.json()
    rid = run["run_id"]
    assert run["state"] == "waiting" and run["pending"]["type"] == "answer"
    ev = read_sse(server, rid)
    assert "anomaly_detected" in [e["type"] for e in ev]
    det = next(e for e in ev if e["type"] == "anomaly_detected")
    assert det["payload"]  # produced from data, not a canned value

    run = c.post(f"/runs/{rid}/answer", json={"answer": "Setpoint was changed on M02"}).json()
    assert run["pending"]["type"] == "approval"

    # a name outside the allow-list is refused over HTTP
    bad = approve(c, rid, {"decision": "approved", "decided_by": "mallory"})
    assert bad.status_code == 422

    run = approve(c, rid, {"decision": "approved", "decided_by": approvers[0]}).json()
    # the demo fix targets the modelled cause (setpoint): the simulator brings the KPI back, Measure passes
    assert run["state"] == "finished"

    events = read_sse(server, rid, follow="true")
    assert events[-1]["type"] == "run_finished"
    for e in events:
        valid_event(e)
        assert e["run_id"] == rid
    assert len({e["event_id"] for e in events}) == len(events)


def test_two_runs_over_http_do_not_leak(server):
    c = httpx.Client(base_url=server, timeout=30)
    ids = [c.post("/runs", json={}).json()["run_id"] for _ in range(2)]
    assert ids[0] != ids[1]
    a, b = (read_sse(server, i) for i in ids)
    assert [e["type"] for e in a] == [e["type"] for e in b]


def test_scripted_llm_only_when_env_set(monkeypatch):
    monkeypatch.delenv("SME_LLM", raising=False)
    assert llm_from_env(CFG) is None
    monkeypatch.setenv("SME_LLM", "scripted")
    a, b = llm_from_env(CFG), llm_from_env(CFG)
    assert a is not b  # a fresh script per call: no cursor shared between runs
    assert scripted_demo_llm(CFG, ask_first=False) is not None


def test_run_scenario_script_exits_zero(e2e_db_url):
    env = {**os.environ, "DATABASE_URL": e2e_db_url}
    env.pop("SME_LLM", None)
    for _ in range(2):  # repeatable
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_scenario.py")],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=300, check=False,
        )
        assert p.returncode == 0, p.stderr[-2000:]
        assert "anomaly_detected" in p.stdout and "run_finished" in p.stdout
    assert set(SCHEMA["required"])  # schema loaded


def test_dashboard_yarnrc_removed():
    assert not (ROOT / "dashboard" / ".yarnrc").exists()
