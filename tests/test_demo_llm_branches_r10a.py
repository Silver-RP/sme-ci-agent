"""R10a/dev-05 (H-16): the scripted demo LLM (SME_LLM=scripted) survives reject / revise / halt -> investigate and
has a rollback mode (SME_DEMO_SCENARIO=rollback). Over HTTP (TestClient), no network, no key."""

import json

import pytest
from fastapi.testclient import TestClient

import pandas as pd

from backend.agent.demo_llm import SCENARIO_ENV, DemoLLM, llm_from_env, scripted_demo_llm
from backend.agent.llm import LLMResponse, ScriptExhaustedError
from backend.sandbox.post_change import action_level, build_post_change_tables
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


SEEDS = [42, 43, 44, 45, 46]


class _Variant(DemoLLM):
    """DemoLLM whose every proposal is rewritten by ``edit`` (always-wrong / no-action LLM for the A5 controls)."""

    def __init__(self, config, edit, **kw):
        super().__init__(config, **kw)
        self._edit = edit

    def _improve(self):
        data = json.loads(super()._improve().text)
        self._edit(data)
        return LLMResponse(text=json.dumps(data))


def _wrong_param(data):
    data["action"]["parameter"] = CFG.actions.parameters[-1]


def _right_param_wrong_value(data):
    data["action"]["value"] = data["action"]["value"] + 15  # still 15 C off the SOP value


def _no_action(data):
    data.pop("action")


def _kpi_measured(c, rid):
    out = []
    with c.stream("GET", f"/runs/{rid}/events") as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                ev = json.loads(line.split(":", 1)[1])
                if ev["type"] == "kpi_measured":
                    out.append(ev["payload"])
    return out


def _drive(c, rid, max_steps=14):
    """Approve every proposal and rollback until the run finishes or a halt needs a person. -> (run, saw_rollback)."""
    run, saw_rollback = get(c, rid), False
    for _ in range(max_steps):
        pend = run.get("pending")
        if run["state"] == "finished" or not pend:
            break
        if pend.get("type") == "answer":
            run = c.post(f"/runs/{rid}/answer", json=ANSWER).json()
        elif pend["kind"] == "proposal":
            run = decide(c, rid, HUMAN)
        elif pend["kind"] == "rollback":
            saw_rollback = True
            run = decide(c, rid, {"decision": "approved", "decided_by": "bob"})
        else:
            break
    return run, saw_rollback


def make_client_llm(db_session, make_llm, seed):
    tables = generate_dataset(seed=seed).tables

    def ctx_factory(run_id):
        return ToolContext(tables=tables, session=db_session, run_id=run_id)

    return TestClient(create_app(CFG, ctx_factory=ctx_factory, llm_factory=lambda rid: make_llm()))


def a5_measure(db_session, monkeypatch, make_llm=None, seeds=SEEDS):
    """Per seed: (a) a rollback was proposed; (b) the LAST kpi_measured has passed == true (not learning_saved)."""
    rows = []
    for seed in seeds:
        if make_llm is None:
            c = make_client(db_session, monkeypatch, scenario="rollback", seed=seed)
        else:
            c = make_client_llm(db_session, make_llm, seed)
        rid = c.post("/runs", json={}).json()["run_id"]
        _, saw_rollback = _drive(c, rid)
        measured = [m for m in _kpi_measured(c, rid) if m["status"] == "measured"]
        rows.append(
            {
                "seed": seed,
                "rolled_back": saw_rollback,
                "passed": bool(measured) and measured[-1]["passed"] is True,
                "after": [round(m["after"], 4) for m in measured],
            }
        )
    return rows


def _print_a5(label, rows):
    a = sum(r["rolled_back"] for r in rows) / len(rows)
    b = sum(r["passed"] for r in rows) / len(rows)
    print(f"A5 [{label}] (a) rollback proposed rate = {a:.2f}; (b) last kpi_measured.passed rate = {b:.2f}")
    for r in rows:
        print(f"   seed {r['seed']}: after={r['after']} rolled_back={r['rolled_back']} passed={r['passed']}")
    return a, b


def test_a5_rollback_rate_and_pass_after_reinvestigation(db_session, monkeypatch, capsys):
    rows = a5_measure(db_session, monkeypatch)
    a5a, a5b = _print_a5("LLM right", rows)
    assert a5a == 1.0
    assert a5b >= 0.8


def test_a5_always_wrong_llm_never_passes(db_session, monkeypatch, capsys):
    rows = a5_measure(db_session, monkeypatch, lambda: _Variant(CFG, _wrong_param))
    _, b = _print_a5("LLM always wrong", rows)
    assert b == 0.0
    assert all(r["after"] for r in rows)  # it was really measured, not skipped


def test_a5_right_parameter_wrong_value_never_passes(db_session, monkeypatch, capsys):
    rows = a5_measure(db_session, monkeypatch, lambda: _Variant(CFG, _right_param_wrong_value))
    _, b = _print_a5("right parameter, wrong value", rows)
    assert b == 0.0
    assert all(r["after"] for r in rows)


def test_a5_control_no_action_applied_never_passes(db_session, monkeypatch, capsys):
    rows = a5_measure(db_session, monkeypatch, lambda: _Variant(CFG, _no_action))
    _, b = _print_a5("nothing applied", rows)
    assert b == 0.0


def test_a5_control_no_change_leaves_kpi_unchanged_on_every_seed():
    """Data level: with no action the post-change KPI stays as it was (no model pulls it to baseline)."""
    mach = CFG.demo.machine_id
    for seed in SEEDS:
        tables = generate_dataset(seed=seed).tables
        k = tables["kpi_log"]
        t0 = pd.Timestamp("2026-03-20")  # ten days into the anomaly
        level = action_level(None, mach, 0.02)
        assert level is None
        post = build_post_change_tables(
            tables, kpi=CFG.kpis[0].name, change_time=t0, machine_id=mach, fixed=False,
            anomaly_start="2026-03-10T22:00:00", level=level, baseline=0.02, noise_sd=0.004,
        )["kpi_log"]

        def mean_after(df):
            sel = (df["kpi"] == CFG.kpis[0].name) & (df["machine_id"] == mach) & (df["timestamp"] >= t0)
            return df.loc[sel & (df["timestamp"] < t0 + pd.Timedelta(days=7)), "value"].mean()

        before, after = mean_after(k), mean_after(post)
        print(f"seed {seed}: KPI after 'apply nothing' = {after:.4f} (source data {before:.4f}, baseline 0.02)")
        assert after > 0.04  # the problem continues; nothing pulled it to the 0.02 baseline
        assert abs(after - before) < 0.01
        assert (post.drop(columns="value").equals(k.drop(columns="value")))  # shape unchanged


def test_a5_seed_changes_real_data(db_session, monkeypatch, capsys):
    rows = a5_measure(db_session, monkeypatch)
    _print_a5("LLM right (seed data)", rows)
    assert len({r["after"][0] for r in rows}) > 1  # the KPI outcome differs between seeds: the data really differs
