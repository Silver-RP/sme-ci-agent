"""Write one example file per branch of the loop, for the frontend (docs/schema/examples/run-<branch>.json).

    uv run python scripts/export_fixtures.py [--out DIR]

Each branch starts a run through the real API (FastAPI TestClient, scripted LLM, synthetic seed-42 data) and plays
the person's part with the steps listed in BRANCHES. These are DEMO examples of the request/response/event shapes,
not evidence that the agent is right. Needs Postgres (DATABASE_URL) with migrations applied.

File format: ``{"note", "branch", "description", "steps": [{"request", "body"?, "http", "response", "last_event"}],
"events": [...]}``. ``events`` is the full SSE stream at the end; ``last_event`` is the last event after that step
(where a retryable ``run_finished`` error shows right after it happens; it also stays in ``events``, H-13).
"""

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.agent.demo_llm import (
    demo_improve,
    demo_investigate,
    demo_low_confidence,
    scripted_demo_llm,
)
from backend.agent.llm import LLM, LLMResponse, ScriptedLLM
from backend.api.app import create_app
from backend.db.session import make_engine
from backend.domain_config import DomainConfig, load_domain_config
from backend.sandbox import generate_dataset
from backend.tools.readonly import ToolContext

DEFAULT_OUT = ROOT / "docs" / "schema" / "examples"
WRONG_PARAMETER = "other_parameter_c"  # not linked to the anomaly by the simulator: the KPI stays high
TOO_LATE = "2026-06-29T22:00:00"  # change time with too few KPI points after it


class FailOnce:
    """Scripted LLM whose first call raises (a transient outage); later calls follow the script."""

    def __init__(self, inner: ScriptedLLM) -> None:
        self.inner, self.failed = inner, False

    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[Any]) -> LLMResponse:
        if not self.failed:
            self.failed = True
            raise RuntimeError("529 overloaded (simulated)")
        return self.inner.complete(system, messages, tools)


@cache
def _tables() -> dict[str, Any]:
    return generate_dataset(seed=42).tables


@cache
def _flat_tables() -> dict[str, Any]:
    t = dict(_tables())
    k = t["kpi_log"].copy()
    k["value"] = k.groupby(["machine_id", "kpi"])["value"].transform("mean")  # a flat series: nothing above the limit
    t["kpi_log"] = k
    return t


APPROVE = {"decision": "approved", "decided_by": "alice", "reason": "ok"}


@dataclass
class Branch:
    description: str
    llm: Callable[[DomainConfig], LLM]
    steps: list[tuple[str, Any]]  # ("answer", text) | ("decide", body) | ("retry", None)
    start: dict[str, Any] = field(default_factory=dict)
    tables: Callable[[], dict[str, Any]] = _tables


def _wrong_then_right(cfg: DomainConfig) -> LLM:
    return ScriptedLLM(
        [*demo_investigate(cfg, "sensor calibration drift"), demo_improve(cfg, WRONG_PARAMETER),
         *demo_investigate(cfg), demo_improve(cfg)]
    )


def _wrong_only(cfg: DomainConfig) -> LLM:
    return ScriptedLLM([*demo_investigate(cfg, "sensor calibration drift"), demo_improve(cfg, WRONG_PARAMETER)])


BRANCHES: dict[str, Branch] = {
    "happy": Branch(
        "Unsure first, a person answers, one proposal is approved, the KPI recovers, Learn saves it.",
        lambda cfg: scripted_demo_llm(cfg),
        [("answer", "I have no further information about this."), ("decide", APPROVE)],
    ),
    "rollback": Branch(
        "A wrong fix is approved, Measure fails, a person confirms the rollback, the agent investigates again and the right fix passes.",
        _wrong_then_right,
        [("decide", APPROVE), ("decide", {**APPROVE, "decided_by": "bob", "reason": "KPI did not recover"}), ("decide", APPROVE)],
    ),
    "rollback-declined": Branch(
        "The fix failed but the person declines the rollback: the run stops; the applied SOP stays in force.",
        _wrong_only,
        [("decide", APPROVE), ("decide", {"decision": "rejected", "decided_by": "alice", "reason": "keep it for another shift"})],
    ),
    "insufficient-evidence": Branch(
        "The change is too recent to measure: Measure has too few samples and asks a person (a pending answer).",
        lambda cfg: scripted_demo_llm(cfg, ask_first=False),
        [("decide", APPROVE)],
        start={"change_time": TOO_LATE},
    ),
    "revise": Branch(
        "A person sends the first proposal back with information (revise): Investigate runs again, the second proposal is approved.",
        lambda cfg: scripted_demo_llm(cfg, ask_first=False, then=("investigate",)),
        [("decide", {"decision": "revise", "decided_by": "alice", "reason": "M02 was serviced on 3/18, check the calibration"}),
         ("decide", APPROVE)],
    ),
    "halt-max-questions": Branch(
        "The agent stays unsure after the allowed number of questions and stops for a person (halt).",
        lambda cfg: ScriptedLLM([demo_low_confidence(cfg)] * 3),
        [("answer", "not sure"), ("answer", "still not sure")],
    ),
    "error-retry": Branch(
        "The LLM fails on the first call: the run ends in a retryable error; Retry continues from the checkpoint.",
        lambda cfg: FailOnce(scripted_demo_llm(cfg, ask_first=False)),  # type: ignore[return-value]
        [("retry", None), ("decide", APPROVE)],
    ),
    "no-anomaly": Branch(
        "Detect finds nothing above the limit: the run finishes with no_anomaly and no LLM call.",
        lambda cfg: ScriptedLLM([]),
        [],
        tables=_flat_tables,
    ),
}


def _read_events(client: TestClient, run_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with client.stream("GET", f"/runs/{run_id}/events") as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                out.append(json.loads(line.split(":", 1)[1]))
    return out


def run_branch(name: str, branch: Branch, config: DomainConfig, session: Session) -> dict[str, Any]:
    tables = branch.tables()
    app = create_app(
        config,
        llm_factory=lambda rid: branch.llm(config),
        ctx_factory=lambda rid: ToolContext(tables=tables, session=session, run_id=rid),
    )
    client = TestClient(app)
    steps: list[dict[str, Any]] = []

    def record(request: str, body: Any, resp: Any, run_id: str | None) -> dict[str, Any]:
        entry: dict[str, Any] = {"request": request}
        if body is not None:
            entry["body"] = body
        entry.update(http=resp.status_code, response=resp.json())
        rid = run_id or entry["response"].get("run_id")
        events = _read_events(client, rid) if rid else []
        entry["last_event"] = events[-1] if events else None
        steps.append(entry)
        return entry

    first = client.post("/runs", json=branch.start)
    if first.status_code != 201:
        raise RuntimeError(f"{name}: POST /runs -> {first.status_code} {first.text}")
    run_id = first.json()["run_id"]
    record("POST /runs", branch.start, first, run_id)
    for kind, arg in branch.steps:
        status = client.get(f"/runs/{run_id}").json()
        if kind == "answer":
            resp = client.post(f"/runs/{run_id}/answer", json={"answer": arg})
            record("POST /runs/{run_id}/answer", {"answer": arg}, resp, run_id)
        elif kind == "decide":
            pending = status["pending"]
            body = {"proposal_id": pending["proposal_id"], "kind": pending["kind"], **arg}
            resp = client.post(f"/runs/{run_id}/approval", json=body)
            record("POST /runs/{run_id}/approval", body, resp, run_id)
        else:
            resp = client.post(f"/runs/{run_id}/retry")
            record("POST /runs/{run_id}/retry", None, resp, run_id)
        if resp.status_code != 200:
            raise RuntimeError(f"{name}: {kind} -> {resp.status_code} {resp.text}")
    session.commit()
    return {
        "note": "Generated by scripts/export_fixtures.py (scripted LLM, synthetic seed-42 data); see docs/schema/payloads.md",
        "branch": name,
        "description": branch.description,
        "steps": steps,
        "events": _read_events(client, run_id),
    }


def export_all(out_dir: Path, session: Session, config: DomainConfig | None = None) -> list[Path]:
    config = config or load_domain_config()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, branch in BRANCHES.items():
        data = run_branch(name, branch, config, session)
        path = out_dir / f"run-{name}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="directory for run-<branch>.json")
    args = p.parse_args(argv)
    with Session(make_engine()) as session:
        try:
            written = export_all(args.out, session)
        except Exception:
            session.rollback()
            raise
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
