"""R10e/dev-06 (H-65 a, c, d): GET /metrics shows the report's llm and limits, refuses a report of another
length, and never answers 500 on NaN/inf."""

import json

import pytest

from tests.test_api import make_client
from tests.test_api_metrics_r10a import make_report, write_report


@pytest.fixture(autouse=True)
def reports_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SME_REPORTS_DIR", str(tmp_path))
    monkeypatch.delenv("SME_DATASET", raising=False)


LIMITS = ["synthetic data only", "manual arm uses assumed delays"]


def test_llm_and_limits_come_from_report(db_session, tmp_path):
    rep = make_report()
    rep["limits"] = LIMITS
    write_report(tmp_path, rep)
    client = make_client(db_session, [])
    body = client.get("/metrics").json()
    assert body["llm"] == "scripted" and body["limits"] == LIMITS
    assert client.get("/metrics").json() == body  # repeated call


def test_llm_and_limits_empty_without_report(db_session):
    body = make_client(db_session, []).get("/metrics").json()
    assert body["llm"] is None and body["limits"] == []


def test_report_with_other_months_is_not_served_as_six(db_session, tmp_path):
    rep = make_report()
    rep["months"] = 1
    rep["limits"] = LIMITS
    write_report(tmp_path, rep)
    body = make_client(db_session, []).get("/metrics").json()
    assert len(body["metrics"]) == 3
    for m in body["metrics"]:
        assert m["available"] is False and m["before"] is None and m["after"] is None
        assert "months" in m["reason"] and "1" in m["reason"]
    assert body["llm"] is None and body["limits"] == [] and body["generated_at"] is None


def test_report_without_months_is_not_served(db_session, tmp_path):
    rep = make_report()
    del rep["months"]
    write_report(tmp_path, rep)
    body = make_client(db_session, []).get("/metrics").json()
    assert all(m["available"] is False for m in body["metrics"])


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_number_is_unavailable_not_500(db_session, tmp_path, bad):
    rep = make_report()
    rep["limits"] = LIMITS
    text = json.dumps(rep).replace('"mttr_hours": 24.0', f'"mttr_hours": {bad}')
    assert bad in text
    (tmp_path / "metrics_sandbox_seed42.json").write_text(text, encoding="utf-8")
    client = make_client(db_session, [])
    resp = client.get("/metrics")
    assert resp.status_code == 200
    kpi, mttd_mttr, rec = resp.json()["metrics"]
    assert kpi["available"] is True and rec["available"] is True
    assert mttd_mttr["available"] is False and mttd_mttr["before"] is None and mttd_mttr["after"] is None
    assert client.get("/metrics").status_code == 200  # repeated call


def test_non_finite_in_assumptions_does_not_break_response(db_session, tmp_path):
    rep = make_report()
    rep["assumptions"][0]["value"] = "NaN-PLACEHOLDER"
    text = json.dumps(rep).replace('"NaN-PLACEHOLDER"', "NaN")
    (tmp_path / "metrics_sandbox_seed42.json").write_text(text, encoding="utf-8")
    resp = make_client(db_session, []).get("/metrics")
    assert resp.status_code == 200
    assert resp.json()["assumptions"][0]["value"] is None


def test_check_run_requires_numbers_when_asked(db_session, monkeypatch, capsys):
    """SME_CHECK_METRICS=1 (set by demo.sh --fresh-db --check): /metrics without numbers fails the check."""
    from tests.test_check_run_r10a import KPI, SOP, check_run
    from tests.test_demo_llm_branches_r10a import make_client as demo_client

    c = demo_client(db_session, monkeypatch)  # no report in SME_REPORTS_DIR
    monkeypatch.setenv("SME_CHECK_METRICS", "1")
    assert check_run.check_many(c, KPI, SOP) is False
    assert "CHECK FAILED: GET /metrics" in capsys.readouterr().err
    monkeypatch.delenv("SME_CHECK_METRICS")
    assert check_run.check_many(c, KPI, SOP) is True
