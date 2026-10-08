"""R8/dev-03: robust against a real LLM (bounded tool output, tolerant parsing, evidence needed, memory of failures).

Scripted LLM, seed 42, no network.
"""

import json
from functools import cache

import pytest
from langgraph.types import Command

from backend.agent.graph import build_graph
from backend.agent.jsonutil import extract_json_object, parse_bool
from backend.agent.llm import (
    DEFAULT_MAX_TOKENS,
    AnthropicLLM,
    LLMConfigError,
    LLMResponse,
    ScriptedLLM,
    ToolCall,
)
from backend.agent.nodes.ask import needs_question
from backend.agent.nodes.improve import ProposalError, compact_evidence, run_improvement
from backend.agent.nodes.investigate import InvestigationFormatError, run_investigation
from backend.agent.state import Hypothesis, new_state
from backend.domain_config import ImproveParams, InvestigateParams, load_domain_config
from backend.sandbox import generate_dataset
from backend.sandbox.post_change import fix_addresses_cause
from backend.tools.readonly import ToolContext, get_shift_schedule, query_logs
from tests.test_act import (
    HUMAN,
    cfg_run,
    improve_answer,
    investigate_script,
    make,
    start,
    to_rollback_prompt,
)
from tests.test_ask import final, run_cfg, tool_step, types

CFG = load_domain_config()
KPI = CFG.kpis[0].name


@cache
def _tables():
    return generate_dataset(seed=42).tables


@pytest.fixture
def ctx(db_session):
    return ToolContext(tables=_tables(), session=db_session, run_id="run_r8")


def state():
    s = new_state("run_r8", CFG.domain)
    s["anomaly"] = {"kpi": KPI, "machine": "M02", "shift": "night"}
    return s


def good_json(**over):
    d = {"hypotheses": [{"group": "machine", "description": "wrong_setpoint", "confidence": 0.8}],
         "insufficient_evidence": False}
    d.update(over)
    return json.dumps(d)


# ---- 1. bounded tool output and prompt size ----


def test_query_logs_unfiltered_is_cut_and_flagged(ctx):
    total = len(_tables()["kpi_log"][lambda d: d["kpi"] == KPI])
    assert total > CFG.investigate.max_log_rows  # the fixture really is bigger than the limit
    out = query_logs(ctx, kpi=KPI)
    assert len(out["rows"]) == CFG.investigate.max_log_rows == out["returned"]
    assert out["truncated"] is True and out["count"] == total
    assert out["mean_by_machine"]  # summary covers all matching rows


def test_query_logs_small_result_not_flagged_and_limit_from_config(ctx):
    small = query_logs(ctx, kpi=KPI, machine_id="M02", start="2026-03-20", end="2026-03-21")
    assert small["truncated"] is False and len(small["rows"]) == small["count"] > 0
    cfg = CFG.model_copy(update={"investigate": InvestigateParams(max_log_rows=3)})
    ctx2 = ToolContext(tables=_tables(), session=ctx.session, config=cfg, run_id="r")
    out = query_logs(ctx2, kpi=KPI)
    assert len(out["rows"]) == 3 and out["truncated"] is True
    again = query_logs(ctx2, kpi=KPI)  # repeated call: same answer, no leaked state
    assert again["rows"] == out["rows"]


def test_query_logs_machine_log_and_shift_schedule_are_cut_too(ctx):
    cfg = CFG.model_copy(update={"investigate": InvestigateParams(max_log_rows=2)})
    c = ToolContext(tables=_tables(), session=ctx.session, config=cfg, run_id="r")
    assert query_logs(c, kpi=KPI, source="machine_log")["returned"] <= 2
    sch = get_shift_schedule(c)
    assert len(sch["rows"]) == 2 and sch["truncated"] is True and sch["count"] > 2


def test_compact_evidence_keeps_index_and_cuts_big_items():
    big = {"source": "tool", "tool": "query_logs", "result": {"count": 900, "truncated": True, "rows": [{"v": i} for i in range(500)]}}
    small = {"source": "human_answer", "answer": "ok"}
    huge_text = {"source": "x", "blob": "z" * 5000}
    out = compact_evidence([small, big, huge_text], 400)
    assert list(out) == [0, 1, 2] and out[0] == small
    assert "rows" not in out[1]["result"] and out[1]["result"]["count"] == 900
    assert len(out[2]) <= 400 and out[2].endswith("(truncated)")
    assert compact_evidence([], 400) == {}


def test_improve_prompt_stays_small_in_e2e(db_session):
    q = {"kpi": KPI}
    wide = [
        LLMResponse(tool_calls=[ToolCall(id=f"t{i}", name="query_logs", arguments=q)]) for i in range(3)
    ]
    script = [*wide, final(0.8), improve_answer()]
    graph, llm = make(db_session, script)
    start(graph, cfg_run())
    improve_prompt = llm.calls[-1]["messages"][0]["content"]
    assert "Evidence" in improve_prompt
    assert len(improve_prompt) < 6000
    # the raw (cut) tool result did reach Investigate, so the bound is Improve's own summarising
    assert any(m["role"] == "user" and "tool_result" in json.dumps(m["content"]) for m in llm.calls[-2]["messages"])


# ---- 2. parsing ----


def test_extract_json_object_balanced_and_skips_prose_braces():
    text = 'Sure {not json} here is it: {"a": {"b": "}"}, "hypotheses": []} thanks {x}'
    assert extract_json_object(text, "hypotheses") == {"a": {"b": "}"}, "hypotheses": []}
    assert extract_json_object("no braces") is None
    assert extract_json_object("{broken", None) is None
    assert extract_json_object("") is None and extract_json_object(None) is None


@pytest.mark.parametrize("v,expected", [("false", False), ("False", False), ("true", True), (True, True),
                                         (False, False), (None, False), (0, False), (1, True), ("no", False)])
def test_parse_bool(v, expected):
    assert parse_bool(v) is expected


def test_parse_bool_unclear_raises():
    with pytest.raises(ValueError):
        parse_bool("maybe")


def test_investigate_parses_text_around_extra_keys_and_string_false(ctx):
    text = (
        "Here is my analysis {draft}:\n```json\n"
        + good_json(insufficient_evidence="false", notes="extra", extra={"x": 1})
        + "\n```\nHope this helps {end}"
    ).replace('"confidence": 0.8}', '"confidence": 0.8, "why": "because"}')
    out = run_investigation(state(), CFG, ScriptedLLM([text]), ctx)
    assert out["evidence_gap"] is False
    assert out["hypotheses"][0].group == "machine" and out["hypotheses"][0].confidence == 0.8


def test_investigate_string_true_means_gap(ctx):
    out = run_investigation(state(), CFG, ScriptedLLM([good_json(insufficient_evidence="true")]), ctx)
    assert out["evidence_gap"] is True


def test_investigate_broken_twice_raises_clear_error_not_hang(ctx):
    llm = ScriptedLLM(["{bad json", "still {not: json"] + [good_json()] * 5)
    with pytest.raises(InvestigationFormatError, match="parsed after 2 attempts"):
        run_investigation(state(), CFG, llm, ctx)
    assert len(llm.calls) == 2  # asked once to fix, then stopped; never loops on


def test_investigate_broken_once_is_fixed_on_request(ctx):
    llm = ScriptedLLM(["{bad json", good_json()])
    out = run_investigation(state(), CFG, llm, ctx)
    assert out["hypotheses"]
    assert "Rejected" in json.dumps(llm.calls[1]["messages"][-1])  # the LLM was told what was wrong


def test_investigate_unclear_bool_counts_as_format_error(ctx):
    llm = ScriptedLLM([good_json(insufficient_evidence="maybe"), good_json(insufficient_evidence="maybe")])
    with pytest.raises(InvestigationFormatError):
        run_investigation(state(), CFG, llm, ctx)


def test_investigate_format_retries_from_config(ctx):
    cfg = CFG.model_copy(update={"investigate": InvestigateParams(max_format_retries=0)})
    with pytest.raises(InvestigationFormatError):
        run_investigation(state(), cfg, ScriptedLLM(["nope", good_json()]), ctx)


def test_improve_parses_text_around_and_extra_keys(ctx):
    d = json.loads(improve_answer())
    d["confidence_note"] = "extra"
    d["expected_kpi"]["unit"] = "ratio"
    text = "Proposal {draft} below:\n" + json.dumps(d) + "\nDone {ok}"
    s = state()
    s["hypotheses"] = [Hypothesis(group="machine", description="wrong_setpoint", confidence=0.8)]
    s["evidence"] = [{"source": "tool", "result": {}}]
    out = run_improvement(s, CFG, ScriptedLLM([text]), ctx)
    assert out["proposal"]["change"]


def test_improve_broken_twice_raises_and_once_is_fixed(ctx):
    s = state()
    s["hypotheses"] = [Hypothesis(group="machine", description="wrong_setpoint", confidence=0.8)]
    s["evidence"] = [{"source": "tool", "result": {}}]
    llm = ScriptedLLM(["{oops", "{oops again", improve_answer()])
    with pytest.raises(ProposalError, match="after 2 attempts"):
        run_improvement(s, CFG, llm, ctx)
    assert len(llm.calls) == 2
    llm2 = ScriptedLLM(["{oops", improve_answer()])
    assert run_improvement(s, CFG, llm2, ctx)["proposal"]["change"]
    cfg0 = CFG.model_copy(update={"improve": ImproveParams(max_format_retries=0)})
    with pytest.raises(ProposalError):
        run_improvement(s, cfg0, ScriptedLLM(["{oops", improve_answer()]), ctx)


# ---- 3. conclusion without tool evidence -> Ask ----


def test_confident_conclusion_without_tool_result_asks(ctx):
    graph = build_graph(CFG, llm=ScriptedLLM([final(0.95)]), tool_ctx=ctx, full_loop=False)
    cfg = run_cfg()
    out = graph.invoke(new_state("run_r8", CFG.domain), cfg)
    assert graph.get_state(cfg).next == ("wait_answer",)
    q = next(e for e in out["events"] if e["type"] == "question_asked")
    assert "no tool result" in q["payload"]["question"]


def test_confident_conclusion_without_tool_result_never_reaches_improve(db_session):
    graph, llm = make(db_session, [final(0.95)])
    cfg = cfg_run()
    out = start(graph, cfg)
    assert graph.get_state(cfg).next == ("wait_answer",)
    assert "proposal_created" not in types(out["events"]) and len(llm.calls) == 1  # Improve not called


def test_failed_tool_call_is_not_evidence():
    s = new_state("r", CFG.domain)
    s["hypotheses"] = [Hypothesis(group="machine", description="d", confidence=0.95)]
    s["evidence"] = [{"source": "tool", "tool": "correlate", "arguments": {}, "error": "boom"}]
    assert needs_question(s, CFG) is True
    s["evidence"].append({"source": "tool", "tool": "correlate", "arguments": {}, "result": {"x": 1}})
    assert needs_question(s, CFG) is False


def test_with_tool_result_goes_on_to_improve(db_session):
    graph, _ = make(db_session, [*investigate_script(), improve_answer()])
    cfg = cfg_run()
    start(graph, cfg)
    assert graph.get_state(cfg).next == ("wait_approval",)


def test_tool_step_helper_is_a_tool_call():  # guards the shared helper other tests rely on
    assert tool_step().tool_calls[0].name == "correlate"


# ---- 4. Investigate again remembers why ----


def test_after_rollback_prompt_has_reason_and_measurement(db_session):
    graph, cfg, _, llm = to_rollback_prompt(db_session)
    calls = len(llm.calls)
    out = graph.invoke(
        Command(resume={"decision": "approved", "decided_by": "bob", "reason": "defect rate stayed high"}), cfg
    )
    prompt = llm.calls[calls]["messages"][0]["content"]
    assert "defect rate stayed high" in prompt
    assert "change rolled back" in prompt and "measurement" in prompt
    assert "Restore setpoint to 180" in prompt  # which change was rolled back
    rb = next(e for e in out["evidence"] if e.get("source") == "rollback")
    assert rb["human_reason"] == "defect rate stayed high" and rb["measurement"]["passed"] is False


def test_after_rejection_prompt_has_reason(db_session):
    script = [*investigate_script(), improve_answer(), improve_answer()]  # rejection goes back to Improve
    graph, llm = make(db_session, script)
    cfg = cfg_run()
    start(graph, cfg)
    calls = len(llm.calls)
    graph.invoke(Command(resume={"decision": "rejected", "decided_by": "alice", "reason": "too risky on night shift"}), cfg)
    # Improve is re-run after a rejection; the rejection is in the evidence the next Investigate/Improve sees
    assert any("too risky on night shift" in json.dumps(c["messages"], default=str) for c in llm.calls[calls:])


def test_investigate_prompt_with_rejection_and_rollback_evidence(ctx):
    s = state()
    s["evidence"] = [
        {"source": "human_rejection", "reason": "too risky", "rejected_change": "turn it off"},
        {"source": "rollback", "reason": 0.2, "human_reason": "still high", "rolled_back_change": "fix A"},
    ]
    llm = ScriptedLLM([good_json()])
    run_investigation(s, CFG, llm, ctx)
    prompt = llm.calls[0]["messages"][0]["content"]
    assert "too risky" in prompt and "turn it off" in prompt and "still high" in prompt and "fix A" in prompt


def test_investigate_prompt_without_history_has_no_attempts_section(ctx):
    llm = ScriptedLLM([good_json()])
    run_investigation(state(), CFG, llm, ctx)
    assert "did NOT work" not in llm.calls[0]["messages"][0]["content"]


# ---- 5. max_tokens ----


def _llm(**kw):
    class Client:
        pass

    return AnthropicLLM(model="m", client=Client(), **kw)


def test_max_tokens_default_env_and_arg(monkeypatch):
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    assert _llm().max_tokens == DEFAULT_MAX_TOKENS >= 4096
    monkeypatch.setenv("LLM_MAX_TOKENS", "8000")
    assert _llm().max_tokens == 8000
    assert _llm(max_tokens=123).max_tokens == 123
    monkeypatch.setenv("LLM_MAX_TOKENS", " ")
    assert _llm().max_tokens == DEFAULT_MAX_TOKENS


@pytest.mark.parametrize("bad", ["abc", "0", "-5"])
def test_max_tokens_bad_env_is_clear_error(monkeypatch, bad):
    monkeypatch.setenv("LLM_MAX_TOKENS", bad)
    with pytest.raises(LLMConfigError, match="LLM_MAX_TOKENS"):
        _llm()


# ---- 6. fix_addresses_cause with wording a real LLM would use ----


@pytest.mark.parametrize(
    "desc",
    [
        "wrong_setpoint",
        "Wrong setpoint on machine M02",
        "Setpoint drifted away from the SOP value after the night shift change",
        "Operator changed the set point manually",
        "The set-point was altered",
        "Incorrect setpoints were applied",
    ],
)
def test_fix_addresses_cause_real_wording(desc):
    assert fix_addresses_cause({"description": desc}) is True


@pytest.mark.parametrize("desc", ["sensor calibration drift", "material batch change", "", "worn tool"])
def test_fix_addresses_cause_other_causes(desc):
    assert fix_addresses_cause({"description": desc}) is False
    assert fix_addresses_cause(None) is False


def test_human_reason_not_needed_for_rollback(db_session):
    """A rollback confirmed without a reason still works and records None."""
    graph, cfg, _, _ = to_rollback_prompt(db_session)
    out = graph.invoke(Command(resume=HUMAN), cfg)
    rb = next(e for e in out["evidence"] if e.get("source") == "rollback")
    assert rb["human_reason"] is None
