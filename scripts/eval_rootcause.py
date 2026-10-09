"""Root-cause eval (R9/dev-03, H-12): does the agent's final hypothesis match the scenario's hidden ground truth?

    uv run python scripts/eval_rootcause.py                  # scripted LLM (3 scenarios: right, wrong, unsure), no key
    uv run python scripts/eval_rootcause.py --llm real       # AnthropicLLM; you set the key and MODEL_REASONING in .env
    uv run python scripts/eval_rootcause.py --seeds 5        # N runs per scenario, a different data seed each

Each run drives the full graph with a NEUTRAL person: every answer is "no further information" and nothing in
the answer, the approval or the reason names the cause, so the agent cannot be handed the solution. A run stops
when it reaches the first proposal (the approval step) or when it halts for a person; the hypothesis it holds
there is compared with ``ground_truth.root_cause`` (group AND cause named in the description).

Scripted scenarios (the fake LLM is a stand-in for the model; the table shows the graph and the judge behave):
    right   confident, correct cause backed by a tool result -> expected accuracy 100%
    wrong   confident, wrong cause backed by a tool result    -> expected accuracy 0%
    unsure  low confidence every time                         -> the agent must ask a person (ask rate > 0)

Columns: accuracy (final hypothesis = ground truth), ask_rate (runs where a person was asked), improve_no_evidence
(runs that reached Improve with low confidence or no tool result), tokens (rough: characters / 4, all LLM calls).
Needs Postgres (DATABASE_URL) with migrations applied. Exit code 0 when the run completes; the scripted
expectations are checked by tests/test_eval_rootcause.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langgraph.types import Command
from sqlalchemy.orm import Session

from backend.agent.checkpoint import memory_checkpointer
from backend.agent.demo_llm import scripted_demo_llm
from backend.agent.graph import build_graph
from backend.agent.llm import (
    LLM,
    AnthropicLLM,
    LLMResponse,
    ScriptedLLM,
    ToolCall,
    ToolSpec,
    prepare_real_llm_env,
)
from backend.agent.nodes.ask import has_tool_evidence
from backend.agent.state import new_state
from backend.db.session import make_engine
from backend.domain_config import DomainConfig, load_domain_config
from backend.sandbox import generate_dataset
from backend.tools.readonly import ToolContext

NEUTRAL_ANSWER = "I have no further information about this."
MAX_STEPS = 12


class CountingLLM:
    """Wraps an LLM and counts calls and (roughly) tokens, so the table can show cost."""

    def __init__(self, inner: LLM) -> None:
        self.inner = inner
        self.calls = 0
        self.chars = 0

    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> LLMResponse:
        self.calls += 1
        self.chars += len(system) + len(json.dumps(messages, default=str))
        resp = self.inner.complete(system, messages, tools)
        self.chars += len(resp.text) + len(json.dumps([c.arguments for c in resp.tool_calls], default=str))
        return resp

    @property
    def tokens(self) -> int:
        return self.chars // 4


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def is_correct(hypothesis: dict[str, Any] | None, root_cause: str, config: DomainConfig) -> bool:
    """Group is the one that holds the true cause in the config, and the description names that cause."""
    if not hypothesis:
        return False
    groups = {g for g, causes in config.hypothesis_groups.items() if root_cause in causes}
    return hypothesis.get("group") in groups and _norm(root_cause) in _norm(hypothesis.get("description", ""))


# --- scripted scenarios -----------------------------------------------------------------------------------------


def _hyp(group: str, cause: str, confidence: float, insufficient: bool = False) -> str:
    return json.dumps(
        {"hypotheses": [{"group": group, "description": cause, "confidence": confidence}],
         "insufficient_evidence": insufficient}
    )


def _wrong_llm(config: DomainConfig) -> ScriptedLLM:
    """Confident and backed by a tool result, but names a cause the data does not support."""
    right = scripted_demo_llm(config, ask_first=False)
    cause = config.signals.batch_change
    group = next(g for g, causes in config.hypothesis_groups.items() if cause in causes)
    kpi = config.kpis[0].name
    investigate = [
        LLMResponse(tool_calls=[ToolCall(id="t1", name="correlate", arguments={"kpi": kpi, "machine_id": config.demo.machine_id})]),
        _hyp(group, cause, 0.8),
    ]
    improve = right._script[-1].text  # same proposal text; only the diagnosis it is based on differs
    return ScriptedLLM([*investigate, improve])


def _unsure_llm(config: DomainConfig) -> ScriptedLLM:
    group = next(iter(config.hypothesis_groups))
    low = _hyp(group, "unclear cause", 0.2, insufficient=True)
    return ScriptedLLM([low] * (config.ask.max_questions + 1))  # first look + one per answer


SCRIPTED: dict[str, Callable[[DomainConfig], ScriptedLLM]] = {
    "right": lambda c: scripted_demo_llm(c, ask_first=False),
    "wrong": _wrong_llm,
    "unsure": _unsure_llm,
}


# --- one run and the table --------------------------------------------------------------------------------------


@dataclass
class RunResult:
    correct: bool
    asked: bool
    reached_improve: bool
    improve_no_evidence: bool
    ended: str  # "proposal" | "halt" | "finished" | "no_anomaly"
    llm_calls: int
    tokens: int


@dataclass
class ScenarioResult:
    name: str
    runs: list[RunResult] = field(default_factory=list)

    def _rate(self, pred: Callable[[RunResult], bool]) -> float:
        return sum(1 for r in self.runs if pred(r)) / len(self.runs) if self.runs else 0.0

    @property
    def accuracy(self) -> float:
        return self._rate(lambda r: r.correct)

    @property
    def ask_rate(self) -> float:
        return self._rate(lambda r: r.asked)

    @property
    def improve_no_evidence(self) -> int:
        return sum(1 for r in self.runs if r.improve_no_evidence)

    @property
    def tokens(self) -> int:
        return sum(r.tokens for r in self.runs)


def run_once(llm: LLM, config: DomainConfig, session: Session, *, seed: int) -> RunResult:
    counted = CountingLLM(llm)
    data = generate_dataset(seed=seed)
    root_cause = data.ground_truth[0].root_cause
    run_id = f"eval_{uuid.uuid4().hex[:8]}"
    ctx = ToolContext(tables=data.tables, session=session, run_id=run_id)
    graph = build_graph(config, checkpointer=memory_checkpointer(), llm=counted, tool_ctx=ctx, full_loop=True)
    cfg = {"configurable": {"thread_id": run_id}}
    payload: object = new_state(run_id, config.domain)
    ended = "finished"
    snap = None
    for _ in range(MAX_STEPS):
        graph.invoke(payload, cfg)
        session.commit()
        snap = graph.get_state(cfg)
        if not snap.next:
            ended = "no_anomaly" if snap.values.get("status") == "no_anomaly" else "finished"
            break
        step = snap.next[0]
        if step == "wait_answer":
            payload = Command(resume=NEUTRAL_ANSWER)
        elif step == "wait_approval":
            ended = "proposal"
            break
        else:  # wait_halt or anything else that needs a person: the eval stops here
            ended = "halt" if step == "wait_halt" else step
            break
    values = snap.values if snap else {}
    proposal = values.get("proposal")
    hyps = values.get("hypotheses") or []
    top = (proposal or {}).get("hypothesis") or (max(hyps, key=lambda h: h.confidence).model_dump() if hyps else None)
    reached = ended == "proposal"
    weak = bool(top) and (top["confidence"] < config.ask.confidence_threshold or not has_tool_evidence(values))
    events = values.get("events", [])
    return RunResult(
        correct=is_correct(top, root_cause, config),
        asked=any(e["type"] == "question_asked" for e in events),
        reached_improve=reached,
        improve_no_evidence=reached and weak,
        ended=ended,
        llm_calls=counted.calls,
        tokens=counted.tokens,
    )


def evaluate(
    llm_factories: dict[str, Callable[[DomainConfig], LLM]],
    config: DomainConfig,
    session: Session,
    *,
    seeds: list[int],
) -> list[ScenarioResult]:
    """Run every scenario once per seed; a fresh LLM per run (a script keeps a cursor)."""
    out = []
    for name, factory in llm_factories.items():
        res = ScenarioResult(name)
        for seed in seeds:
            res.runs.append(run_once(factory(config), config, session, seed=seed))
        out.append(res)
    return out


def format_table(results: list[ScenarioResult]) -> str:
    head = f"{'scenario':<10}{'runs':>5}{'accuracy':>10}{'ask_rate':>10}{'improve_no_evidence':>21}{'tokens~':>9}"
    rows = [
        f"{r.name:<10}{len(r.runs):>5}{r.accuracy:>10.0%}{r.ask_rate:>10.0%}{r.improve_no_evidence:>21}{r.tokens:>9}"
        for r in results
    ]
    return "\n".join([head, *rows])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--llm", choices=["scripted", "real"], default="scripted")
    p.add_argument("--seeds", type=int, default=3, help="runs per scenario (data seeds 42, 43, ...)")
    args = p.parse_args(argv)
    if args.llm == "real":
        problem = prepare_real_llm_env(ROOT / ".env")
        if problem:
            print(problem, file=sys.stderr)
            return 2
    config = load_domain_config()
    seeds = [42 + i for i in range(max(1, args.seeds))]
    factories: dict[str, Callable[[DomainConfig], LLM]] = (
        dict(SCRIPTED) if args.llm == "scripted" else {"real": lambda _c: AnthropicLLM()}
    )
    with Session(make_engine()) as session:
        try:
            results = evaluate(factories, config, session, seeds=seeds)
        except Exception:
            session.rollback()
            raise
    print(format_table(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
