"""R10a/dev-04 (H-13): the event list of a run is append-only; an error event survives a retry,
event_ids stay unique and the SSE index keeps counting so Last-Event-ID resumes without loss."""

import importlib.util
import json
from pathlib import Path

from tests.test_act import HUMAN, approve, improve_answer, investigate_script
from tests.test_api import make_flaky_client, sse_events

ROOT = Path(__file__).resolve().parents[1]


def _failed_then_retried(db_session):
    inv = investigate_script()
    client = make_flaky_client(db_session, [inv[0], inv[0], inv[1], improve_answer()], fail_at=2)
    run = client.post("/runs", json={}).json()
    assert run["state"] == "error"
    return client, run["run_id"]


def test_event_ids_unique_and_error_event_kept_after_retry(db_session):
    client, rid = _failed_then_retried(db_session)
    before = sse_events(client, rid)
    assert before[-1]["data"]["payload"]["status"] == "error"
    assert client.post(f"/runs/{rid}/retry").status_code == 200
    msgs = sse_events(client, rid)
    ids = [m["data"]["event_id"] for m in msgs]
    assert len(set(ids)) == len(ids)
    errs = [m for m in msgs if m["event"] == "run_finished"]
    assert len(errs) == 1 and errs[0]["data"]["payload"]["status"] == "error"
    assert [m["id"] for m in msgs] == [str(i + 1) for i in range(len(msgs))]
    # the stream seen before is a prefix of the stream after
    assert [m["data"] for m in msgs[: len(before)]] == [m["data"] for m in before]


def test_resume_with_last_event_id_of_error_event_gets_next_real_event(db_session):
    client, rid = _failed_then_retried(db_session)
    before = sse_events(client, rid)
    err = before[-1]
    assert client.post(f"/runs/{rid}/retry").status_code == 200
    full = sse_events(client, rid)
    r = client.get(f"/runs/{rid}/events", headers={"Last-Event-ID": err["id"]})
    got = [json.loads(line.split(":", 1)[1]) for line in r.iter_lines() if line.startswith("data:")]
    assert got == [m["data"] for m in full[len(before) :]]
    assert got and got[0]["type"] != "run_finished"
    assert got[0]["event_id"] != err["data"]["event_id"]


def test_two_failures_then_finish_keeps_both_errors_and_unique_ids(db_session):
    client, rid = _failed_then_retried(db_session)
    assert client.post(f"/runs/{rid}/retry").status_code == 200
    done = approve(client, rid, HUMAN).json()
    assert done["state"] == "finished"
    msgs = sse_events(client, rid)
    ids = [m["data"]["event_id"] for m in msgs]
    assert len(set(ids)) == len(ids)
    outcomes = [m["data"]["payload"]["status"] for m in msgs if m["event"] == "run_finished"]
    assert outcomes == ["error", "completed"]
    runs = client.get("/runs").json()["runs"]
    assert runs[0]["outcome"] == "completed"


def test_waiting_run_after_retry_has_no_stale_outcome(db_session):
    client, rid = _failed_then_retried(db_session)
    client.post(f"/runs/{rid}/retry")
    row = next(r for r in client.get("/runs").json()["runs"] if r["run_id"] == rid)
    assert row["state"] == "waiting" and row["outcome"] is None


def test_error_retry_fixture_has_unique_event_ids_and_the_error_event():
    data = json.loads((ROOT / "docs/schema/examples/run-error-retry.json").read_text())
    ids = [e["event_id"] for e in data["events"]]
    assert len(set(ids)) == len(ids)
    statuses = [e["payload"]["status"] for e in data["events"] if e["type"] == "run_finished"]
    assert statuses == ["error", "completed"]


def test_regenerated_fixture_has_unique_event_ids(db_session, tmp_path):
    spec = importlib.util.spec_from_file_location("export_fixtures_r10a_dev04", ROOT / "scripts" / "export_fixtures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.export_all(tmp_path, db_session)
    data = json.loads((tmp_path / "run-error-retry.json").read_text())
    ids = [e["event_id"] for e in data["events"]]
    assert len(set(ids)) == len(ids)
    assert any(e["type"] == "run_finished" and e["payload"]["status"] == "error" for e in data["events"])
