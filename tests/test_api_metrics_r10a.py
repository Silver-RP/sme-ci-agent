"""R10a/dev-03: GET /metrics, honest numbers only (scripted LLM, seed 42, no network)."""

import json
import re
from pathlib import Path

from sqlalchemy import func, select

from backend.db.models import AuditLog, LearningEntry
from tests.test_act import CFG, HUMAN, approve, improve_answer, investigate_script
from tests.test_api import make_client, sse_events, start

PAYLOADS = Path(__file__).resolve().parents[1] / "docs" / "schema" / "payloads.md"
METRIC_KEYS = {"name", "unit", "before", "after", "available", "reason", "run_id"}


def documented_example(marker: str) -> dict:
    text = PAYLOADS.read_text(encoding="utf-8")
    m = re.search(re.escape(marker) + r".*?```json\n(.*?)```", text, re.DOTALL)
    assert m, f"payloads.md has no example after {marker!r}"
    return json.loads(m.group(1))


def test_no_finished_learning_means_nothing_available(db_session):
    client = make_client(db_session, [])
    body = client.get("/metrics").json()
    assert len(body["metrics"]) == 3
    for m in body["metrics"]:
        assert set(m) == METRIC_KEYS
        assert m["available"] is False and m["reason"]
        assert m["before"] is None and m["after"] is None and m["run_id"] is None
    assert client.get("/metrics").json() == body  # repeated call


def test_kpi_metric_equals_learning_saved_of_the_run(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run_id = start(client)["run_id"]
    assert approve(client, run_id, HUMAN).json()["state"] == "finished"
    saved = next(e for e in sse_events(client, run_id) if e["event"] == "learning_saved")["data"]["payload"]["content"]
    body = client.get("/metrics").json()
    kpi, *others = body["metrics"]
    assert [m["name"] for m in others] == ["mttd_mttr", "recurrence_rate"]
    assert kpi["name"] == saved["kpi"] == CFG.kpis[0].name
    assert kpi["unit"] == CFG.kpis[0].unit
    assert kpi["available"] is True and kpi["reason"] is None and kpi["run_id"] == run_id
    assert kpi["before"] == saved["kpi_before"] and kpi["after"] == saved["kpi_after"]
    for m in others:  # no real source until R10b2: never a made-up number
        assert m["available"] is False and "R10b2" in m["reason"] and m["before"] is None and m["after"] is None
    assert client.get("/metrics").json() == body


def test_metrics_keys_match_payloads_md_example(db_session):
    example = documented_example("Ví dụ phản hồi `GET /metrics`")
    for state in ("empty", "learned"):
        client = make_client(db_session, [[*investigate_script(), improve_answer()]])
        if state == "learned":
            run_id = start(client)["run_id"]
            approve(client, run_id, HUMAN)
        body = client.get("/metrics").json()
        assert set(body) == set(example)
        for m in body["metrics"]:
            assert set(m) == set(example["metrics"][0]) == METRIC_KEYS
        assert [m["name"] for m in body["metrics"]] == [m["name"] for m in example["metrics"]]


def test_metrics_does_not_write_the_db(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run_id = start(client)["run_id"]
    approve(client, run_id, HUMAN)

    def counts():
        return (
            db_session.scalar(select(func.count()).select_from(AuditLog)),
            db_session.scalar(select(func.count()).select_from(LearningEntry)),
        )

    before = counts()
    client.get("/metrics")
    client.get("/metrics")
    assert counts() == before
    for method in (client.post, client.put, client.delete):
        assert method("/metrics").status_code in (404, 405)
