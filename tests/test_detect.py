"""dev-03 (M2): statistical detect, T-012."""

import inspect
import json
from functools import cache
from pathlib import Path

import pandas as pd
import pytest

from backend.detect import DetectParams, detect, detect_anomalies, planned_maintenance_windows
from backend.domain_config import load_domain_config
from backend.sandbox import TABLE_NAMES, generate_dataset
from backend.sandbox.simulator import empty_table

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "docs" / "schema" / "events.json").read_text()
)
CFG = load_domain_config()
KPI = CFG.kpis[0].name
DAY = pd.Timedelta(days=1)


@cache
def ds(seed):
    return generate_dataset(seed=seed)


def gt(d, gid):
    return next(g for g in d.ground_truth if g.id == gid)


def in_window(a, g):
    return a.machine_id == g.machine_id and g.start - DAY <= a.start < g.end + DAY


# 1. threshold from config, KPI is a parameter
def test_threshold_from_config_and_direction():
    t = ds(42).tables
    base = detect_anomalies(t, CFG, KPI)
    # lower threshold: never fewer anomalies; higher threshold (above every injected effect): fewer
    low = detect_anomalies(t, CFG, KPI, threshold_sd=1.5)
    high = detect_anomalies(t, CFG, KPI, threshold_sd=20)
    assert len(low) >= len(base) > len(high) == 0
    assert all(a.upper_limit > a.baseline for a in base)
    assert base[0].upper_limit == pytest.approx(base[0].baseline + 3 * base[0].sigma)
    # the default multiplier is the config's alert_threshold_sd
    cfg2 = CFG.model_copy(deep=True)
    cfg2.kpis[0].alert_threshold_sd = 20
    assert len(detect_anomalies(t, cfg2, KPI)) == len(high)


def test_kpi_is_a_parameter():
    t = ds(42).tables
    assert detect_anomalies(t, CFG, "rework_rate") == []  # no such rows in the data
    with pytest.raises(ValueError):
        detect_anomalies(t, CFG, "nope")


# 2. A1 / A2 detected within 1 day
def test_detects_a1_and_a2_seed42():
    d = ds(42)
    evs = detect(d.tables, CFG, KPI)
    for gid in ("A1", "A2_recurrence"):
        g = gt(d, gid)
        hits = [
            e
            for e in evs
            if e["payload"]["machine"] == g.machine_id
            and g.start <= pd.Timestamp(e["payload"]["start"]) <= g.start + DAY
        ]
        assert len(hits) == 1, gid
        assert hits[0]["payload"]["planned"] is False


# 3. FP1: no anomaly to investigate
def test_no_anomaly_in_fp1_window():
    d = ds(42)
    g = gt(d, "FP1")
    assert not [a for a in detect_anomalies(d.tables, CFG, KPI) if a.machine_id == g.machine_id]
    assert planned_maintenance_windows(d.tables["machine_log"])["M03"] == [(g.start, g.end)]


def test_maintenance_log_is_what_suppresses_fp1():
    d = ds(42)
    log = d.tables["machine_log"]
    no_maint = {**d.tables, "machine_log": log[log["event_type"] != "maintenance"]}
    assert any(a.machine_id == "M03" for a in detect_anomalies(no_maint, CFG, KPI))


# 4. false alarms <= 2 for seeds 1..5
@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_false_alarms_at_most_two(seed):
    d = ds(seed)
    wins = [gt(d, i) for i in ("A1", "A2_recurrence", "FP1")]
    false = [a for a in detect_anomalies(d.tables, CFG, KPI) if not any(in_window(a, g) for g in wins)]
    assert len(false) <= 2, false
    # and the real ones are still found
    for gid in ("A1", "A2_recurrence"):
        g = gt(d, gid)
        assert any(a.machine_id == g.machine_id and g.start <= a.start <= g.start + DAY
                   for a in detect_anomalies(d.tables, CFG, KPI)), (seed, gid)


# 5. events valid
def test_events_valid_against_schema():
    evs = detect(ds(42).tables, CFG, KPI, run_id="run_x")
    assert evs
    ids = set()
    for ev in evs:
        assert set(ev) <= set(SCHEMA["properties"])
        assert all(k in ev for k in SCHEMA["required"])
        assert ev["type"] == "anomaly_detected" == SCHEMA["examples"][0]["type"]
        assert ev["agent"] == "quality" and ev["agent"] in SCHEMA["properties"]["agent"]["enum"]
        assert ev["domain"] == CFG.domain
        assert ev["run_id"] == "run_x"
        p = ev["payload"]
        for key in ("kpi", "machine", "start", "value", "baseline", "upper_limit"):
            assert key in p
        assert p["kpi"] == KPI and p["value"] > p["upper_limit"] > p["baseline"]
        pd.Timestamp(ev["ts"])
        ids.add(ev["event_id"])
    assert len(ids) == len(evs)


def test_domain_comes_from_config():
    cfg2 = CFG.model_copy(update={"domain": "other_domain"})
    evs = detect(ds(42).tables, cfg2, KPI)
    assert evs and {e["domain"] for e in evs} == {"other_domain"}


# 6. tables only; empty / normal data -> nothing; repeatable
def test_signature_has_no_ground_truth():
    for fn in (detect, detect_anomalies):
        names = " ".join(inspect.signature(fn).parameters).lower()
        assert "truth" not in names and "ground" not in names


def test_empty_input():
    empty = {n: empty_table(n) for n in TABLE_NAMES}
    assert detect(empty, CFG, KPI) == []
    assert detect({}, CFG, KPI) == []


def test_normal_data_only_has_no_anomaly():
    from backend.sandbox.simulator import params_from_config, simulate

    for seed in (1, 2, 3):
        normal = simulate(params_from_config(seed=seed))
        assert detect(normal, CFG, KPI) == []


def test_repeated_calls_same_result_and_no_mutation():
    t = ds(42).tables
    before = t["kpi_log"].copy()
    a = detect(t, CFG, KPI)
    b = detect(t, CFG, KPI)
    strip = lambda evs: [{**e, "ts": None} for e in evs]  
    assert strip(a) == strip(b)
    pd.testing.assert_frame_equal(before, t["kpi_log"])


def test_anomalies_are_merged_not_per_point():
    d = ds(42)
    a1 = [a for a in detect_anomalies(d.tables, CFG, KPI) if a.machine_id == "M02"]
    assert len(a1) == 1 and a1[0].n_points > 10  # lasts to the end of the horizon
    assert DetectParams().rule_hits == 2 and DetectParams().rule_window == 3
