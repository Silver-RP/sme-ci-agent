"""R10d/dev-01: /kpi/series rejects time zones (422, #110); config SOP version has null run_id/created_at (#112)."""

import pytest

from tests.test_act import HUMAN, SOP_ID, approve, improve_answer, investigate_script
from tests.test_api import make_client, start
from tests.test_api_kpi_series_r10a import KPI

NAIVE_OK = {"kpi": KPI, "start": "2026-01-01T00:00:00", "end": "2026-02-01T00:00:00"}


@pytest.mark.parametrize("name", ["start", "end"])
@pytest.mark.parametrize("value", ["2026-01-01T00:00:00Z", "2026-01-01T00:00:00+09:00"])
def test_series_with_time_zone_is_422_naming_the_parameter(db_session, name, value):
    client = make_client(db_session, [])
    params = {**NAIVE_OK, name: value}
    r = client.get("/kpi/series", params=params)
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert name in detail and "time zone" in detail


def test_series_without_time_zone_is_still_200_and_repeatable(db_session):
    client = make_client(db_session, [])
    first = client.get("/kpi/series", params=NAIVE_OK)
    assert first.status_code == 200
    assert client.get("/kpi/series", params={**NAIVE_OK, "end": "2026-01-01T00:00:00Z"}).status_code == 422
    assert client.get("/kpi/series", params=NAIVE_OK).json() == first.json()


def test_config_sop_version_has_null_run_id_and_created_at_after_a_run(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    run = start(client)
    assert approve(client, run["run_id"], HUMAN).json()["state"] == "finished"
    versions = client.get(f"/sop/{SOP_ID}/versions").json()["versions"]
    config = [v for v in versions if v["created_by"] == "config"]
    assert config and all(v["run_id"] is None and v["created_at"] is None for v in config)
    made = [v for v in versions if v["created_by"] != "config"]
    assert made and all(v["run_id"] == run["run_id"] and v["created_at"] for v in made)


def test_payloads_doc_kpi_series_row_states_time_zone_rule_and_422():
    from pathlib import Path

    doc = Path(__file__).resolve().parents[1] / "docs" / "schema" / "payloads.md"
    rows = [ln for ln in doc.read_text(encoding="utf-8").splitlines() if ln.startswith("|") and "/kpi/series" in ln]
    assert len(rows) == 1
    assert "múi giờ" in rows[0] and "422" in rows[0]
    assert "Z" in rows[0] and "+09:00" in rows[0]
