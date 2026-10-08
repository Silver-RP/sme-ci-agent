"""R9/dev-06: the rollback chain over real HTTP (uvicorn, scripted LLM with several steps, read through SSE like the
dashboard) and scripts/export_fixtures.py (one fixture file per branch, produced through the API)."""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from backend.agent.demo_llm import demo_improve, demo_investigate
from backend.agent.llm import ScriptedLLM
from backend.api.app import create_app
from backend.domain_config import load_domain_config
from tests.test_act import valid_event
from tests.test_e2e import e2e_db_url, read_sse  # noqa: F401  (fixture re-used)

ROOT = Path(__file__).resolve().parents[1]
CFG = load_domain_config()
WRONG = "other_parameter_c"  # a parameter the simulator does not link to the anomaly


def chain_script():
    """Wrong cause + wrong fix -> Measure fails -> (rollback) -> investigate again -> right fix."""
    return [*demo_investigate(CFG, "sensor calibration drift"), demo_improve(CFG, WRONG), *demo_investigate(CFG), demo_improve(CFG)]


@pytest.fixture
def chain_server(e2e_db_url, monkeypatch):  # noqa: F811
    monkeypatch.setenv("DATABASE_URL", e2e_db_url)
    scripts = []

    def llm_factory(run_id):
        s = ScriptedLLM(chain_script())
        scripts.append(s)
        return s

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(create_app(CFG, llm_factory=llm_factory), log_level="warning"))
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


def decide(c, rid, body):
    pending = c.get(f"/runs/{rid}").json()["pending"]
    return c.post(f"/runs/{rid}/approval", json={"proposal_id": pending["proposal_id"], "kind": pending["kind"], **body})


def test_wrong_fix_then_rollback_then_right_fix_completes_over_uvicorn(chain_server):
    c = httpx.Client(base_url=chain_server, timeout=60)
    run = c.post("/runs", json={}).json()
    rid = run["run_id"]
    assert run["pending"]["kind"] == "proposal"
    assert run["pending"]["proposal"]["action"]["parameter"] == WRONG

    # approve the wrong fix: Measure fails and the agent proposes a rollback (a person must confirm it)
    run = decide(c, rid, {"decision": "approved", "decided_by": "alice"}).json()
    assert run["state"] == "waiting" and run["pending"]["kind"] == "rollback"
    assert "rollback_done" not in [e["type"] for e in read_sse(chain_server, rid)]  # nothing rolled back yet

    # confirm: rollback_done, Investigate again, a new (right) proposal
    run = decide(c, rid, {"decision": "approved", "decided_by": "bob"}).json()
    assert run["pending"]["kind"] == "proposal" and run["pending"]["proposal"]["action"]["parameter"] != WRONG

    run = decide(c, rid, {"decision": "approved", "decided_by": "alice"}).json()
    assert run["state"] == "finished" and run["status"] == "completed"

    events = read_sse(chain_server, rid, follow="true")
    for e in events:
        valid_event(e)
    kinds = [e["type"] for e in events]
    measured = [e["payload"] for e in events if e["type"] == "kpi_measured"]
    assert [m["passed"] for m in measured] == [False, True]
    seq = ["proposal_created", "sop_applied", "kpi_measured", "proposal_created", "approval_decided", "rollback_done",
           "hypothesis_updated", "proposal_created", "approval_decided", "sop_applied", "kpi_measured", "learning_saved",
           "run_finished"]
    it = iter(kinds)
    assert all(step in it for step in seq), kinds  # in this order (other events may sit between)
    rb = next(e["payload"] for e in events if e["type"] == "rollback_done")
    assert rb["rolled_back"] is True and rb["approved_by"] == "bob"
    assert events[-1]["payload"]["status"] == "completed"
    assert len({e["event_id"] for e in events}) == len(events)


# ---- scripts/export_fixtures.py ----

BRANCHES = {
    "happy": ("finished", "completed"),
    "rollback": ("finished", "completed"),
    "rollback-declined": ("waiting", "halt:rollback_declined"),
    "insufficient-evidence": ("waiting", "answer"),
    "revise": ("finished", "completed"),
    "halt-max-questions": ("waiting", "halt:max_questions_reached"),
    "error-retry": ("finished", "completed"),
    "no-anomaly": ("finished", "no_anomaly"),
}


def load_script():
    spec = importlib.util.spec_from_file_location("export_fixtures_under_test", ROOT / "scripts" / "export_fixtures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_fixture(name, data):
    state, expect = BRANCHES[name]
    last = data["steps"][-1]["response"]
    assert last["state"] == state, (name, last)
    events = data["events"]
    for e in events:
        valid_event(e)
    if state == "finished":
        assert events[-1]["type"] == "run_finished" and events[-1]["payload"]["status"] == expect
    else:
        assert last["pending"] is not None
        if expect.startswith("halt:"):
            assert last["pending"]["kind"] == "halt" and last["pending"]["reason"] == expect[5:]
        else:
            assert last["pending"]["type"] == expect


def test_export_all_writes_one_valid_file_per_branch(db_session, tmp_path):
    mod = load_script()
    for _ in range(2):  # repeatable: no state leaks between calls
        written = mod.export_all(tmp_path, db_session)
        assert sorted(p.name for p in written) == sorted(f"run-{b}.json" for b in BRANCHES)
    assert sorted(p.name for p in tmp_path.glob("run-*.json")) == sorted(f"run-{b}.json" for b in BRANCHES)
    for name in BRANCHES:
        check_fixture(name, json.loads((tmp_path / f"run-{name}.json").read_text()))


def test_error_retry_fixture_shows_the_retryable_error_then_recovery(db_session, tmp_path):
    mod = load_script()
    mod.export_all(tmp_path, db_session)
    data = json.loads((tmp_path / "run-error-retry.json").read_text())
    first = data["steps"][0]
    assert first["response"]["state"] == "error" and first["response"]["retryable"] is True
    assert first["last_event"]["type"] == "run_finished" and first["last_event"]["payload"]["status"] == "error"
    assert first["last_event"]["payload"]["retryable"] is True


def test_rollback_fixture_has_rollback_events(db_session, tmp_path):
    mod = load_script()
    mod.export_all(tmp_path, db_session)
    data = json.loads((tmp_path / "run-rollback.json").read_text())
    kinds = [e["type"] for e in data["events"]]
    assert "rollback_done" in kinds and "learning_saved" in kinds
    assert [e["payload"]["passed"] for e in data["events"] if e["type"] == "kpi_measured"] == [False, True]


def test_export_fixtures_command_exits_zero(e2e_db_url, tmp_path):  # noqa: F811
    env = {**os.environ, "DATABASE_URL": e2e_db_url}
    env.pop("SME_LLM", None)
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_fixtures.py"), "--out", str(tmp_path)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=300, check=False,
    )
    assert p.returncode == 0, p.stderr[-2000:]
    assert len(list(tmp_path.glob("run-*.json"))) == len(BRANCHES)


def test_committed_examples_cover_every_branch():
    for name in BRANCHES:
        path = ROOT / "docs" / "schema" / "examples" / f"run-{name}.json"
        assert path.exists(), path
        check_fixture(name, json.loads(path.read_text()))
