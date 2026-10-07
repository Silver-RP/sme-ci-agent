import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from backend.sandbox import TABLE_NAMES, generate_dataset
from backend.sandbox.injector import load_scenario
from backend.sandbox.simulator import DEFAULT_SCENARIO_PATH

SCEN = load_scenario()
NOISE = SCEN["baseline"]["noise_sd"]
BASE = SCEN["baseline"]["value"]
SOP_SP = SCEN["baseline"]["zone3_setpoint_c"]


@pytest.fixture(scope="module")
def ds():
    return generate_dataset(seed=42)


def gt(ds, gid):
    return next(g for g in ds.ground_truth if g.id == gid)


def window_mean(ds, g):
    k = ds.tables["kpi_log"]
    m = (k["machine_id"] == g.machine_id) & (k["timestamp"] >= g.start) & (k["timestamp"] < g.end)
    return k.loc[m, "value"].mean(), int(m.sum())


# --- criterion 1: ground truth vs YAML ---
def test_ground_truth_matches_yaml(ds):
    specs = {a["id"]: a for a in SCEN["injected_anomalies"]}
    for gid, spec in specs.items():
        g = gt(ds, gid)
        assert g.machine_id == spec["machine"]
        assert g.start == pd.Timestamp(spec["start"])
        assert g.root_cause == spec["ground_truth"]["root_cause"]
        assert g.planned is False
    fp = gt(ds, SCEN["false_positive_case"]["id"])
    assert fp.machine_id == "M03" and fp.planned is True
    assert fp.start == pd.Timestamp(SCEN["false_positive_case"]["start"])
    assert fp.end == pd.Timestamp(SCEN["false_positive_case"]["end"])
    assert {g.id for g in ds.ground_truth} == {*specs, "FP1"}


def test_ground_truth_is_separate_from_tables(ds):
    assert set(ds.tables) == set(TABLE_NAMES)  # no 7th table for ground truth


# --- criterion 2: traces in logs ---
def test_machine_log_setpoint_changes(ds):
    ml = ds.tables["machine_log"]
    for gid, machine in (("A1", "M02"), ("A2_recurrence", "M01")):
        g = gt(ds, gid)
        row = ml[(ml["event_type"] == "setpoint_change") & (ml["machine_id"] == machine)]
        assert len(row) == 1
        r = row.iloc[0]
        assert r["timestamp"] == g.start
        assert (r["old_value"], r["new_value"]) == (180.0, 195.0)
        assert r["parameter"] == "zone3_setpoint_c"


def test_shift_schedule_has_night_substitute_around_a1(ds):
    s = ds.tables["shift_schedule"]
    a1 = gt(ds, "A1")
    sub = s[s["is_substitute"]]
    assert not sub.empty
    assert set(sub["machine_id"]) == {"M02"} and set(sub["shift"]) == {"night"}
    assert (sub["date"] == a1.start.normalize()).any()
    assert sub["date"].between(a1.start.normalize() - pd.Timedelta(days=2),
                               a1.start.normalize() + pd.Timedelta(days=2)).all()
    # table still complete: one row per (date, shift, machine)
    assert not s.duplicated(["date", "shift", "machine_id"]).any()


def test_fp1_has_planned_maintenance_record(ds):
    ml = ds.tables["machine_log"]
    fp = gt(ds, "FP1")
    mt = ml[(ml["event_type"] == "maintenance") & (ml["machine_id"] == "M03")]
    assert fp.start in set(mt["timestamp"]) and fp.end in set(mt["timestamp"])
    assert mt["note"].str.contains("planned").all()


# --- criterion 3: effect level inside window, baseline outside ---
@pytest.mark.parametrize("gid", ["A1", "A2_recurrence", "FP1"])
def test_mean_in_window_near_effect(ds, gid):
    g = gt(ds, gid)
    mean, n = window_mean(ds, g)
    assert n >= 5
    assert abs(mean - g.effect_value) <= NOISE
    assert g.effect_value == pytest.approx(
        next(
            (a["effect"]["defect_rate"] for a in SCEN["injected_anomalies"] if a["id"] == gid),
            SCEN["false_positive_case"]["effect"]["defect_rate"],
        )
    )


def test_outside_windows_stays_baseline(ds):
    k = ds.tables["kpi_log"]
    for machine in ("M01", "M02", "M03"):
        m = k["machine_id"] == machine
        for g in ds.ground_truth:
            if g.machine_id == machine:
                m &= ~((k["timestamp"] >= g.start) & (k["timestamp"] < g.end))
        assert abs(k.loc[m, "value"].mean() - BASE) <= NOISE
    # untouched machine: M03 apart from FP1 is baseline too (covered above); values valid
    assert k["value"].between(0, 1).all()


def test_window_without_end_runs_to_horizon(ds):
    horizon_end = pd.Timestamp("2026-01-01") + pd.DateOffset(months=6)
    for gid in ("A1", "A2_recurrence"):
        assert gt(ds, gid).end == horizon_end


def test_explicit_end_restores_setpoint(tmp_path):
    scen = load_scenario()
    scen["injected_anomalies"][0]["end"] = "2026-03-20T06:00:00"
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(scen), encoding="utf-8")
    d = generate_dataset(seed=42, scenario_path=p)
    a1 = gt(d, "A1")
    assert a1.end == pd.Timestamp("2026-03-20T06:00:00")
    ml = d.tables["machine_log"]
    back = ml[(ml["machine_id"] == "M02") & (ml["new_value"] == 180.0)]
    assert list(back["timestamp"]) == [a1.end]
    k = d.tables["kpi_log"]
    after = k[(k["machine_id"] == "M02") & (k["timestamp"] >= a1.end)]
    assert abs(after["value"].mean() - BASE) <= NOISE


# --- criterion 4: recurrence ---
def test_a2_recurs_a1_root_cause_on_other_machine_later(ds):
    a1, a2 = gt(ds, "A1"), gt(ds, "A2_recurrence")
    assert a2.root_cause == a1.root_cause
    assert a2.machine_id != a1.machine_id
    assert a2.start > a1.start


# --- criterion 5: no leakage into tables ---
def test_tables_do_not_leak_ground_truth(ds):
    secrets = {"root_cause", "hidden", "ground_truth", "wrong_setpoint", "correct_fix"}
    for name, df in ds.tables.items():
        for col in df.columns:
            assert not any(s in col.lower() for s in secrets), (name, col)
        text = df.select_dtypes(include="object")
        for col in text.columns:
            vals = " ".join(text[col].astype(str).unique()).lower()
            assert not any(s in vals for s in secrets), (name, col)
    # the A1/A2 ids and FP1 id are not marked anywhere in the tables either
    ids = {g.id for g in ds.ground_truth}
    for df in ds.tables.values():
        for col in df.select_dtypes(include="object").columns:
            assert not (set(df[col].astype(str)) & ids), col


# --- determinism / repeated calls / seeds ---
def test_same_seed_identical_and_repeatable(ds):
    again = generate_dataset(seed=42)
    for name in TABLE_NAMES:
        pd.testing.assert_frame_equal(ds.tables[name], again.tables[name])
    assert ds.ground_truth == again.ground_truth


def test_different_seed_differs_but_same_truth(ds):
    other = generate_dataset(seed=7)
    assert not ds.tables["kpi_log"]["value"].equals(other.tables["kpi_log"]["value"])
    assert ds.ground_truth == other.ground_truth


def test_inject_does_not_mutate_input():
    from backend.sandbox import inject, simulate
    from backend.sandbox.simulator import params_from_config

    p = params_from_config()
    normal = simulate(p)
    snap = {k: v.copy() for k, v in normal.items()}
    inject(normal, p, load_scenario())
    for k in normal:
        pd.testing.assert_frame_equal(normal[k], snap[k])


def test_scenario_without_injections_is_normal(tmp_path):
    scen = load_scenario()
    scen["injected_anomalies"] = []
    scen.pop("false_positive_case")
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(scen), encoding="utf-8")
    d = generate_dataset(seed=42, scenario_path=p)
    assert d.ground_truth == []
    assert d.tables["machine_log"].empty
    assert not d.tables["shift_schedule"]["is_substitute"].any()


# --- criterion 6: gen_data script ---
def _load_gen_data():
    path = Path(__file__).resolve().parents[1] / "scripts" / "gen_data.py"
    spec = importlib.util.spec_from_file_location("gen_data", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_gen_data_main_writes_csv_and_summary(tmp_path, capsys):
    mod = _load_gen_data()
    counts = mod.main(["--seed", "42"], out_dir=tmp_path)
    out = capsys.readouterr().out
    assert set(counts) == set(TABLE_NAMES)
    for name in TABLE_NAMES:
        assert (tmp_path / f"{name}.csv").exists()
        assert f"{name}: {counts[name]} rows" in out
    k = pd.read_csv(tmp_path / "kpi_log.csv", parse_dates=["timestamp"])
    span_days = (k["timestamp"].max() - k["timestamp"].min()).days
    assert 178 <= span_days <= 184  # 6 months
    truth = json.loads((tmp_path / "ground_truth.json").read_text(encoding="utf-8"))
    assert {t["id"] for t in truth} == {"A1", "A2_recurrence", "FP1"}
    # ground truth is a separate file, not in any CSV
    for name in TABLE_NAMES:
        header = (tmp_path / f"{name}.csv").read_text(encoding="utf-8").splitlines()[0]
        assert "root_cause" not in header


def test_gen_data_repeat_call_same_output(tmp_path):
    mod = _load_gen_data()
    a, b = tmp_path / "a", tmp_path / "b"
    mod.main(["--seed", "3"], out_dir=a)
    mod.main(["--seed", "3"], out_dir=b)
    assert (a / "kpi_log.csv").read_text() == (b / "kpi_log.csv").read_text()


def test_default_scenario_path_unchanged():
    assert Path(DEFAULT_SCENARIO_PATH).name == "scenario1.yaml"
