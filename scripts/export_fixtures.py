"""Write one example file per branch of the loop, for the frontend (docs/schema/examples/run-<branch>.json).

    uv run python scripts/export_fixtures.py [--out DIR] [--dashboard-dir DIR] [--use-database]

Each branch starts a run through the real API (FastAPI TestClient, scripted LLM, synthetic seed-42 data) and plays
the person's part with the steps listed in BRANCHES. These are DEMO examples of the request/response/event shapes,
not evidence that the agent is right. Needs a Postgres server (DATABASE_URL): it works on a fresh database
`<name>_fixtures_demo` and normalizes ids, SOP versions and event times, so the output does not depend on the dev
database (H-66). With no --out it also copies the files to dashboard/fixtures/examples/.

File format: ``{"note", "branch", "description", "steps": [{"request", "body"?, "http", "response", "last_event"}],
"events": [...]}``. ``events`` is the full SSE stream at the end; ``last_event`` is the last event after that step
(where a retryable ``run_finished`` error shows right after it happens; it also stays in ``events``, H-13).
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import types
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.agent.demo_llm import (
    demo_improve,
    demo_investigate,
    demo_low_confidence,
    scripted_demo_llm,
)
from backend.agent.llm import LLM, LLMResponse, ScriptedLLM
from backend.api import app as app_module
from backend.api.app import create_app
from backend.db.config import get_database_url
from backend.db.session import make_engine
from backend.domain_config import DomainConfig, load_domain_config
from backend.sandbox import generate_dataset
from backend.tools.readonly import ToolContext

DEFAULT_OUT = ROOT / "docs" / "schema" / "examples"
DASHBOARD_OUT = ROOT / "dashboard" / "fixtures" / "examples"  # byte-for-byte copy of DEFAULT_OUT (H-66)
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
    source_may_grow: bool = False  # a live source: Measure asks to wait and measures again (not the sandbox default)


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
        source_may_grow=True,
    ),
    "insufficient-evidence-final": Branch(
        "The change is too recent and the source cannot grow (sandbox): Measure stops once with a halt "
        "(insufficient_evidence, options [finish]); the person finishes the run (closed).",
        lambda cfg: scripted_demo_llm(cfg, ask_first=False),
        [("decide", APPROVE), ("decide", {"decision": "finish", "decided_by": "alice", "reason": "no more data"})],
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


VERSION_KEYS = {"version", "base_version", "previous_version", "sop_version", "current_version",
                "restored_from_version", "failed_version"}
_RUN_ID = re.compile(r"run_[0-9a-f]{8}")
_ID12 = re.compile(r'"([0-9a-f]{12})"')
_VERSION_IN_TEXT = re.compile(r"(phiên bản )(\d+)")
_LEARNING_ID = re.compile(r'"learning_id": (\d+)')
_HASH64 =re.compile(r'"([0-9a-f]{64})"')


def _digest(*parts: str, n: int) -> str:
    return hashlib.sha256(":".join(parts).encode()).hexdigest()[:n]


def _is_version(key: Any, value: Any) -> bool:
    return key in VERSION_KEYS and isinstance(value, int) and not isinstance(value, bool)


def _walk_versions(obj: Any, found: set[int]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _is_version(k, v):
                found.add(v)
            else:
                _walk_versions(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk_versions(v, found)


def _map_versions(obj: Any, mapping: dict[int, int]) -> Any:
    if isinstance(obj, dict):
        return {k: mapping[v] if _is_version(k, v) else _map_versions(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_map_versions(v, mapping) for v in obj]
    return obj


def _map_ts(obj: Any, ts_of: dict[str, str]) -> Any:
    if isinstance(obj, dict):
        out = {k: _map_ts(v, ts_of) for k, v in obj.items()}
        if "event_id" in out and "ts" in out and out["event_id"] in ts_of:
            out["ts"] = ts_of[out["event_id"]]
        return out
    if isinstance(obj, list):
        return [_map_ts(v, ts_of) for v in obj]
    return obj


def normalize(data: dict[str, Any], name: str) -> dict[str, Any]:
    """Make an export independent of the database and the clock (H-66): the same branch gives the same bytes.

    Run id, proposal ids and hashes become digests of the branch name and their order of appearance; SOP
    versions become 1..n by rank (the DB may already hold any number of versions); the time of an event becomes
    2026-01-01T00:00:00Z + its position in the stream. Times of the data are untouched."""
    versions: set[int] = set()
    _walk_versions(data, versions)
    vmap = {v: i for i, v in enumerate(sorted(versions), start=1)}
    data = _map_versions(data, vmap)
    text = json.dumps(data, ensure_ascii=False)
    # the same numbers inside sentences ("Hoàn tác SOP ... về phiên bản 11")
    text = _VERSION_IN_TEXT.sub(lambda m: m.group(1) + str(vmap.get(int(m.group(2)), m.group(2))), text)
    lids = sorted({int(x) for x in _LEARNING_ID.findall(text)})
    text = _LEARNING_ID.sub(lambda m: f'"learning_id": {lids.index(int(m.group(1))) + 1}', text)
    for i, rid in enumerate(dict.fromkeys(_RUN_ID.findall(text))):
        text = text.replace(rid, "run_" + _digest(name, "run", str(i), n=8))
    for pattern, n, tag in ((_ID12, 12, "id"), (_HASH64, 64, "hash")):
        found = list(dict.fromkeys(pattern.findall(text)))
        mapping = {old: _digest(name, tag, str(i), n=n) for i, old in enumerate(found)}
        text = pattern.sub(lambda m, mp=mapping: f'"{mp[m.group(1)]}"', text)
    data = json.loads(text)
    # an event's time is its position in the final stream (steps repeat events: same event_id, same time)
    ts_of = {e["event_id"]: f"2026-01-01T{i // 3600:02d}:{i % 3600 // 60:02d}:{i % 60:02d}Z"
             for i, e in enumerate(data["events"])}
    return _map_ts(data, ts_of)


def _read_events(client: TestClient, run_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with client.stream("GET", f"/runs/{run_id}/events") as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                out.append(json.loads(line.split(":", 1)[1]))
    return out


def run_branch(name: str, branch: Branch, config: DomainConfig, session: Session) -> dict[str, Any]:
    # The data after a change is a function of the run id: a fixed id per branch makes the numbers repeatable.
    fixed = types.SimpleNamespace(uuid4=lambda: uuid.UUID(hashlib.sha256(f"fixture:{name}".encode()).hexdigest()[:32]))
    with mock.patch.object(app_module, "uuid", fixed):
        return _run_branch(name, branch, config, session)


def _run_branch(name: str, branch: Branch, config: DomainConfig, session: Session) -> dict[str, Any]:
    tables = branch.tables()
    if branch.source_may_grow:
        config = config.model_copy(update={"measure": config.measure.model_copy(update={"source_may_grow": True})})
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
            qid = status["pending"]["question_id"]
            resp = client.post(f"/runs/{run_id}/answer", json={"answer": arg, "question_id": qid})
            record("POST /runs/{run_id}/answer", {"answer": arg, "question_id": qid}, resp, run_id)
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
    return normalize(
        {
            "note": "Generated by scripts/export_fixtures.py (scripted LLM, synthetic seed-42 data); see docs/schema/payloads.md",
            "branch": name,
            "description": branch.description,
            "steps": steps,
            "events": _read_events(client, run_id),
        },
        name,
    )


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


def temp_database(base_url: str) -> str:
    """A fresh database `<name>_fixtures_demo` (dropped and created on each call, migrations applied)."""
    from scripts.fresh_db import drop_and_create

    u = make_url(base_url)
    name = u.database if u.database.endswith("_fixtures_demo") else f"{u.database}_fixtures_demo"
    url = u.set(database=name).render_as_string(hide_password=False)
    drop_and_create(url)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend/db/migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    return url


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="directory for run-<branch>.json")
    p.add_argument("--dashboard-dir", type=Path, default=None,
                   help=f"also copy the files here (default {DASHBOARD_OUT} when --out is the default)")
    p.add_argument("--use-database", action="store_true",
                   help="run on DATABASE_URL as it is instead of a fresh temporary database")
    args = p.parse_args(argv)
    os.environ["SME_SKIP_HANDLED"] = "0"  # every branch takes the first anomaly, whatever lessons exist
    url = get_database_url() if args.use_database else temp_database(get_database_url())
    engine = make_engine(url)
    with Session(engine) as session:
        try:
            written = export_all(args.out, session)
        except Exception:
            session.rollback()
            raise
    engine.dispose()
    copy_to = args.dashboard_dir or (DASHBOARD_OUT if args.out == DEFAULT_OUT else None)
    if copy_to:
        copy_to.mkdir(parents=True, exist_ok=True)
        for path in written:
            shutil.copyfile(path, copy_to / path.name)
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
