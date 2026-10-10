"""R10c/dev-07 (A6): invariants of the human-in-the-loop rules under random API call sequences.

A seeded generator builds many sequences of API calls on runs with a fake LLM: answers, approvals, rejections,
revisions, halts, retries, calls in the wrong order, stale ids and approvers that are not allowed (agent, llm, ...).
After EVERY call the invariants are checked (`check_invariants`). The test prints how many sequences ran, how many
different branches they went through and how many calls were refused with the right code (409/422).
The checker is tested against hand-made bad data too (a test that cannot fail proves nothing).
"""

import random
import re
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.agent.demo_llm import DemoLLM
from backend.api.app import create_app
from backend.db.models import AuditLog, SopVersion
from backend.domain_config import load_domain_config
from backend.sandbox.injector import generate_dataset
from backend.tools.readonly import ToolContext
from tests.test_api import sse_events
from tests.test_api_limits_r9 import LATE
from tests.test_engine_pool_r10c import own_db_url  # noqa: F401 - fixture: a private migrated DB

CFG = load_domain_config()
ROOT = Path(__file__).resolve().parents[1]
N_SEQUENCES = 60
STEPS = 22
BASE_SEED = 20261010
NOT_PEOPLE = {"agent", "llm", "claude", "system", "assistant", "ai", "bot", ""}
BAD_APPROVERS = ["agent", "llm", "claude", "system", "Mallory", "   ", "alice2"]
NEEDS_VERDICT = ("sop_applied", "rollback_done")


class FlakyDemo:
    """DemoLLM that raises once on call number ``fail_at`` (a transient 429), then works."""

    def __init__(self, inner, fail_at):
        self.inner, self.fail_at, self.n = inner, fail_at, 0

    def complete(self, system, messages, tools):
        self.n += 1
        if self.n == self.fail_at:
            raise RuntimeError("429 overloaded")
        return self.inner.complete(system, messages, tools)


# ---- the invariants (pure: they read what the API and the DB show) ----


def check_events(events, approvers=tuple(CFG.approvers)):
    """Rules visible in the event list of one run. Returns the violations (empty = fine)."""
    bad = []
    ids = [e["event_id"] for e in events]
    if len(ids) != len(set(ids)):
        bad.append("duplicate event_id")
    allowed = set(approvers)
    approved = None  # the last human verdict for the thing being applied: "proposal" / "rollback" / None
    applied_since_proposal = False
    for e in events:
        t, p = e["type"], e["payload"]
        if t == "approval_decided" and p.get("decision") != "sop_conflict":
            if p.get("decided_by") not in allowed:
                bad.append(f"decision by {p.get('decided_by')!r}, not an approver")
            approved = p["kind"] if p.get("decision") == "approved" and p["kind"] in ("proposal", "rollback") else None
        elif t in NEEDS_VERDICT:
            want = "proposal" if t == "sop_applied" else "rollback"
            if approved != want:
                bad.append(f"{t} without an approved {want}")
            approved = None
            if t == "sop_applied":
                applied_since_proposal = True
        elif t == "proposal_created" or (t == "question_asked" and p.get("kind") == "halt"):
            approved = None
            applied_since_proposal = False
        elif t == "learning_saved" and not applied_since_proposal:
            bad.append("learning_saved from an SOP that was not applied for the current proposal (stale applied)")
        if p.get("approved_by") is not None and p["approved_by"] not in allowed:
            bad.append(f"{t} approved_by {p['approved_by']!r}")
    return bad


def check_audit(events, audit, approvers=tuple(CFG.approvers)):
    """One audit_log row per decision of a person; actors are people from the allow-list."""
    bad = []
    allowed = set(approvers)
    by_action = {}
    for a in audit:
        by_action.setdefault(a.action, []).append(a)
    for action in ("approval_decided", "halt_decided"):
        for a in by_action.get(action, []):
            if a.actor not in allowed:
                bad.append(f"audit {action} by {a.actor!r}")
    for a in by_action.get("answer_received", []):
        if a.actor != "human":  # never an agent / llm / system name
            bad.append(f"answer_received by {a.actor!r}")
    decided = [e for e in events if e["type"] == "approval_decided" and e["payload"].get("decision") != "sop_conflict"]
    want = {
        "approval_decided": sum(1 for e in decided if e["payload"]["kind"] in ("proposal", "rollback")),
        "halt_decided": sum(1 for e in decided if e["payload"]["kind"] == "halt"),
        "answer_received": sum(1 for e in events if e["type"] == "answer_received"),
    }
    for action, n in want.items():
        got = len(by_action.get(action, []))
        if got != n:
            bad.append(f"{got} audit rows for {n} {action}")
    return bad


def check_versions(rows, prev, approvers=tuple(CFG.approvers)):
    """sop_versions only grow: old rows keep their content, versions are 1..n per SOP, authors are people."""
    bad = []
    now = {(r.sop_id, r.version): r.content for r in rows}
    for key, content in prev.items():
        if key not in now:
            bad.append(f"sop version {key} disappeared")
        elif now[key] != content:
            bad.append(f"sop version {key} was overwritten")
    for sop_id in {k[0] for k in now}:
        vs = sorted(v for s, v in now if s == sop_id)
        if vs != list(range(vs[0], vs[0] + len(vs))):
            bad.append(f"sop {sop_id} versions not contiguous: {vs}")
    return bad


def tables_hash(tables):
    return {k: int(pd.util.hash_pandas_object(v, index=True).sum()) for k, v in tables.items()}


# ---- the sequence generator ----


class Harness:
    def __init__(self, db_session, tables, rng):
        self.db, self.tables, self.rng = db_session, tables, rng
        self.rejected = 0  # calls refused with 409/422
        self.out_of_order = 0  # of those: asked in a state that cannot take them
        self.branches = set()
        self.trace = []
        self.prev_versions = {}
        self.violations = []

    def build(self, ask_first, rollback, fail_at):
        def llm_factory(run_id):
            llm = DemoLLM(CFG, ask_first=ask_first, rollback=rollback)
            return FlakyDemo(llm, fail_at) if fail_at else llm

        def ctx_factory(run_id):
            return ToolContext(tables=self.tables, session=self.db, run_id=run_id)

        self.client = TestClient(create_app(CFG, llm_factory=llm_factory, ctx_factory=ctx_factory))

    def audit(self, rid):
        return list(self.db.scalars(select(AuditLog).where(AuditLog.run_id == rid).order_by(AuditLog.id)))

    def versions(self):
        return list(self.db.scalars(select(SopVersion).order_by(SopVersion.id)))

    def counts(self, rid):
        return (len(self.audit(rid)), len(self.versions()), len(sse_events(self.client, rid)))

    def post(self, rid, path, body=None):
        return self.client.post(f"/runs/{rid}/{path}", json=body) if body is not None else self.client.post(f"/runs/{rid}/{path}")

    def step(self, rid, name, send, in_order):
        """Do one call, check the code and the invariants. ``in_order``: the call fits the state of the run."""
        before = self.counts(rid)
        v_before = {(r.sop_id, r.version) for r in self.versions()}
        r = send()
        self.trace.append((name, r.status_code))
        assert r.status_code in (200, 409, 422), f"{name}: unexpected {r.status_code} {r.text}"
        if r.status_code in (409, 422):
            self.rejected += 1
            self.out_of_order += 0 if in_order else 1
            if self.counts(rid) != before:
                self.violations.append(f"{name}: refused call (HTTP {r.status_code}) changed audit/sop/events")
        elif not in_order:
            self.violations.append(f"{name}: a call that does not fit the state got 200")
        events = sse_events(self.client, rid)
        self.violations += [f"{name}: {v}" for v in check_events([m["data"] for m in events])]
        self.violations += [f"{name}: {v}" for v in check_audit([m["data"] for m in events], self.audit(rid))]
        rows = self.versions()
        self.violations += [f"{name}: {v}" for v in check_versions(rows, self.prev_versions)]
        new = [x for x in rows if (x.sop_id, x.version) not in v_before]
        if new and not any(m["data"]["type"] in NEEDS_VERDICT for m in events[before[2] :]):
            self.violations.append(f"{name}: sop version written without sop_applied/rollback_done")
        for x in new:
            if x.created_by not in CFG.approvers and not (x.version == 1 and x.created_by == "config"):  # v1 = YAML seed
                self.violations.append(f"{name}: sop version by {x.created_by!r}")
        self.prev_versions = {(x.sop_id, x.version): x.content for x in rows}
        for m in events:
            d = m["data"]
            self.branches.add(d["type"] + (":" + str(d["payload"].get("decision")) if d["type"] == "approval_decided" else ""))
            if d["type"] in ("question_asked", "run_finished") and d["payload"].get("reason"):
                self.branches.add(d["type"] + ":" + d["payload"]["reason"])
            if d["type"] == "run_finished" and d["payload"].get("status") == "error":
                self.branches.add("error")
        return r

    def status(self, rid):
        return self.client.get(f"/runs/{rid}").json()

    def run_sequence(self):
        rng = self.rng
        self.build(rng.random() < 0.6, rng.random() < 0.5, rng.choice([0, 0, 2, 3, 5, 7]))
        if rng.random() < 0.15:  # a start that is refused leaves no run behind
            assert self.client.post("/runs", json={"change_time": ""}).status_code == 422
            self.rejected += 1
        change = rng.choice([None, None, "2026-03-20", LATE])
        r = self.client.post("/runs", json={} if change is None else {"change_time": change})
        assert r.status_code == 201, r.text
        rid = r.json()["run_id"]
        for _ in range(STEPS):
            self.one_call(rid)
        return rid

    def one_call(self, rid):
        rng = self.rng
        st = self.status(rid)
        p = st["pending"] or {}
        kind = p.get("type")
        who = rng.choice(CFG.approvers)
        pid, pkind = p.get("proposal_id", "none"), p.get("kind", "proposal")
        ok = {"proposal_id": pid, "kind": pkind, "decided_by": who}
        choice = rng.random()
        if choice < 0.62:  # in order: what the run is waiting for
            if st["state"] == "error":
                return self.step(rid, "retry", lambda: self.post(rid, "retry"), st.get("retryable", True))
            if kind == "answer":
                body = {"answer": rng.choice(["Setpoint was changed on M02", "no idea"])}
                if rng.random() < 0.5:
                    body["question_id"] = p.get("question_id") or "none"
                return self.step(rid, "answer", lambda: self.post(rid, "answer", body), True)
            if kind == "approval":
                options = p.get("options") or []
                if pkind == "halt":
                    d = rng.choice(options or ["investigate", "finish"])
                    body = {**ok, "decision": d, "reason": "continue"}
                elif pkind == "rollback":
                    body = {**ok, "decision": rng.choice(["approved", "approved", "rejected"]), "reason": "r"}
                else:
                    d = rng.choice(["approved", "approved", "approved", "rejected", "revise"])
                    body = {**ok, "decision": d, "reason": "check the sensor too" if d != "approved" else ""}
                return self.step(rid, f"approval:{pkind}:{body['decision']}", lambda: self.post(rid, "approval", body), True)
            # finished: everything below is out of order
        wrong = rng.choice(["bad_approver", "bad_approver", "wrong_kind", "stale_id", "answer", "empty_answer", "stale_q",
                            "retry", "bad_decision", "halt_option", "empty_reason_revise"])
        if wrong == "bad_approver":
            who = rng.choice(BAD_APPROVERS)
            body = {"proposal_id": pid, "kind": pkind, "decided_by": who, "decision": "approved"}
            return self.step(rid, "approval:bad_approver", lambda: self.post(rid, "approval", body), False)
        if wrong == "wrong_kind":
            other = rng.choice([k for k in ("proposal", "rollback", "halt") if k != pkind])
            body = {**ok, "kind": other, "decision": "approved" if other != "halt" else "finish"}
            return self.step(rid, "approval:wrong_kind", lambda: self.post(rid, "approval", body), False)
        if wrong == "stale_id":
            body = {**ok, "proposal_id": "prop_stale", "decision": "approved"}
            return self.step(rid, "approval:stale_id", lambda: self.post(rid, "approval", body), False)
        if wrong == "answer":
            return self.step(rid, "answer:out_of_order", lambda: self.post(rid, "answer", {"answer": "late answer"}), kind == "answer")
        if wrong == "empty_answer":
            return self.step(rid, "answer:empty", lambda: self.post(rid, "answer", {"answer": ""}), False)
        if wrong == "stale_q":
            body = {"answer": "x", "question_id": "q_stale"}
            return self.step(rid, "answer:stale_question", lambda: self.post(rid, "answer", body), False)
        if wrong == "retry":
            return self.step(rid, "retry", lambda: self.post(rid, "retry"), st["state"] == "error" and st.get("retryable", True))
        if wrong == "bad_decision":
            body = {**ok, "decision": "finish" if pkind != "halt" else "approved"}
            return self.step(rid, "approval:bad_decision", lambda: self.post(rid, "approval", body), False)
        if wrong == "halt_option":
            body = {**ok, "decision": "investigate"}  # not offered after the last rollback, or not a halt at all
            return self.step(rid, "approval:halt_option", lambda: self.post(rid, "approval", body), pkind == "halt" and "investigate" in (p.get("options") or []) and kind == "approval")
        body = {**ok, "decision": "revise", "reason": "  "}
        return self.step(rid, "approval:revise_no_reason", lambda: self.post(rid, "approval", body), False)


# ---- tests ----


@pytest.mark.xfail(
    strict=True,
    reason="H-39 (llm.py NO_EFFORT_MODEL_PREFIXES) is closed in R10b2/dev-07; strict: this turns red when it is "
    "fixed, so remove the mark then",
)
def test_no_model_name_in_backend():
    hits = [str(f) for f in (ROOT / "backend").rglob("*.py") if re.search(r"claude-", f.read_text(encoding="utf-8"))]
    assert hits == [], f"model names must come from .env, found in {hits}"


def test_random_sequences_keep_every_invariant(db_session, capsys):
    tables = generate_dataset(seed=42).tables
    before = tables_hash(tables)
    sequences, all_branches, rejected, out_of_order, traces = 0, set(), 0, 0, set()
    violations = []
    for i in range(N_SEQUENCES):
        h = Harness(db_session, tables, random.Random(BASE_SEED + i))
        rid = h.run_sequence()
        sequences += 1
        all_branches |= h.branches
        rejected += h.rejected
        out_of_order += h.out_of_order
        traces.add(tuple(h.trace))
        violations += [f"seed {BASE_SEED + i} run {rid}: {v}" for v in h.violations]
        assert tables_hash(tables) == before, f"source tables changed (seed {BASE_SEED + i})"
    with capsys.disabled():
        print(
            f"\n[A6] sequences={sequences} distinct_traces={len(traces)} branches={len(all_branches)} "
            f"refused_409_422={rejected} out_of_order_refused={out_of_order} violations={len(violations)}"
        )
        print(f"[A6] branches: {sorted(all_branches)}")
    assert violations == [], "\n".join(violations[:10])
    assert sequences >= 50 and len(traces) >= 50
    assert len(all_branches) >= 5
    assert out_of_order >= 50, "the generator must send calls in the wrong order, not only the happy path"
    assert rejected >= out_of_order
    for needed in ("learning_saved", "rollback_done", "approval_decided:rejected", "approval_decided:revise", "error"):
        assert needed in all_branches, f"the sequences never reached {needed}"
    assert any(b.startswith("question_asked:") for b in all_branches)


def test_same_seed_gives_the_same_sequence(db_session):
    tables = generate_dataset(seed=42).tables
    traces = []
    for _ in range(2):
        h = Harness(db_session, tables, random.Random(BASE_SEED))
        h.run_sequence()
        traces.append(h.trace)
    assert traces[0] == traces[1] and len(traces[0]) == STEPS


# ---- the checker must be able to fail ----


def ev(i, t, **payload):
    return {"event_id": f"e{i}", "type": t, "payload": payload}


def test_checker_catches_apply_without_approval():
    events = [ev(1, "proposal_created"), ev(2, "sop_applied")]
    assert any("without an approved" in v for v in check_events(events))
    events = [ev(1, "proposal_created"), ev(2, "approval_decided", kind="proposal", decision="rejected", decided_by="alice"),
              ev(3, "sop_applied")]
    assert any("without an approved" in v for v in check_events(events))
    events = [ev(1, "proposal_created"), ev(2, "approval_decided", kind="proposal", decision="approved", decided_by="alice"),
              ev(3, "rollback_done")]
    assert any("without an approved rollback" in v for v in check_events(events))


@pytest.mark.parametrize("who", ["agent", "llm", "claude", "system", "mallory"])
def test_checker_catches_decision_by_non_person(who):
    events = [ev(1, "approval_decided", kind="proposal", decision="approved", decided_by=who), ev(2, "sop_applied")]
    assert any("not an approver" in v for v in check_events(events))


def test_checker_catches_duplicate_event_id_and_stale_learning():
    dup = [ev(1, "proposal_created"), {**ev(1, "proposal_created")}]
    assert "duplicate event_id" in check_events(dup)
    stale = [ev(1, "proposal_created"), ev(2, "learning_saved")]
    assert any("stale applied" in v for v in check_events(stale))


def test_checker_catches_missing_or_extra_audit_rows():
    class Row:
        def __init__(self, action, actor="alice"):
            self.action, self.actor = action, actor

    events = [ev(1, "approval_decided", kind="proposal", decision="approved", decided_by="alice"),
              ev(2, "answer_received")]
    assert check_audit(events, [Row("approval_decided"), Row("answer_received", "human")]) == []
    assert check_audit(events, [Row("answer_received", "human")])  # decision without a row
    assert check_audit(events, [Row("approval_decided"), Row("approval_decided"), Row("answer_received", "human")])
    assert check_audit(events, [Row("approval_decided", "agent"), Row("answer_received", "human")])
    assert check_audit(events, [Row("approval_decided"), Row("answer_received", "claude")])
    assert check_audit(events, [Row("approval_decided"), Row("answer_received", "human"), Row("answer_received", "human")])


def test_checker_catches_overwritten_or_missing_sop_version():
    class V:
        def __init__(self, v, c):
            self.sop_id, self.version, self.content = "s", v, c

    prev = {("s", 1): "a", ("s", 2): "b"}
    assert check_versions([V(1, "a"), V(2, "b"), V(3, "c")], prev) == []
    assert check_versions([V(1, "a"), V(2, "CHANGED")], prev)
    assert check_versions([V(1, "a")], prev)
    assert check_versions([V(1, "a"), V(2, "b"), V(4, "d")], prev)


# ---- cases left open by earlier tasks (non-blocking notes of dev-03 and dev-06, H-37 of dev-01) ----


def _decide(h, rid, body):
    p = h.status(rid)["pending"]
    r = h.client.post(f"/runs/{rid}/approval", json={"proposal_id": p["proposal_id"], "kind": p["kind"], **body})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("fail_at", [2, 3, 4, 5])
def test_retry_after_an_answer_keeps_one_answer_row(db_session, fail_at):
    """The LLM fails in a step after the person answered; /retry must not write the answer a second time."""
    h = Harness(db_session, generate_dataset(seed=42).tables, random.Random(1))
    h.build(ask_first=True, rollback=False, fail_at=fail_at)
    rid = h.client.post("/runs", json={}).json()["run_id"]
    st = h.status(rid)
    if st["state"] == "error":  # the failure came before the question: retry first
        assert h.client.post(f"/runs/{rid}/retry").status_code == 200
        st = h.status(rid)
    assert st["pending"]["type"] == "answer"
    r = h.client.post(f"/runs/{rid}/answer", json={"answer": "Setpoint was changed on M02"})
    assert r.status_code == 200
    for _ in range(3):
        if h.status(rid)["state"] != "error":
            break
        assert h.client.post(f"/runs/{rid}/retry").status_code == 200
    events = [m["data"] for m in sse_events(h.client, rid)]
    audit = h.audit(rid)
    assert sum(1 for e in events if e["type"] == "answer_received") == 1
    assert sum(1 for a in audit if a.action == "answer_received") == 1
    assert check_audit(events, audit) == [] and check_events(events) == []


def test_learning_after_a_halt_uses_the_sop_applied_by_this_proposal(db_session):
    """rollback declined -> halt (the old applied stays in state) -> investigate -> new proposal -> approved:
    the lesson must name the version written now, not the one from before the halt."""
    h = Harness(db_session, generate_dataset(seed=42).tables, random.Random(2))
    h.build(ask_first=False, rollback=True, fail_at=0)
    rid = h.client.post("/runs", json={}).json()["run_id"]
    run = _decide(h, rid, {"decision": "approved", "decided_by": "alice"})
    assert run["pending"]["kind"] == "rollback"
    run = _decide(h, rid, {"decision": "rejected", "decided_by": "bob", "reason": "keep it"})
    assert run["pending"]["kind"] == "halt"
    old = max(v.version for v in h.versions())
    run = _decide(h, rid, {"decision": "investigate", "decided_by": "alice"})
    assert run["pending"]["kind"] == "proposal"
    run = _decide(h, rid, {"decision": "approved", "decided_by": "alice"})
    assert run["state"] == "finished"
    events = [m["data"] for m in sse_events(h.client, rid)]
    assert check_events(events) == [] and check_audit(events, h.audit(rid)) == []
    new = max(v.version for v in h.versions())
    assert new > old
    lesson = next(e for e in events if e["type"] == "learning_saved")["payload"]["content"]
    assert lesson["sop_version"] == new
    applied = [e["payload"] for e in events if e["type"] == "sop_applied"]
    assert applied[-1]["version"] == new


def test_error_and_pending_runs_do_not_hold_connections(own_db_url, monkeypatch):  # noqa: F811
    """Runs that failed or wait for a person keep no pooled connection checked out (default factory, own DB)."""
    from backend.db.session import get_shared_engine

    monkeypatch.setenv("DATABASE_URL", own_db_url)
    monkeypatch.delenv("SME_LLM", raising=False)
    made = []

    def llm_factory(run_id):
        llm = FlakyDemo(DemoLLM(CFG, ask_first=True), 2 if len(made) % 2 == 0 else 0)
        made.append(llm)
        return llm

    with TestClient(create_app(CFG, llm_factory=llm_factory)) as c:
        engine = get_shared_engine()
        waiting, failed = [], []
        for _ in range(6):
            run = c.post("/runs", json={}).json()  # waits for an answer
            assert run["state"] == "waiting", run
            assert engine.pool.checkedout() == 0
            r = c.post(f"/runs/{run['run_id']}/answer", json={"answer": "Setpoint was changed on M02"}).json()
            assert engine.pool.checkedout() == 0
            (failed if r["state"] == "error" else waiting).append(run["run_id"])
        assert failed and waiting, (failed, waiting)
        for rid in failed:
            assert c.post(f"/runs/{rid}/retry").json()["state"] == "waiting"
            assert engine.pool.checkedout() == 0
        for rid in [*failed, *waiting]:  # all pending: finish them one by one
            for _ in range(4):  # a proposal made before another run changed the SOP is sent back once (H-14)
                p = c.get(f"/runs/{rid}").json()["pending"]
                body = {"proposal_id": p["proposal_id"], "kind": p["kind"], "decision": "approved", "decided_by": "alice"}
                r = c.post(f"/runs/{rid}/approval", json=body).json()
                assert engine.pool.checkedout() == 0
                if r["state"] == "finished":
                    break
            assert r["state"] == "finished", r
