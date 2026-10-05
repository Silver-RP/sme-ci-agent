"""dev-03: graph skeleton, fake tool, event contract."""

import json
from pathlib import Path

from backend.agent import graph as graph_mod
from backend.agent.graph import build_graph
from backend.agent.state import new_state
from backend.domain_config import load_domain_config
from backend.tools import fake_metrics

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "docs" / "schema" / "events.json").read_text()
)


def _run():
    cfg = load_domain_config()
    g = build_graph(cfg)
    out = g.invoke(new_state("run_t", cfg.domain), config={"configurable": {"thread_id": "t1"}})
    return cfg, out


def _validate_event(ev):
    assert set(ev) <= set(SCHEMA["properties"])  # additionalProperties false
    for key in SCHEMA["required"]:
        assert key in ev
    for key in ("event_id", "run_id", "ts", "type", "agent", "domain"):
        assert isinstance(ev[key], str) and ev[key]
    assert ev["type"] in SCHEMA["properties"]["type"]["enum"]
    assert ev["agent"] in SCHEMA["properties"]["agent"]["enum"]
    assert isinstance(ev["payload"], dict)


def test_graph_runs_end_to_end_with_hypotheses():
    cfg, out = _run()
    assert out["hypotheses"]
    assert out["anomaly"]["kpi"] == cfg.kpis[0].name
    assert {h.group for h in out["hypotheses"]} <= set(cfg.hypothesis_groups)


def test_events_valid_against_contract():
    cfg, out = _run()
    assert out["events"]
    for ev in out["events"]:
        _validate_event(ev)
        assert ev["domain"] == cfg.domain
    types = [e["type"] for e in out["events"]]
    assert "anomaly_detected" in types and "hypothesis_updated" in types
    assert len({e["event_id"] for e in out["events"]}) == len(out["events"])


def test_investigate_calls_tool_with_params(monkeypatch):
    calls = []
    real = fake_metrics.fetch_kpi_breakdown

    def spy(kpi, start, end):
        calls.append((kpi, start, end))
        return real(kpi, start, end)

    monkeypatch.setattr(graph_mod, "fetch_kpi_breakdown", spy)
    cfg = load_domain_config()
    build_graph(cfg).invoke(
        new_state("run_s", cfg.domain), config={"configurable": {"thread_id": "t2"}}
    )
    assert len(calls) >= 2
    assert all(c[0] == cfg.kpis[0].name and c[1] < c[2] for c in calls)


def test_fake_tool_is_parametric_and_offline():
    a = fake_metrics.fetch_kpi_breakdown("rework_rate", "2026-10-01", "2026-10-02")
    assert a["kpi"] == "rework_rate" and (a["start"], a["end"]) == ("2026-10-01", "2026-10-02")
