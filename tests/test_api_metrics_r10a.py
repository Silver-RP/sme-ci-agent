"""R10a/dev-03 + R10b2/dev-06: GET /metrics, honest numbers only (scripted LLM, no network).

Since R10b2 the numbers come from the report of scripts/metrics_report.py for the current dataset and seed."""

import json
import re
from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.db.models import AuditLog, LearningEntry
from tests.test_act import CFG, HUMAN, approve, improve_answer, investigate_script
from tests.test_api import make_client, start

PAYLOADS = Path(__file__).resolve().parents[1] / "docs" / "schema" / "payloads.md"
METRIC_KEYS = {"name", "unit", "before", "after", "available", "reason", "run_id"}


@pytest.fixture(autouse=True)
def reports_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SME_REPORTS_DIR", str(tmp_path))
    monkeypatch.delenv("SME_DATASET", raising=False)


def documented_example(marker: str) -> dict:
    text = PAYLOADS.read_text(encoding="utf-8")
    m = re.search(re.escape(marker) + r".*?```json\n(.*?)```", text, re.DOTALL)
    assert m, f"payloads.md has no example after {marker!r}"
    return json.loads(m.group(1))


def make_report(dataset="sandbox", seed=42):
    agent = {"defect_rate_before": 0.031, "period_rate": 0.0204, "mttd_hours": 8.0, "mttr_hours": 24.0,
             "recurrence_rate": 0.25}
    manual = {"defect_rate_before": 0.031, "period_rate": 0.0208, "mttd_hours": 72.0, "mttr_hours": 44.0,
              "recurrence_rate": 0.5}
    return {"dataset": dataset, "seed": seed, "months": 6, "llm": "scripted",
            "generated_at": "2026-10-11T10:00:00+00:00",
            "assumptions": [{"name": "approval_delay_hours", "value": 4.0, "unit": "hours", "source": "assumption"}],
            "agent": agent, "manual": manual}


def write_report(directory, rep, name=None):
    name = name or f"metrics_{rep['dataset']}_seed{rep['seed']}.json"
    (directory / name).write_text(json.dumps(rep), encoding="utf-8")


def test_no_report_means_nothing_available(db_session):
    client = make_client(db_session, [])
    body = client.get("/metrics").json()
    assert len(body["metrics"]) == 3
    for m in body["metrics"]:
        assert set(m) == METRIC_KEYS
        assert m["available"] is False and "metrics_report" in m["reason"]
        assert m["before"] is None and m["after"] is None and m["run_id"] is None
    assert (body["dataset"], body["seed"]) == ("sandbox", 42)
    assert body["generated_at"] is None and body["assumptions"] == []
    assert client.get("/metrics").json() == body  # repeated call


def test_report_numbers_are_served(db_session, tmp_path):
    rep = make_report()
    write_report(tmp_path, rep)
    client = make_client(db_session, [])
    body = client.get("/metrics").json()
    assert (body["dataset"], body["seed"], body["generated_at"]) == ("sandbox", 42, rep["generated_at"])
    assert body["assumptions"] == rep["assumptions"]
    kpi, mttd_mttr, rec = body["metrics"]
    assert [m["name"] for m in body["metrics"]] == [CFG.kpis[0].name, "mttd_mttr", "recurrence_rate"]
    for m in body["metrics"]:
        assert set(m) == METRIC_KEYS and m["available"] is True and m["reason"] is None
    a, c = rep["agent"], rep["manual"]
    assert kpi["unit"] == CFG.kpis[0].unit
    # "before" = without the agent (control arm), "after" = with the agent, as the dashboard labels them
    assert (kpi["before"], kpi["after"]) == (c["period_rate"], a["period_rate"])
    assert mttd_mttr["unit"] == "hours"
    assert (mttd_mttr["before"], mttd_mttr["after"]) == (c["mttd_hours"] + c["mttr_hours"], a["mttd_hours"] + a["mttr_hours"])
    assert (rec["before"], rec["after"]) == (c["recurrence_rate"], a["recurrence_rate"])
    assert client.get("/metrics").json() == body  # repeated call


def test_report_of_another_dataset_or_seed_is_not_served(db_session, tmp_path):
    client = make_client(db_session, [])
    write_report(tmp_path, make_report(dataset="other"))
    write_report(tmp_path, make_report(seed=7))
    # file named for this dataset/seed but holding another one: still not served
    write_report(tmp_path, make_report(dataset="other"), name="metrics_sandbox_seed42.json")
    body = client.get("/metrics").json()
    assert (body["dataset"], body["seed"]) == ("sandbox", 42)
    assert len(body["metrics"]) == 3
    for m in body["metrics"]:
        assert m["available"] is False and "metrics_report" in m["reason"]
        assert m["before"] is None and m["after"] is None
    assert body["generated_at"] is None and body["assumptions"] == []


def test_unreadable_or_incomplete_report_is_unavailable(db_session, tmp_path):
    client = make_client(db_session, [])
    (tmp_path / "metrics_sandbox_seed42.json").write_text("{not json", encoding="utf-8")
    assert all(m["available"] is False for m in client.get("/metrics").json()["metrics"])
    rep = make_report()
    rep["agent"]["mttr_hours"] = None  # one number missing: that metric alone is unavailable
    write_report(tmp_path, rep)
    kpi, mttd_mttr, rec = client.get("/metrics").json()["metrics"]
    assert kpi["available"] is True and rec["available"] is True
    assert mttd_mttr["available"] is False and mttd_mttr["before"] is None and mttd_mttr["reason"]


def test_report_follows_the_active_dataset(db_session, tmp_path, monkeypatch):
    write_report(tmp_path, make_report(dataset="sandbox"))
    client = make_client(db_session, [])
    assert client.get("/metrics").json()["metrics"][0]["available"] is True
    monkeypatch.setenv("SME_DATASET", "plant_a")
    body = client.get("/metrics").json()
    assert body["dataset"] == "plant_a" and body["metrics"][0]["available"] is False


def test_metrics_keys_match_payloads_md_example(db_session, tmp_path):
    example = documented_example("Ví dụ phản hồi `GET /metrics`")
    for state in ("empty", "reported"):
        client = make_client(db_session, [])
        if state == "reported":
            write_report(tmp_path, make_report())
        body = client.get("/metrics").json()
        assert set(body) == set(example)
        for m in body["metrics"]:
            assert set(m) == set(example["metrics"][0]) == METRIC_KEYS
        assert [m["name"] for m in body["metrics"]] == [m["name"] for m in example["metrics"]]


def test_metrics_does_not_write_the_db(db_session, tmp_path):
    write_report(tmp_path, make_report())
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
