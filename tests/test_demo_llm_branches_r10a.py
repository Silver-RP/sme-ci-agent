"""R10a/dev-05 (H-16): the scripted demo LLM (SME_LLM=scripted) survives reject / revise / halt -> investigate and
has a rollback mode (SME_DEMO_SCENARIO=rollback). Over HTTP (TestClient), no network, no key."""

import json

import pytest
from fastapi.testclient import TestClient

from backend.agent.demo_llm import SCENARIO_ENV, llm_from_env, scripted_demo_llm
from backend.agent.llm import ScriptExhaustedError
from backend.api.app import create_app
from backend.domain_config import load_domain_config
from backend.sandbox.injector import generate_dataset
from backend.tools.readonly import ToolContext
from tests.test_act import HUMAN

CFG = load_domain_config()
ANSWER = {"answer": "I have no further information about this."}


def make_client(db_session, monkeypatch, scenario=None, seed=42):
    monkeypatch.setenv("SME_LLM", "scripted")
    if scenario is None:
        monkeypatch.delenv(SCENARIO_ENV, raising=False)
    else:
        monkeypatch.setenv(SCENARIO_ENV, scenario)
    tables = generate_dataset(seed=seed).tables

    def ctx_factory(run_id):
        return ToolContext(tables=tables, session=db_session, run_id=run_id)

    return TestClient(create_app(CFG, ctx_factory=ctx_factory))


def get(c, rid):
    return c.get(f"/runs/{rid}").json()


def decide(c, rid, body):
    p = get(c, rid)["pending"]
    r = c.post(f"/runs/{rid}/approval", json={"proposal_id": p["proposal_id"], "kind": p["kind"], **body})
    assert r.status_code == 200, r.text
    return r.json()


def start(c):
    r = c.post("/runs", json={})
    assert r.status_code == 201, r.text
    run = r.json()
    if run["pending"] and run["pending"]["type"] == "answer":
        run = c.post(f"/runs/{run['run_id']}/answer", json=ANSWER).json()
    assert run["pending"]["kind"] == "proposal", run
    return run


def event_types(c, rid):
    out = []
    with c.stream("GET", f"/runs/{rid}/events") as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                out.append(json.loads(line.split(":", 1)[1])["type"])
    return out


def test_reject_then_approve_reaches_learning_saved(db_session, monkeypatch):
    c = make_client(db_session, monkeypatch)
    rid = start(c)["run_id"]
    run = decide(c, rid, {"decision": "rejected", "decided_by": "alice", "reason": "too risky"})
    assert run["pending"]["kind"] == "proposal"
    run = decide(c, rid, HUMAN)
    assert run["state"] == "finished"
    assert "learning_saved" in event_types(c, rid)


def test_revise_investigates_again_then_approve(db_session, monkeypatch):
    c = make_client(db_session, monkeypatch)
    rid = start(c)["run_id"]
    run = decide(c, rid, {"decision": "revise", "decided_by": "alice", "reason": "check the sensor too"})
    assert run["pending"]["kind"] == "proposal"
    run = decide(c, rid, HUMAN)
    assert run["state"] == "finished"
    assert "learning_saved" in event_types(c, rid)


def test_halt_then_investigate_again_gives_valid_pending(db_session, monkeypatch):
    c = make_client(db_session, monkeypatch)
    rid = start(c)["run_id"]
    for _ in range(CFG.loop.max_rejections):
        run = decide(c, rid, {"decision": "rejected", "decided_by": "alice", "reason": "no"})
    assert run["pending"]["kind"] == "halt"
    run = decide(c, rid, {"decision": "investigate", "decided_by": "alice"})
    assert run["state"] == "waiting" and run["pending"]["type"] in ("approval", "answer")
    assert run["pending"]["kind"] == "proposal"
    assert decide(c, rid, HUMAN)["state"] == "finished"


def test_rollback_scenario_rolls_back_then_learns(db_session, monkeypatch):
    c = make_client(db_session, monkeypatch, scenario="rollback")
    rid = start(c)["run_id"]
    run = decide(c, rid, HUMAN)
    assert run["state"] == "waiting" and run["pending"]["kind"] == "rollback"
    run = decide(c, rid, {"decision": "approved", "decided_by": "bob"})
    assert run["pending"]["kind"] == "proposal"
    run = decide(c, rid, HUMAN)
    assert run["state"] == "finished"
    kinds = event_types(c, rid)
    assert "rollback_done" in kinds and "learning_saved" in kinds


def test_default_scenario_has_no_rollback(db_session, monkeypatch):
    c = make_client(db_session, monkeypatch)
    rid = start(c)["run_id"]
    assert decide(c, rid, HUMAN)["state"] == "finished"
    assert "rollback_done" not in event_types(c, rid)


def test_two_runs_same_app_give_same_event_chain(db_session, monkeypatch):
    c = make_client(db_session, monkeypatch, scenario="rollback")
    chains = []
    for _ in range(2):
        rid = start(c)["run_id"]
        decide(c, rid, HUMAN)
        decide(c, rid, {"decision": "approved", "decided_by": "bob"})
        decide(c, rid, HUMAN)
        chains.append(event_types(c, rid))
    assert chains[0] == chains[1]


def test_unknown_scenario_value_means_default(monkeypatch):
    monkeypatch.setenv("SME_LLM", "scripted")
    monkeypatch.setenv(SCENARIO_ENV, "nonsense")
    assert llm_from_env(CFG) is not None


def test_not_scripted_unchanged(monkeypatch):
    monkeypatch.delenv("SME_LLM", raising=False)
    monkeypatch.setenv(SCENARIO_ENV, "rollback")
    assert llm_from_env(CFG) is None


def test_fixed_script_helper_still_exhausts():
    # the old list-based helper keeps its behaviour (other tests rely on it)
    llm = scripted_demo_llm(CFG, ask_first=False)
    with pytest.raises(ScriptExhaustedError):
        for _ in range(20):
            llm.complete("s", [], [])


def test_a5_rollback_rate_and_pass_after_reinvestigation(db_session, monkeypatch, capsys):
    seeds = [42, 43, 44, 45, 46]
    proposed = passed = 0
    for seed in seeds:
        c = make_client(db_session, monkeypatch, scenario="rollback", seed=seed)
        run = c.post("/runs", json={}).json()
        rid = run["run_id"]
        if run["pending"] and run["pending"]["type"] == "answer":
            run = c.post(f"/runs/{rid}/answer", json=ANSWER).json()
        run = decide(c, rid, HUMAN)
        if run["pending"] and run["pending"]["kind"] == "rollback":
            proposed += 1
            run = decide(c, rid, {"decision": "approved", "decided_by": "bob"})
            run = decide(c, rid, HUMAN)
            if run["state"] == "finished" and "learning_saved" in event_types(c, rid):
                passed += 1
    a5a, a5b = proposed / len(seeds), passed / max(proposed, 1)
    print(f"A5 (a) rollback proposed rate = {a5a:.2f}; (b) pass after re-investigation = {a5b:.2f}")
    assert a5a == 1.0
    assert a5b >= 0.8
