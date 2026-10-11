"""R10b2/dev-04: scripts/metrics_report.py, 3 metrics over a replayed period with a "no agent" control."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.db.config import get_database_url
from backend.detect.statistical import replay_detect
from backend.domain_config import UNSOURCED, load_domain_config
from backend.sandbox import generate_dataset

PATH = Path(__file__).resolve().parents[1] / "scripts" / "metrics_report.py"
spec = importlib.util.spec_from_file_location("metrics_report", PATH)
MR = importlib.util.module_from_spec(spec)
sys.modules["metrics_report"] = MR  # dataclasses look the module up by name
spec.loader.exec_module(MR)

CFG = load_domain_config()
METRICS = ("defect_rate_before", "defect_rate_after", "period_rate", "mttd_hours", "mttr_hours", "recurrence_rate")


@pytest.fixture(scope="module")
def data():
    d = generate_dataset(seed=42)
    tables = MR.cut_months(d.tables, 6)
    return SimpleNamespace(tables=tables, truth=d.ground_truth, replay=replay_detect(tables, CFG))


def make_ev(data, config=CFG, truth="default"):
    return MR.Evaluator(
        config, data.tables, data.truth if truth == "default" else truth, MR.temp_db_sessions(), seed=42,
        replay=data.replay,
    )


@pytest.fixture(scope="module")
def ev(data):
    return make_ev(data)


def with_assumption(name, value):
    a = CFG.assumptions[name].model_copy(update={"value": value})
    return CFG.model_copy(update={"assumptions": {**CFG.assumptions, name: a}})


def test_every_metric_is_set_in_both_arms_seed_42(ev):
    rep = MR.build_report(ev, dataset="sandbox", months=6, llm="scripted", sensitivity=False)
    for arm in ("agent", "manual"):
        assert rep[arm]["anomalies_handled"] == 2, arm
        for k in METRICS:
            assert rep[arm][k] is not None, (arm, k)
    # the agent sees the anomaly within a few shifts; the manual arm by its assumed delay
    assert rep["agent"]["mttd_hours"] < rep["manual"]["mttd_hours"]
    assert all(e["passed"] is True for e in rep["agent"]["events"])
    assert all(e["resolved_at"] for e in rep["agent"]["events"] + rep["manual"]["events"])


def test_same_seed_gives_the_same_numbers(data, ev):
    a = MR.build_report(ev, dataset="sandbox", months=6, llm="scripted", sensitivity=False)
    b = MR.build_report(make_ev(data), dataset="sandbox", months=6, llm="scripted", sensitivity=False)  # nothing cached
    for r in (a, b):
        r.pop("generated_at")
    assert a == b


def test_agent_detection_is_after_the_true_start_and_not_before(ev):
    for e in ev.metrics(ev.assumption_values())["agent"]["events"]:
        assert pd.Timestamp(e["detected_at"]) >= pd.Timestamp(e["true_start"])
        assert pd.Timestamp(e["change_time"]) >= pd.Timestamp(e["detected_at"])


@pytest.mark.parametrize(
    ("name", "value", "changes"),
    [
        ("approval_delay_hours", 20.0, "agent"),
        ("sop_prevention_efficacy", 0.9, "agent"),
        ("manual_detect_delay_hours", 100.0, "manual"),
        ("manual_fix_delay_hours", 60.0, "manual"),
    ],
)
def test_changing_one_assumption_changes_only_the_arm_that_uses_it(ev, name, value, changes):
    base = ev.metrics(ev.assumption_values())
    other = "manual" if changes == "agent" else "agent"
    new = ev.metrics(ev.assumption_values({name: value}))
    assert new[changes] != base[changes]
    assert new[other] == base[other]


def test_report_lists_assumptions_with_source_and_sensitivity(ev):
    rep = MR.build_report(ev, dataset="sandbox", months=6, llm="scripted")
    names = {a["name"] for a in rep["assumptions"]}
    assert names == set(CFG.assumptions) and set(MR.REQUIRED_ASSUMPTIONS) <= names
    assert all(a["source"] for a in rep["assumptions"])
    assert {a["source"] for a in rep["assumptions"]} == {UNSOURCED}  # empty source in the YAML
    got = {(r["assumption"], r["value"]) for r in rep["sensitivity"]}
    assert got == {(n, v) for n, a in CFG.assumptions.items() for v in a.alternatives}
    assert all(len(a.alternatives) == 2 for a in CFG.assumptions.values())
    md = MR.to_markdown(rep)
    assert UNSOURCED in md and "approval_delay_hours" in md and "Sensitivity" in md


def test_a_given_source_is_shown():
    a = CFG.assumptions["approval_delay_hours"].model_copy(update={"source": "D3 mục 2"})
    assert a.source_label == "D3 mục 2"


def test_missing_assumptions_are_refused(data):
    bare = CFG.model_copy(update={"assumptions": {}})
    with pytest.raises(ValueError, match="assumptions"):
        MR.Evaluator(bare, data.tables, data.truth, MR.temp_db_sessions(), replay=[])


def test_source_tables_are_not_changed_and_ground_truth_gives_only_the_start(data):
    before = {k: v.copy() for k, v in data.tables.items()}
    # a ground truth that exposes ONLY machine, kpi, start, planned: any other attribute read would raise
    truth = [SimpleNamespace(machine_id=g.machine_id, kpi=g.kpi, start=g.start, planned=g.planned) for g in data.truth]
    ev = make_ev(data, truth=truth)
    ev.metrics(ev.assumption_values())
    for k, v in before.items():
        pd.testing.assert_frame_equal(data.tables[k], v)
    src = PATH.read_text(encoding="utf-8")
    for secret in (".root_cause", ".correct_fix", ".effect_value", "ground_truth["):
        assert secret not in src, secret


def test_without_ground_truth_the_detected_start_is_used(data):
    ev = make_ev(data, truth=None)
    events = ev.metrics(ev.assumption_values())["agent"]["events"]
    assert events and all(e["true_start"] for e in events)


def test_replays_leave_nothing_in_the_main_database(data):
    base = make_url(get_database_url())
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    main = create_engine(base)

    def lessons():
        with main.connect() as c:
            return c.execute(text("select count(*) from learning_store")).scalar()

    def leftovers():
        with admin.connect() as c:
            rows = c.execute(text("select datname from pg_database where datname like :p"),
                             {"p": f"%{MR.TEMP_DB_MARK}%"}).all()
        return {r[0] for r in rows}

    n, left = lessons(), leftovers()
    ev = make_ev(data)
    ev.metrics(ev.assumption_values())
    assert lessons() == n  # lessons of the replay are in a database of its own...
    assert leftovers() == left  # ...which is dropped afterwards
    admin.dispose()
    main.dispose()


def test_lessons_already_in_the_main_database_do_not_hide_anomalies(data, db_session):
    from backend.db import repo

    repo.save_learning(db_session, domain=CFG.domain, run_id="old", content={
        "anomaly": {"kpi": "defect_rate", "machine": "M02", "start": "2026-03-10T22:00:00"}, "kpi": "defect_rate",
        "outcome": "success"})
    db_session.commit()
    ev = make_ev(data)
    assert ev.metrics(ev.assumption_values())["agent"]["anomalies_handled"] == 2


def test_the_first_run_is_not_a_repeat_and_the_second_is_for_the_agent(ev):
    m = ev.metrics(ev.assumption_values())
    assert [e["repeat"] for e in m["agent"]["events"]] == [False, True]
    assert [e["repeat"] for e in m["manual"]["events"]] == [False, True]
    assert m["agent"]["recurrence_rate"] == pytest.approx(0.5 * (1 - CFG.assumptions["sop_prevention_efficacy"].value))
    assert m["manual"]["recurrence_rate"] == 0.5


def test_no_anomaly_gives_empty_metrics_not_a_crash(data):
    short = MR.cut_months(data.tables, 1)  # inside the reference period: nothing to detect
    ev = MR.Evaluator(CFG, short, data.truth, MR.temp_db_sessions(), replay=replay_detect(short, CFG))
    rep = MR.build_report(ev, dataset="sandbox", months=1, llm="scripted", sensitivity=False)
    assert rep["agent"]["anomalies_handled"] == 0 and rep["manual"]["anomalies_handled"] == 0
    assert rep["agent"]["mttd_hours"] is None and rep["manual"]["recurrence_rate"] is None
    assert MR.to_markdown(rep)


def test_main_writes_json_and_markdown(tmp_path, capsys):
    assert MR.main(["--months", "6", "--seed", "42", "--no-sensitivity", "--out-dir", str(tmp_path)]) == 0
    jp, mp = MR.report_paths(tmp_path, "sandbox", 42)
    rep = json.loads(jp.read_text(encoding="utf-8"))
    assert rep["seed"] == 42 and rep["dataset"] == "sandbox" and rep["generated_at"]
    assert all(rep["agent"][k] is not None and rep["manual"][k] is not None for k in METRICS)
    assert "Assumptions" in mp.read_text(encoding="utf-8")
    assert "written:" in capsys.readouterr().out


def test_demo_llm_follows_the_machine_it_is_given_and_defaults_to_the_demo_machine():
    from backend.agent.demo_llm import DemoLLM, demo_improve

    assert json.loads(demo_improve(CFG))["action"]["machine_id"] == CFG.demo.machine_id
    assert json.loads(demo_improve(CFG, machine_id="M01"))["action"]["machine_id"] == "M01"
    llm = DemoLLM(CFG, ask_first=False, machine_id="M01")
    assert json.loads(llm.complete("s", [], []).text)["action"]["machine_id"] == "M01"
    first = DemoLLM(CFG, ask_first=False).complete("s", [{"role": "user"}], [object()])
    assert first.tool_calls[0].arguments["machine_id"] == CFG.demo.machine_id


def test_main_refuses_bad_months(tmp_path):
    assert MR.main(["--months", "0", "--out-dir", str(tmp_path)]) == 2
