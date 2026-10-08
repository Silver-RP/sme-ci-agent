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


def _seqs(out):
    return [int(e["event_id"].rsplit("_", 1)[1]) for e in out["events"]]


def test_domain_falls_back_to_config_when_state_has_none():
    cfg = load_domain_config()
    g = build_graph(cfg)
    for state in ({"run_id": "r_nodomain", "evidence": [], "events": []}, new_state("r_empty")):
        out = g.invoke(state, config={"configurable": {"thread_id": f"d_{state['run_id']}"}})
        assert out["events"]
        assert all(e["domain"] == cfg.domain for e in out["events"])


def test_event_ids_restart_per_run_on_same_graph():
    cfg = load_domain_config()
    g = build_graph(cfg)
    outs = [
        g.invoke(new_state(f"run_{i}", cfg.domain), config={"configurable": {"thread_id": f"x{i}"}})
        for i in (1, 2, 3)
    ]
    for i, out in enumerate(outs, 1):
        seqs = _seqs(out)
        assert seqs == list(range(1, len(seqs) + 1))
        assert len({e["event_id"] for e in out["events"]}) == len(out["events"])
        assert all(e["event_id"].startswith(f"evt_run_{i}_") for e in out["events"])


# ---- dev-02 (R7): real Detect inside the graph when tool_ctx is given ----


def _detect_ctx(tables):
    from backend.tools.readonly import ToolContext

    return ToolContext(tables=tables, session=None, run_id="run_det")


def test_graph_with_tool_ctx_emits_anomaly_from_real_detect():
    from backend.detect.statistical import detect
    from backend.sandbox import generate_dataset

    cfg = load_domain_config()
    tables = generate_dataset(seed=42).tables
    expected = detect(tables, cfg, run_id="run_det")[0]["payload"]
    graph = build_graph(cfg, tool_ctx=_detect_ctx(tables))
    for _ in range(2):  # repeated calls: no state leaks between runs
        out = graph.invoke(new_state("run_det", cfg.domain), {"configurable": {"thread_id": f"t{_}"}})
        evs = [e for e in out["events"] if e["type"] == "anomaly_detected"]
        assert len(evs) == 1
        _validate_event(evs[0])
        p = evs[0]["payload"]
        assert p == expected and p["kpi"] in {k.name for k in cfg.kpis}
        assert p["start"] and p["end"] and out["anomaly"] == expected
        assert [e["event_id"] for e in out["events"]] == sorted({e["event_id"] for e in out["events"]})


def test_graph_without_anomaly_finishes_cleanly_without_llm():
    from backend.agent.llm import ScriptedLLM
    from backend.sandbox import generate_dataset

    cfg = load_domain_config()
    tables = dict(generate_dataset(seed=42).tables)
    kpi = cfg.kpis[0].name
    k = tables["kpi_log"].copy()
    k["value"] = k.groupby(["machine_id", "kpi"])["value"].transform("mean")  # flat series: nothing above the limit
    tables["kpi_log"] = k
    llm = ScriptedLLM([])
    graph = build_graph(cfg, llm=llm, tool_ctx=_detect_ctx(tables), full_loop=True)
    cfgrun = {"configurable": {"thread_id": "t_none"}}
    out = graph.invoke(new_state("run_none", cfg.domain), cfgrun)
    assert graph.get_state(cfgrun).next == ()
    assert out["status"] == "no_anomaly" and out["anomaly"] is None and kpi
    last = out["events"][-1]
    assert last["type"] == "run_finished" and last["payload"]["status"] == "no_anomaly"
    assert "anomaly_detected" not in [e["type"] for e in out["events"]]
    _validate_event(last)
    assert llm.calls == []
