"""Run one full loop (scenario 1) through the agent graph from the command line.

    uv run python scripts/run_scenario.py              # scripted (fake) LLM, no key needed
    uv run python scripts/run_scenario.py --llm real   # AnthropicLLM; you set the key and MODEL_REASONING in .env

Branches (the demo person takes them on request; every one is a human decision, never the agent's):
    --on-proposal revise|reject   send the FIRST proposal back (revise -> Investigate with feedback, reject -> Improve)
    --on-halt investigate|finish  what to do when the run stops at a limit (default: finish)

The graph pauses for people (a question, an approval). This script plays that person only because you
ask for a demo run: it answers with --answer and approves as --approver (a name from the config
allow-list, default: the first one). Needs Postgres (DATABASE_URL) with migrations applied.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy.orm import Session

from backend.agent.demo_llm import scripted_demo_llm
from backend.agent.graph import build_graph
from backend.agent.llm import LLM, AnthropicLLM
from backend.agent.state import new_state
from backend.db.session import make_engine
from backend.domain_config import DomainConfig, load_domain_config
from backend.sandbox import generate_dataset
from backend.tools.readonly import ToolContext

SEND_BACK_SCRIPT = {"approve": (), "revise": ("investigate",), "reject": ("improve",)}
MAX_STEPS = 20  # safety bound on pause/resume rounds


def run_scenario(
    llm: LLM,
    config: DomainConfig,
    session: Session,
    *,
    seed: int = 42,
    answer: str = "The setpoint on M02 was changed by the night shift",
    approver: str | None = None,
    change_time: str | None = None,
    on_proposal: str = "approve",
    on_halt: str = "finish",
) -> list[dict]:
    """Drive the graph to the end; returns all events. Raises RuntimeError if it does not finish."""
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    ctx = ToolContext(tables=generate_dataset(seed=seed).tables, session=session, run_id=run_id)
    graph = build_graph(config, checkpointer=InMemorySaver(), llm=llm, tool_ctx=ctx, full_loop=True)
    cfg = {"configurable": {"thread_id": run_id}}
    state = new_state(run_id, config.domain)
    if change_time:
        state["change_time"] = change_time
    payload: object = state
    who = approver or config.approvers[0]
    first_proposal = True
    for _ in range(MAX_STEPS):
        graph.invoke(payload, cfg)
        session.commit()
        snap = graph.get_state(cfg)
        if not snap.next:
            return list(snap.values.get("events", []))
        if snap.next[0] == "wait_answer":
            payload = Command(resume=answer)
        elif snap.next[0] == "wait_halt":
            payload = Command(resume={"decision": on_halt, "decided_by": who, "reason": "demo run"})
        elif snap.next[0] == "wait_approval" and first_proposal and on_proposal != "approve":
            first_proposal = False
            decision = {"revise": "revise", "reject": "rejected"}[on_proposal]
            payload = Command(resume={"decision": decision, "decided_by": who, "reason": "demo run: please look again"})
        elif snap.next[0] == "wait_rollback":
            # the fix did not bring the KPI back: the demo person declines the rollback
            payload = Command(resume={"decision": "rejected", "decided_by": who, "reason": "demo run: keep"})
        else:
            payload = Command(resume={"decision": "approved", "decided_by": who, "reason": "demo run"})
    raise RuntimeError(f"run did not finish within {MAX_STEPS} steps")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--llm", choices=["scripted", "real"], default="scripted")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--approver", default=None, help="name from the config allow-list (default: first)")
    p.add_argument("--answer", default="The setpoint on M02 was changed by the night shift")
    p.add_argument("--on-proposal", choices=["approve", "revise", "reject"], default="approve")
    p.add_argument("--on-halt", choices=["investigate", "finish"], default="finish")
    args = p.parse_args(argv)

    config = load_domain_config()
    llm: LLM = scripted_demo_llm(config, then=SEND_BACK_SCRIPT[args.on_proposal]) if args.llm == "scripted" else AnthropicLLM()
    with Session(make_engine()) as session:
        try:
            events = run_scenario(llm, config, session, seed=args.seed, answer=args.answer, approver=args.approver,
                                 on_proposal=args.on_proposal, on_halt=args.on_halt)
        except Exception:
            session.rollback()
            raise
    for e in events:
        print(f"{e['event_id']}  {e['agent']:<12} {e['type']}")
    counts = Counter(e["type"] for e in events)
    print(f"\n{len(events)} events; " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    last = events[-1]["type"] if events else None
    if last != "run_finished":
        print(f"run did not end with run_finished (last: {last})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
