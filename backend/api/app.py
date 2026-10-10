"""FastAPI + SSE for the dashboard (T-025).

Endpoints: ``POST /runs``, ``POST /runs/{id}/answer``, ``POST /runs/{id}/approval``,
``GET /runs/{id}/events`` (SSE, one message per event of docs/schema/events.json).

The LLM, the tool context (sandbox tables + DB session) and the checkpointer are injected through
``create_app`` so tests run with a scripted LLM and need no API key. The graph is driven by people:
the API only starts it and passes their answers / decisions as ``Command(resume=...)``; it never
decides anything itself. Runs are kept in memory (one process); the graph state lives in the checkpointer.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from backend.agent.demo_llm import llm_from_env
from backend.agent.events import make_event
from backend.agent.graph import build_graph
from backend.agent.llm import LLM, AnthropicLLM
from backend.agent.nodes.act import DecisionError, parse_decision
from backend.agent.nodes.improve import ProposalError
from backend.agent.state import new_state
from backend.db import repo
from backend.db.session import make_engine
from backend.domain_config import DomainConfig, load_domain_config
from backend.sandbox import generate_dataset
from backend.tools.readonly import ToolContext

LLMFactory = Callable[[str], LLM]
CtxFactory = Callable[[str], ToolContext]

WAIT_ANSWER = ("wait_answer", "wait_evidence")  # both are a question to a person answered with POST /answer
WAIT_APPROVAL = ("wait_approval", "wait_rollback", "wait_halt")


class StartRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # when the fix takes effect; Measure compares windows around it. Optional: default = end of the anomaly
    change_time: str | None = Field(default=None, min_length=1)


class AnswerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)


class ApprovalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # what the person was shown: must match the interrupt now waiting, else 409 (a stale or double click)
    proposal_id: str = Field(min_length=1)
    kind: Literal["proposal", "rollback", "halt"]  # halt: a stopped run (proposal_id = the halt id)
    # approved/rejected; revise (kind proposal, needs reason); investigate/finish (kind halt)
    decision: Literal["approved", "rejected", "revise", "investigate", "finish"]
    decided_by: str = Field(min_length=1)
    reason: str = ""


@dataclass
class Run:
    run_id: str
    graph: Any
    cfg: dict[str, Any]
    ctx: ToolContext
    lock: threading.Lock = field(default_factory=threading.Lock)
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    retries: int = 0  # consecutive /retry calls since the last successful step
    retryable: bool = True
    started_at: str = field(default_factory=lambda: _now())
    finished_at: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


AUDIT_DEFAULT_LIMIT = 100
AUDIT_MAX_LIMIT = 500


@cache
def _default_tables():
    return generate_dataset(seed=42).tables


def _default_ctx_factory(run_id: str) -> ToolContext:
    return ToolContext(tables=_default_tables(), session=Session(make_engine()), run_id=run_id)


def _default_llm_factory(run_id: str) -> LLM:
    return AnthropicLLM()  # needs MODEL_REASONING and the API key; tests inject a scripted LLM instead


def _status(run: Run) -> dict[str, Any]:
    """Where the run is, derived from the graph state (not stored separately); a failed run is "error"."""
    if run.error is not None:
        return {
            "run_id": run.run_id, "state": "error", "status": "error", "pending": None, "error": run.error,
            "retryable": run.retryable,
        }
    snap = run.graph.get_state(run.cfg)
    nxt = snap.next[0] if snap.next else None
    pending = None
    if nxt in WAIT_ANSWER:
        pending = {"type": "answer", **_interrupt_value(snap)}
    elif nxt in WAIT_APPROVAL:
        pending = {"type": "approval", **_interrupt_value(snap)}
    state = "finished" if nxt is None else ("waiting" if pending else "running")
    return {
        "run_id": run.run_id,
        "state": state,
        "status": snap.values.get("status", ""),
        "pending": pending,
    }


def _interrupt_value(snap: Any) -> dict[str, Any]:
    for t in snap.tasks:
        for i in t.interrupts:
            return dict(i.value) if isinstance(i.value, dict) else {"value": i.value}
    return {}


def create_app(
    config: DomainConfig | None = None,
    llm_factory: LLMFactory | None = None,
    ctx_factory: CtxFactory | None = None,
    checkpointer: Any | None = None,
) -> FastAPI:
    """Build the app. Every dependency is injectable; the defaults need the real LLM and Postgres."""
    cfg_domain = config or load_domain_config()
    def env_llm_factory(run_id: str) -> LLM:
        # SME_LLM=scripted -> fake LLM (demo/e2e, no key); otherwise the real one
        return llm_from_env(cfg_domain) or _default_llm_factory(run_id)

    make_llm = llm_factory or env_llm_factory
    make_ctx = ctx_factory or _default_ctx_factory
    if checkpointer is None:
        from backend.agent.checkpoint import memory_checkpointer

        checkpointer = memory_checkpointer()  # one saver for all runs; thread_id isolates them
    runs: dict[str, Run] = {}
    app = FastAPI(title="SME CI Agent")
    app.state.runs = runs
    # the dashboard (yarn dev, port 3000) calls this API from the browser
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o for o in os.environ.get("SME_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    def get_run(run_id: str) -> Run:
        run = runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
        return run

    def advance(run: Run, payload: Any, resumed: bool = False) -> None:
        """Run the graph until the next interrupt or the end; refresh the stored events.

        Bad input -> 422, but only when the run is being started (``resumed=False``: e.g. a bad change_time;
        the run is not registered). Once a run is resumed, the caller's input was already checked, so every
        failure (ValueError, DecisionError, ProposalError, LLM 429, outage, bug) stops the run cleanly: rollback
        of the current step, remember the error, emit a ``run_finished`` event with status ``error``.
        ``POST /runs/{id}/retry`` runs the failed step again (at most ``loop.max_retries`` times in a row).
        Decisions of people are committed to audit_log by the node before the next step (H-07).
        """
        run.error = None
        try:
            run.graph.invoke(payload, run.cfg)
            run.ctx.session.commit()
            run.retries = 0
        except (ValueError, DecisionError) as e:
            run.ctx.session.rollback()
            if not resumed and not isinstance(e, ProposalError):  # e.g. missing change_time at start
                raise HTTPException(status_code=422, detail=str(e)) from e
            run.error = f"{type(e).__name__}: {e}"
        except Exception as e:  # noqa: BLE001 - any failure (LLM 429, outage) must stop the run cleanly
            run.ctx.session.rollback()
            run.error = f"{type(e).__name__}: {e}"
        finally:
            run.events = list(run.graph.get_state(run.cfg).values.get("events", []))
            run.retryable = run.retries < cfg_domain.loop.max_retries
            if run.error is None and run.finished_at is None and _status(run)["state"] == "finished":
                run.finished_at = _now()
            if run.error is not None:
                run.events.append(
                    make_event(
                        {"run_id": run.run_id, "domain": cfg_domain.domain},
                        "run_finished",
                        "system",
                        {"status": "error", "error": run.error, "retryable": run.retryable},
                        len(run.events) + 1,
                        cfg_domain.domain,
                    )
                )

    def require_waiting(run: Run, kind: str) -> None:
        st = _status(run)
        pending = st["pending"]
        if pending is None or pending["type"] != kind:
            raise HTTPException(
                status_code=409,
                detail=f"run {run.run_id!r} is not waiting for {kind} (state: {st['state']})",
            )

    @app.post("/runs", status_code=201)
    def start_run(body: StartRun) -> dict[str, Any]:
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        ctx = make_ctx(run_id)
        graph = build_graph(cfg_domain, checkpointer=checkpointer, llm=make_llm(run_id), tool_ctx=ctx, full_loop=True)
        run = Run(run_id=run_id, graph=graph, cfg={"configurable": {"thread_id": run_id}}, ctx=ctx)
        state = new_state(run_id, cfg_domain.domain)
        if body.change_time is not None:
            state["change_time"] = body.change_time
        with run.lock:
            advance(run, state)  # on failure the run is not registered
            runs[run_id] = run
            return _status(run)

    @app.post("/runs/{run_id}/answer")
    def answer(run_id: str, body: AnswerBody) -> dict[str, Any]:
        run = get_run(run_id)
        with run.lock:
            require_waiting(run, "answer")
            advance(run, Command(resume=body.answer), resumed=True)
            return _status(run)

    @app.post("/runs/{run_id}/approval")
    def approval(run_id: str, body: ApprovalBody) -> dict[str, Any]:
        run = get_run(run_id)
        with run.lock:
            require_waiting(run, "approval")
            pending = _status(run)["pending"]
            if body.kind != pending.get("kind") or body.proposal_id != pending.get("proposal_id"):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"run {run_id!r} is now waiting for {pending.get('kind')!r} "
                        f"{pending.get('proposal_id')!r}, not {body.kind!r} {body.proposal_id!r}; reload the run"
                    ),
                )
            try:
                decision = parse_decision(body.model_dump(), cfg_domain)  # reject before resuming: a bad resume would break the run
            except DecisionError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            offered = pending.get("options") or []
            if body.kind == "halt" and offered and decision["decision"] not in offered:
                raise HTTPException(status_code=422, detail=f"this halt only allows {offered}, got {decision['decision']!r}")
            advance(run, Command(resume={**decision, "proposal_id": body.proposal_id, "kind": body.kind}), resumed=True)
            return _status(run)

    @app.post("/runs/{run_id}/retry")
    def retry(run_id: str) -> dict[str, Any]:
        run = get_run(run_id)
        with run.lock:
            if run.error is None:
                raise HTTPException(status_code=409, detail=f"run {run_id!r} has no failed step to retry")
            if run.retries >= cfg_domain.loop.max_retries:
                raise HTTPException(
                    status_code=409,
                    detail=f"run {run_id!r} was retried {run.retries} time(s) in a row (limit {cfg_domain.loop.max_retries}); not retryable",
                )
            run.retries += 1
            advance(run, None, resumed=True)  # continue from the last checkpoint: the failed node runs again
            return _status(run)

    @app.get("/config/approvers")
    def approvers() -> dict[str, Any]:
        return {"approvers": list(cfg_domain.approvers)}

    read_lock = threading.Lock()
    shared_read: dict[str, Session] = {}

    @contextmanager
    def read_db():
        """A session for read-only endpoints (audit, SOP versions). With an injected ctx_factory (tests) reuse its
        session; otherwise open one per request on the default engine and close it."""
        if ctx_factory is not None:
            with read_lock:
                if "s" not in shared_read:
                    shared_read["s"] = ctx_factory("api_read").session
                yield shared_read["s"]
            return
        session = Session(make_engine())
        try:
            yield session
        finally:
            session.close()
            session.get_bind().dispose()

    @app.get("/runs")
    def list_runs() -> dict[str, Any]:
        """Runs held by this app, newest first. In memory only (lost on restart, H-15)."""
        out = []
        for run in reversed(list(runs.values())):
            with run.lock:
                st = _status(run)
                finished = [e for e in run.events if e["type"] == "run_finished"]
                pending = st["pending"]
                out.append(
                    {
                        "run_id": run.run_id,
                        "state": st["state"],
                        "started_at": run.started_at,
                        "finished_at": run.finished_at,
                        "outcome": finished[-1]["payload"].get("status") if finished else None,
                        "pending": (
                            {k: pending.get(k) for k in ("type", "kind", "proposal_id") if k in pending}
                            if pending
                            else None
                        ),
                    }
                )
        return {"runs": out}

    @app.get("/audit")
    def audit(
        run_id: str | None = None,
        limit: int = Query(AUDIT_DEFAULT_LIMIT, ge=1, le=AUDIT_MAX_LIMIT),
    ) -> dict[str, Any]:
        """Read audit_log, newest first (read only)."""
        with read_db() as session:
            rows = repo.recent_actions(session, run_id=run_id, limit=limit)
            return {
                "rows": [
                    {"id": r.id, "ts": r.ts.isoformat(), "run_id": r.run_id, "actor": r.actor, "action": r.action, "params": r.params}
                    for r in rows
                ]
            }

    @app.get("/sop/{sop_id}/versions")
    def sop_versions(sop_id: str) -> dict[str, Any]:
        """The config version plus the versions in sop_versions, oldest first. On the same version number the DB row
        wins (the first DB row is a copy of the config version)."""
        base = [s for s in cfg_domain.sop if s.id == sop_id]
        if not base:
            raise HTTPException(status_code=404, detail=f"sop {sop_id!r} not found")
        found: dict[int, dict[str, Any]] = {
            s.version: {
                "version": s.version, "created_by": "config", "run_id": None, "created_at": None,
                "content": "\n".join(s.steps),
            }
            for s in base
        }
        with read_db() as session:
            for r in repo.list_sop_versions(session, sop_id):
                found[r.version] = {
                    "version": r.version, "created_by": r.created_by, "run_id": r.run_id,
                    "created_at": r.created_at.isoformat(), "content": r.content,
                }
        return {"sop_id": sop_id, "versions": [found[v] for v in sorted(found)]}

    @app.get("/runs/{run_id}")
    def run_status(run_id: str) -> dict[str, Any]:
        return _status(get_run(run_id))

    @app.get("/runs/{run_id}/events")
    async def events(run_id: str, request: Request, follow: bool = False, after: int = 0):
        """SSE. Sends events recorded so far (``id`` = 1-based index; resume with ``Last-Event-ID`` or
        ``after``), then closes when the run is waiting for a person or finished. ``follow=true`` stays
        open until the run finishes."""
        run = get_run(run_id)
        last = request.headers.get("last-event-id")
        sent = int(last) if last and last.isdigit() else after

        async def stream():
            nonlocal sent
            while True:
                for i in range(sent, len(run.events)):
                    ev = run.events[i]
                    yield {"id": str(i + 1), "event": ev["type"], "data": json.dumps(ev)}
                    sent = i + 1
                if not follow or _status(run)["state"] in ("finished", "error"):
                    return
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.2)

        return EventSourceResponse(stream())

    return app
