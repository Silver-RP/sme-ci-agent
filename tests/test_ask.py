"""R4/dev-03: Ask node (interrupt) + resume from the Postgres checkpointer (scripted LLM, no network)."""

import json
import uuid
from functools import cache

import pytest
from langgraph.types import Command

from backend.agent.checkpoint import postgres_checkpointer
from backend.agent.graph import build_graph
from backend.agent.llm import ScriptedLLM
from backend.agent.nodes.ask import needs_question
from backend.agent.state import Hypothesis, new_state
from backend.domain_config import AskParams, load_domain_config
from backend.sandbox import generate_dataset
from backend.tools.readonly import ToolContext

CFG = load_domain_config()


@cache
def _tables():
    return generate_dataset(seed=42).tables


@pytest.fixture
def ctx(db_session):
    return ToolContext(tables=_tables(), session=db_session, run_id="run_ask")


def final(conf, gap=False, group="machine"):
    return json.dumps(
        {
            "hypotheses": [{"group": group, "description": "setpoint changed", "confidence": conf}],
            "insufficient_evidence": gap,
        }
    )


def types(events):
    return [e["type"] for e in events]


def cfg_with(max_questions=2, threshold=0.6):
    return CFG.model_copy(update={"ask": AskParams(confidence_threshold=threshold, max_questions=max_questions)})


def run_cfg():
    return {"configurable": {"thread_id": f"t_{uuid.uuid4().hex[:8]}"}}


def start(graph, cfg):
    return graph.invoke(new_state("run_ask", CFG.domain), cfg)


def test_config_values_come_from_yaml():
    assert CFG.ask.confidence_threshold == 0.6 and CFG.ask.max_questions == 2


def test_low_confidence_pauses_at_ask(ctx):
    graph = build_graph(CFG, llm=ScriptedLLM([final(0.3)]), tool_ctx=ctx)
    cfg = run_cfg()
    out = start(graph, cfg)
    snap = graph.get_state(cfg)
    assert snap.next == ("wait_answer",)
    assert "question_asked" in types(out["events"]) and "answer_received" not in types(out["events"])
    assert out["question_count"] == 1
    assert snap.tasks[0].interrupts[0].value["question"]


def test_high_confidence_does_not_ask(ctx):
    graph = build_graph(CFG, llm=ScriptedLLM([final(0.9)]), tool_ctx=ctx)
    cfg = run_cfg()
    out = start(graph, cfg)
    assert graph.get_state(cfg).next == ()
    assert "question_asked" not in types(out["events"])


def test_threshold_boundary_equal_is_not_asked():
    s = new_state("r", CFG.domain)
    s["hypotheses"] = [Hypothesis(group="machine", description="d", confidence=0.6)]
    s["evidence_gap"] = False
    assert needs_question(s, CFG) is False


def test_empty_hypotheses_and_evidence_gap_count_as_missing_evidence():
    s = new_state("r", CFG.domain)
    assert needs_question(s, CFG) is True  # no hypotheses at all, even without the evidence_gap key
    s["hypotheses"] = [Hypothesis(group="machine", description="d", confidence=0.95)]
    s["evidence_gap"] = True
    assert needs_question(s, CFG) is True


def test_gap_flag_asks_even_with_high_confidence(ctx):
    graph = build_graph(CFG, llm=ScriptedLLM([final(0.9, gap=True)]), tool_ctx=ctx)
    cfg = run_cfg()
    out = start(graph, cfg)
    assert graph.get_state(cfg).next == ("wait_answer",)
    assert "question_asked" in types(out["events"])


def test_empty_hypotheses_ask_a_person(ctx):
    empty = json.dumps({"hypotheses": [], "insufficient_evidence": False})
    graph = build_graph(CFG, llm=ScriptedLLM([empty]), tool_ctx=ctx)
    cfg = run_cfg()
    start(graph, cfg)
    assert graph.get_state(cfg).next == ("wait_answer",)


def test_resume_with_answer_goes_back_to_investigate(ctx):
    llm = ScriptedLLM([final(0.3), final(0.9)])
    graph = build_graph(CFG, llm=llm, tool_ctx=ctx)
    cfg = run_cfg()
    start(graph, cfg)
    out = graph.invoke(Command(resume="Setpoint was changed on night shift"), cfg)
    assert "answer_received" in types(out["events"])
    assert {"source": "human_answer", "answer": "Setpoint was changed on night shift"} in out["evidence"]
    assert graph.get_state(cfg).next == ()
    assert out["hypotheses"][0].confidence == 0.9
    # the second investigation saw the human answer
    assert "Setpoint was changed" in llm.calls[1]["messages"][0]["content"]


def test_ask_is_bounded_then_awaits_human(ctx):
    cfg_ = cfg_with(max_questions=2)
    graph = build_graph(cfg_, llm=ScriptedLLM([final(0.1)] * 5), tool_ctx=ctx)
    cfg = run_cfg()
    start(graph, cfg)
    graph.invoke(Command(resume="a1"), cfg)
    out = graph.invoke(Command(resume="a2"), cfg)
    assert graph.get_state(cfg).next == ()
    assert types(out["events"]).count("question_asked") == 2
    assert out["status"] == "awaiting_human"
    last = out["events"][-1]
    assert last["type"] == "run_finished" and last["payload"]["status"] == "awaiting_human"
    assert not out.get("proposal")  # never concludes by itself


def test_zero_max_questions_halts_without_asking(ctx):
    graph = build_graph(cfg_with(max_questions=0), llm=ScriptedLLM([final(0.1)]), tool_ctx=ctx)
    out = start(graph, run_cfg())
    assert "question_asked" not in types(out["events"]) and out["status"] == "awaiting_human"


def test_repeated_runs_do_not_leak_state(ctx):
    for _ in range(2):
        graph = build_graph(cfg_with(max_questions=1), llm=ScriptedLLM([final(0.1), final(0.1)]), tool_ctx=ctx)
        cfg = run_cfg()
        start(graph, cfg)
        out = graph.invoke(Command(resume="x"), cfg)
        assert types(out["events"]).count("question_asked") == 1


def test_events_follow_schema_fields(ctx):
    graph = build_graph(CFG, llm=ScriptedLLM([final(0.3)]), tool_ctx=ctx)
    out = start(graph, run_cfg())
    ev = next(e for e in out["events"] if e["type"] == "question_asked")
    assert ev["agent"] and ev["domain"] == CFG.domain and ev["payload"]["question"]


def test_resume_from_new_graph_over_postgres(ctx, shared_db_url):
    cfg = run_cfg()
    with postgres_checkpointer(shared_db_url) as saver:
        g1 = build_graph(CFG, checkpointer=saver, llm=ScriptedLLM([final(0.3)]), tool_ctx=ctx)
        start(g1, cfg)
        assert g1.get_state(cfg).next == ("wait_answer",)
    # brand-new saver (new connection) and brand-new graph, same thread_id
    with postgres_checkpointer(shared_db_url) as saver2:
        g2 = build_graph(CFG, checkpointer=saver2, llm=ScriptedLLM([final(0.9)]), tool_ctx=ctx)
        assert g2.get_state(cfg).next == ("wait_answer",)
        out = g2.invoke(Command(resume="human says wear"), cfg)
        assert "answer_received" in types(out["events"])
        assert any(e.get("answer") == "human says wear" for e in out["evidence"])
        assert out["events"][0]["type"] == "tool_called"  # earlier events survived the restart
        assert g2.get_state(cfg).next == ()
