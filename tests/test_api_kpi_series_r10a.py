"""R10a/dev-02: GET /kpi/series (read only, same data as the tools, limits from Detect)."""

import json
import re
from pathlib import Path

from backend.api.kpi_series import kpi_series
from backend.domain_config import load_domain_config
from backend.sandbox import generate_dataset
from tests.test_act import improve_answer, investigate_script
from tests.test_api import make_client, sse_events, start

CFG = load_domain_config()
KPI = CFG.kpis[0].name
PAYLOADS = Path(__file__).resolve().parents[1] / "docs" / "schema" / "payloads.md"
MARKER = "Ví dụ phản hồi `GET /kpi/series`:"


def example_response() -> dict:
    text = PAYLOADS.read_text(encoding="utf-8")
    assert MARKER in text
    block = re.search(r"```json\n(.*?)\n```", text[text.index(MARKER) :], re.DOTALL)
    return json.loads(block.group(1))


def anomaly_event(client):
    run = start(client)
    msgs = sse_events(client, run["run_id"])
    return next(m["data"]["payload"] for m in msgs if m["event"] == "anomaly_detected")


def test_series_matches_anomaly_event_of_a_run(db_session):
    client = make_client(db_session, [[*investigate_script(), improve_answer()]])
    ev = anomaly_event(client)
    body = client.get("/kpi/series", params={"kpi": ev["kpi"], "machine": ev["machine"], "shift": ev["shift"]}).json()
    assert body["points"] and set(body["points"][0]) == {"ts", "value"}
    assert body["baseline"] == ev["baseline"] and body["upper_limit"] == ev["upper_limit"]
    assert any(a["start"] == ev["start"] and a["end"] == ev["end"] for a in body["anomalies"])
    assert client.get("/kpi/series", params={"kpi": ev["kpi"], "machine": ev["machine"], "shift": ev["shift"]}).json() == body


def test_response_keys_match_payloads_example(db_session):
    client = make_client(db_session, [])
    ex = example_response()
    body = client.get("/kpi/series", params={"kpi": KPI, "machine": CFG.demo.machine_id}).json()
    assert set(body) == set(ex)
    assert set(body["points"][0]) == set(ex["points"][0])
    assert body["anomalies"] and set(body["anomalies"][0]) == set(ex["anomalies"][0])
    all_machines = client.get("/kpi/series", params={"kpi": KPI}).json()
    assert set(all_machines) == set(ex) and all_machines["baseline"] is None and all_machines["upper_limit"] is None


def test_bad_parameters_are_422(db_session):
    client = make_client(db_session, [])
    for params in (
        {},  # kpi is required
        {"kpi": "nope"},
        {"kpi": KPI, "machine": "M99"},
        {"kpi": KPI, "shift": "dawn"},
        {"kpi": KPI, "start": "not-a-date"},
    ):
        assert client.get("/kpi/series", params=params).status_code == 422, params


def test_empty_range_gives_no_points(db_session):
    client = make_client(db_session, [])
    r = client.get("/kpi/series", params={"kpi": KPI, "start": "2030-01-01", "end": "2030-02-01"})
    assert r.status_code == 200 and r.json()["points"] == [] and r.json()["anomalies"] == []
    r = client.get("/kpi/series", params={"kpi": KPI, "start": "2026-03-01", "end": "2026-03-01"})
    assert r.status_code == 200 and r.json()["points"] == []


def test_range_filters_points(db_session):
    client = make_client(db_session, [])
    r = client.get("/kpi/series", params={"kpi": KPI, "machine": "M01", "start": "2026-02-01", "end": "2026-02-08"})
    pts = r.json()["points"]
    assert 0 < len(pts) <= 21 and all("2026-02-01" <= p["ts"] < "2026-02-08" for p in pts)


def test_points_are_capped_and_response_small(db_session):
    tables = generate_dataset(seed=42).tables
    full = kpi_series(tables, CFG, KPI)
    assert len(json.dumps(full)) < 1_000_000
    small = kpi_series(tables, CFG, KPI, max_points=50)
    days = {p["ts"][:10] for p in full["points"]}
    assert len(full["points"]) > 50 and len(small["points"]) == len(days)  # merged into one point per day
    assert all(p["ts"].endswith("T00:00:00") for p in small["points"])
    assert small["anomalies"] == full["anomalies"]
