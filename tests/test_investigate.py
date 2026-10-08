"""R4/dev-02: Investigate node with an LLM tool-use loop (scripted LLM, seed 42, no network)."""

import json
from functools import cache
from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.agent.graph import build_graph
from backend.agent.llm import LLMResponse, ScriptedLLM, ToolCall
from backend.agent.nodes.investigate import run_investigation
from backend.agent.state import new_state
from backend.db.models import AuditLog
from backend.domain_config import load_domain_config
from backend.sandbox import generate_dataset
from backend.tools.readonly import ToolContext

CFG = load_domain_config()
KPI = CFG.kpis[0].name
SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "docs" / "schema" / "events.json").read_text())


@cache
def _tables():
    return generate_dataset(seed=42).tables


@pytest.fixture
def ctx(db_session):
    return ToolContext(tables=_tables(), session=db_session, run_id="run_inv")


def final(*hyps, gap=False):
    return json.dumps(
        {
            "hypotheses": [{"group": g, "description": d, "confidence": c} for g, d, c in hyps],
            "insufficient_evidence": gap,
        }
    )


def call(i, name, **args):
    return LLMResponse(tool_calls=[ToolCall(id=f"t{i}", name=name, arguments=args)])


def state():
    s = new_state("run_inv", CFG.domain)
    s["anomaly"] = {"kpi": KPI, "machine": "M02", "shift": "night"}
    return s


def audits(s):
    return s.scalar(select(func.count()).select_from(AuditLog))


def good_script():
    return [
        call(1, "correlate", kpi=KPI, machine_id="M02"),
        call(2, "get_shift_schedule", machine_id="M02", start="2026-03-10", end="2026-03-12"),
        final(("machine", "setpoint changed", 0.8), ("people", "substitute operator", 0.3)),
    ]


def test_scripted_correlate_then_schedule_top_is_wrong_setpoint(ctx):
    out = run_investigation(state(), CFG, ScriptedLLM(good_script()), ctx)
    top = out["hypotheses"][0]
    assert top.group == "machine" and top.confidence == 0.8
    tools = [e for e in out["evidence"] if e.get("source") == "tool"]
    assert [e["tool"] for e in tools] == ["correlate", "get_shift_schedule"]
    corr = tools[0]["result"]["correlations"]  # real tool output
    assert corr[0]["hypothesis"] == "wrong_setpoint" and corr[0]["strength"] > 0.3
    assert tools[1]["result"]["count"] > 0
    assert out["evidence_gap"] is False


def test_tool_calls_go_through_audited_layer(ctx):
    before = audits(ctx.session)
    run_investigation(state(), CFG, ScriptedLLM(good_script()), ctx)
    assert audits(ctx.session) - before == 2


def test_events_match_schema_and_config(ctx):
    out = run_investigation(state(), CFG, ScriptedLLM(good_script()), ctx)
    evs = out["events"]
    assert [e["type"] for e in evs] == ["tool_called", "tool_called", "hypothesis_updated"]
    for ev in evs:
        assert set(ev) == set(SCHEMA["required"])
        assert ev["agent"] == "investigation" and ev["domain"] == CFG.domain
        assert ev["type"] in SCHEMA["properties"]["type"]["enum"]
    assert len({e["event_id"] for e in evs}) == 3


def test_domain_falls_back_to_config(ctx):
    s = state()
    s["domain"] = ""
    out = run_investigation(s, CFG, ScriptedLLM(good_script()), ctx)
    assert all(e["domain"] == CFG.domain for e in out["events"])


def test_unknown_tool_and_bad_params_recorded_and_retry(ctx):
    script = [
        call(1, "drop_tables"),
        call(2, "correlate", kpi=KPI),  # missing machine_id
        call(3, "correlate", kpi="nope", machine_id="M02"),  # bad KPI
        call(4, "correlate", kpi=KPI, machine_id="M02"),
        final(("machine", "setpoint", 0.7)),
    ]
    llm = ScriptedLLM(script)
    out = run_investigation(state(), CFG, llm, ctx)
    errs = [e for e in out["evidence"] if "error" in e]
    assert len(errs) == 3 and "unknown tool" in errs[0]["error"]
    ok = [e for e in out["evidence"] if "result" in e]
    assert len(ok) == 1 and out["hypotheses"][0].group == "machine"
    # the LLM saw the errors and retried
    last_user = llm.calls[-1]["messages"][-1]["content"]
    assert last_user[0]["type"] == "tool_result"
    assert any(m["content"][0].get("is_error") for m in llm.calls[-1]["messages"] if isinstance(m["content"], list) and m["role"] == "user" and m["content"][0]["type"] == "tool_result")
    assert [e["payload"]["ok"] for e in out["events"] if e["type"] == "tool_called"] == [False, False, False, True]


def test_step_limit_marks_evidence_gap(ctx):
    n = CFG.investigate.max_tool_steps
    llm = ScriptedLLM([call(i, "read_sop", sop_id="SOP-RFL-001") for i in range(n)] + [final(("machine", "x", 0.9))])
    out = run_investigation(state(), CFG, llm, ctx)
    assert len(llm.calls) == n  # stopped at the limit, last scripted answer never requested
    assert out["evidence_gap"] is True and out["hypotheses"] == []
    assert out["events"][-1]["type"] == "hypothesis_updated"
    assert out["events"][-1]["payload"]["insufficient_evidence"] is True


def test_step_limit_comes_from_config(ctx):
    cfg = CFG.model_copy(update={"investigate": CFG.investigate.model_copy(update={"max_tool_steps": 2})})
    llm = ScriptedLLM([call(i, "read_sop", sop_id="SOP-RFL-001") for i in range(5)])
    out = run_investigation(state(), cfg, llm, ctx)
    assert len(llm.calls) == 2 and out["evidence_gap"] is True


def test_llm_flagging_insufficient_evidence(ctx):
    out = run_investigation(state(), CFG, ScriptedLLM([final(("machine", "maybe", 0.2), gap=True)]), ctx)
    assert out["evidence_gap"] is True and out["hypotheses"][0].confidence == 0.2


def test_group_not_in_yaml_is_rejected_then_corrected(ctx):
    llm = ScriptedLLM([final(("cosmic_rays", "x", 0.9)), final(("machine", "setpoint", 0.6))])
    out = run_investigation(state(), CFG, llm, ctx)
    assert [h.group for h in out["hypotheses"]] == ["machine"]
    assert any("cosmic_rays" in e.get("error", "") for e in out["evidence"])


def test_only_invalid_group_never_accepted(ctx):
    llm = ScriptedLLM([final(("cosmic_rays", "x", 0.9))] * CFG.investigate.max_tool_steps)
    out = run_investigation(state(), CFG, llm, ctx)
    assert out["hypotheses"] == [] and out["evidence_gap"] is True


def test_garbage_final_answer_does_not_crash(ctx):
    out = run_investigation(state(), CFG, ScriptedLLM(["not json", final(("method", "sop", 0.5))]), ctx)
    assert out["hypotheses"][0].group == "method"


def test_hypotheses_sorted_by_confidence(ctx):
    out = run_investigation(state(), CFG, ScriptedLLM([final(("people", "a", 0.2), ("machine", "b", 0.9))]), ctx)
    assert [h.group for h in out["hypotheses"]] == ["machine", "people"]


def test_repeated_runs_do_not_leak(ctx):
    a = run_investigation(state(), CFG, ScriptedLLM(good_script()), ctx)
    b = run_investigation(state(), CFG, ScriptedLLM(good_script()), ctx)
    assert [e["event_id"] for e in a["events"]] == [e["event_id"] for e in b["events"]]
    assert len(a["evidence"]) == len(b["evidence"]) == 2


def test_graph_with_llm_observe_detect_investigate(ctx):
    g = build_graph(CFG, llm=ScriptedLLM(good_script()), tool_ctx=ctx)
    out = g.invoke(new_state("run_g", CFG.domain), config={"configurable": {"thread_id": "inv1"}})
    assert out["hypotheses"][0].group == "machine"
    types = [e["type"] for e in out["events"]]
    assert types[:2] == ["tool_called", "anomaly_detected"] and types[-1] == "hypothesis_updated"
    assert len({e["event_id"] for e in out["events"]}) == len(out["events"])


def test_graph_without_llm_still_uses_mock():
    out = build_graph(CFG).invoke(new_state("m", CFG.domain), config={"configurable": {"thread_id": "m1"}})
    assert out["hypotheses"][0].description.startswith("mock")


def test_graph_llm_requires_tool_ctx():
    g = build_graph(CFG, llm=ScriptedLLM([]))
    with pytest.raises(ValueError):
        g.invoke(new_state("m", CFG.domain), config={"configurable": {"thread_id": "m2"}})
