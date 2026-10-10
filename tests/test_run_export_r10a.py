"""R10a/dev-06 (T-041): GET /runs/{id}/export and scripts/record_run.py write a run in the fixture format."""

import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.agent.llm import ScriptedLLM
from backend.api.app import create_app
from backend.tools.readonly import ToolContext
from tests.test_act import (
    CFG,
    HUMAN,
    SCHEMA,
    _fixed_tables,
    approve,
    improve_answer,
    investigate_script,
    valid_event,
)
from tests.test_api import make_client, start

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((ROOT / "docs" / "schema" / "examples").glob("run-*.json"))
FILE_KEYS = {"note", "branch", "description", "steps", "events"}
STEP_KEYS = {"request", "http", "response", "last_event"}


def check_fixture_format(data):
    """The same rules for the 8 committed fixtures and for a recorded file."""
    assert set(data) == FILE_KEYS
    assert data["note"] and data["branch"] and data["description"]
    assert data["steps"] and data["events"]
    for s in data["steps"]:
        assert STEP_KEYS <= set(s) <= STEP_KEYS | {"body"}
        assert s["http"] in (200, 201)
        assert s["request"].split(" ")[0] in ("POST", "GET")
    for e in data["events"]:
        valid_event(e)
    ids = [e["event_id"] for e in data["events"]]
    assert len(set(ids)) == len(ids)
    assert data["steps"][-1]["last_event"] == data["events"][-1]
    assert data["steps"][-1]["response"]["run_id"] == data["events"][0]["run_id"]


def load_record_script():
    spec = importlib.util.spec_from_file_location("record_run_under_test", ROOT / "scripts" / "record_run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def script():
    return [*investigate_script(), improve_answer()]


def finished_run(client):
    run = start(client)
    assert approve(client, run["run_id"], HUMAN).json()["state"] == "finished"
    return run["run_id"]


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_committed_fixtures_pass_the_format_check(path):
    assert len(EXAMPLES) == 8
    check_fixture_format(json.loads(path.read_text()))


def test_export_of_finished_run_has_all_events_in_order_and_valid(db_session):
    client = make_client(db_session, [script()])
    rid = finished_run(client)
    r = client.get(f"/runs/{rid}/export")
    assert r.status_code == 200
    data = r.json()
    check_fixture_format(data)
    assert data["note"] == "Bản ghi từ run thật, LLM giả"
    sse = []
    with client.stream("GET", f"/runs/{rid}/events") as s:
        for line in s.iter_lines():
            if line.startswith("data:"):
                sse.append(json.loads(line.split(":", 1)[1]))
    assert data["events"] == sse and data["events"][-1]["type"] == "run_finished"
    assert [s["request"] for s in data["steps"]] == ["POST /runs", "POST /runs/{run_id}/approval"]
    assert data["steps"][0]["response"]["state"] == "waiting"
    assert data["steps"][-1]["response"]["state"] == "finished"
    for e in data["events"]:
        assert e["type"] in SCHEMA["properties"]["type"]["enum"]
    assert client.get(f"/runs/{rid}/export").json() == data  # repeated call: same answer


def test_export_unknown_run_is_404(db_session):
    assert make_client(db_session, []).get("/runs/run_nope/export").status_code == 404


def test_export_does_not_mix_runs(db_session):
    client = make_client(db_session, [script(), script()])
    a = finished_run(client)
    b = finished_run(client)
    da, db = client.get(f"/runs/{a}/export").json(), client.get(f"/runs/{b}/export").json()
    assert {e["run_id"] for e in da["events"]} == {a} and {e["run_id"] for e in db["events"]} == {b}
    assert len(da["steps"]) == 2 and len(db["steps"]) == 2


def test_failed_requests_are_not_recorded(db_session):
    client = make_client(db_session, [script()])
    run = start(client)
    bad = client.post(f"/runs/{run['run_id']}/approval", json={"proposal_id": "nope", "kind": "proposal", **HUMAN})
    assert bad.status_code == 409
    assert len(client.get(f"/runs/{run['run_id']}/export").json()["steps"]) == 1


def test_export_has_no_traceback_raw_exception_sim_or_env(db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-secret-123")

    class Boom(ScriptedLLM):
        def complete(self, *a, **k):
            raise RuntimeError("Traceback (most recent call last): secret path /srv/x.py sim=1 sk-ant-test-secret-123")

    # a run whose first LLM call fails -> run_finished(status=error) with the raw message inside the app
    failing = TestClient(
        create_app(
            CFG,
            llm_factory=lambda rid: Boom([]),
            ctx_factory=lambda rid: ToolContext(tables=_fixed_tables(), session=db_session, run_id=rid),
        )
    )
    r = failing.post("/runs", json={"change_time": "2026-03-19T00:00:00"})
    rid = r.json()["run_id"]
    assert r.json()["state"] == "error"
    text = json.dumps(failing.get(f"/runs/{rid}/export").json(), ensure_ascii=False)
    for bad in ("Traceback", "/srv/x.py", "sk-ant", "secret", "sim=1", '"sim"'):
        assert bad not in text, bad
    assert "RuntimeError" in text  # the class name may stay
    check_fixture_format(json.loads(text))


def test_normal_export_has_no_sim_key(db_session):
    client = make_client(db_session, [script()])
    rid = finished_run(client)
    text = json.dumps(client.get(f"/runs/{rid}/export").json())
    assert '"sim"' not in text and "Traceback" not in text


def test_record_run_writes_the_file_the_api_returns(db_session, tmp_path):
    mod = load_record_script()
    client = make_client(db_session, [script()])
    rid = finished_run(client)
    out = tmp_path / "recorded-test.json"
    for _ in range(2):  # repeated call overwrites the same file
        assert mod.record(client, rid, out) == out
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == client.get(f"/runs/{rid}/export").json()
    check_fixture_format(data)


def test_record_run_default_path_is_recorded_name_in_examples():
    mod = load_record_script()
    p = mod.default_out("run_abc")
    assert p.parent == ROOT / "docs" / "schema" / "examples" and p.name == "recorded-run_abc.json"


def test_record_run_unknown_run_fails_without_writing(db_session, tmp_path):
    mod = load_record_script()
    out = tmp_path / "x.json"
    client = make_client(db_session, [])
    with pytest.raises(SystemExit):
        mod.record(client, "run_nope", out)
    assert not out.exists()
