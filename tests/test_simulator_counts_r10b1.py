"""R10b1/dev-02: count-based simulator (binomial), material_batches, sop, normal machine events."""

import math

import numpy as np
import pandas as pd
import pytest

from backend.domain_config import load_domain_config
from backend.sandbox import SetpointChange, generate_dataset, simulate
from backend.sandbox.kpi_derive import derive_kpi_log
from backend.sandbox.schema import CONTRACT_TABLE_SCHEMAS, TABLE_NAMES, TABLE_SCHEMAS
from backend.sandbox.simulator import params_from_config

CFG = load_domain_config()
KPI = CFG.kpis[0]  # numerator / denominator column names come from the config
NUM, DEN = KPI.numerator, KPI.denominator
REWORK = next(k for k in CFG.kpis if k.name != KPI.name)


@pytest.fixture(scope="module")
def ds():
    return generate_dataset(seed=42)


def test_contract_tables_are_in_table_schemas():
    for name in ("production_log", "material_batches", "sop"):
        assert name in TABLE_NAMES
        assert TABLE_SCHEMAS[name] == CONTRACT_TABLE_SCHEMAS[name]


# criterion 1: same seed -> identical tables; ratio near baseline outside anomalies
def test_same_seed_identical_tables_and_no_state_leak():
    a = simulate(params_from_config(seed=5))
    simulate(params_from_config(seed=6))
    b = simulate(params_from_config(seed=5))
    assert set(a) == set(TABLE_NAMES)
    for name in TABLE_NAMES:
        pd.testing.assert_frame_equal(a[name], b[name])
    other = simulate(params_from_config(seed=6))
    assert not a["production_log"][NUM].equals(other["production_log"][NUM])


def test_generate_dataset_same_seed_identical_new_tables(ds):
    again = generate_dataset(seed=42)
    for name in ("production_log", "material_batches", "sop", "machine_log", "kpi_log"):
        pd.testing.assert_frame_equal(ds.tables[name], again.tables[name])


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_pooled_rate_outside_anomalies_near_baseline(seed):
    p = params_from_config(seed=seed)
    pl = simulate(p)["production_log"]
    n = int(pl[DEN].sum())
    rate = pl[NUM].sum() / n
    se = math.sqrt(p.baseline * (1 - p.baseline) / n)
    assert abs(rate - p.baseline) <= 3 * se
    # the other KPI is also a binomial count, around its own target
    r2 = pl[REWORK.numerator].sum() / n
    assert abs(r2 - REWORK.target) <= 3 * math.sqrt(REWORK.target * (1 - REWORK.target) / n)


def test_pooled_rate_outside_injected_windows_near_baseline(ds):
    pl = ds.tables["production_log"]
    keep = pd.Series(True, index=pl.index)
    for g in ds.ground_truth:
        keep &= ~((pl["machine_id"] == g.machine_id) & (pl["shift_start"] >= g.start) & (pl["shift_start"] < g.end))
    sub = pl[keep]
    base = params_from_config().baseline
    n = int(sub[DEN].sum())
    se = math.sqrt(base * (1 - base) / n)
    assert abs(sub[NUM].sum() / n - base) <= 3 * se


# criterion 2: integrity
def test_counts_bounded_and_batches_known_and_shift_starts_valid(ds):
    for tables in (ds.tables, simulate(params_from_config(seed=9))):
        pl = tables["production_log"]
        assert (pl[DEN] > 0).all()
        for col in (NUM, REWORK.numerator):
            assert (pl[col] >= 0).all() and (pl[col] <= pl[DEN]).all()
        mb = tables["material_batches"]
        assert not mb["batch_id"].duplicated().any()
        assert set(pl["batch_id"]) <= set(mb["batch_id"])
        assert (pl["batch_id"] != "").all()
        hours = CFG.plant.shift_start_hours
        assert (pl["shift_start"].dt.hour == pl["shift"].map(hours)).all()
        assert (pl["shift_start"].dt.minute == 0).all() and (pl["shift_start"].dt.second == 0).all()
        assert set(pl["shift"]) <= set(CFG.plant.shifts) and set(pl["machine_id"]) <= set(CFG.plant.machines)
        assert not pl.duplicated(["shift_start", "machine_id"]).any()


def test_production_volume_comes_from_config_per_machine_and_shift():
    p = params_from_config()
    pl = simulate(p)["production_log"]
    mean = pl.groupby("machine_id")[DEN].mean()
    assert (mean > 0).all()
    # the config's machine factors show in the data (largest factor -> largest mean)
    f = p.machine_factor
    assert mean.idxmax() == max(f, key=f.get) and mean.idxmin() == min(f, key=f.get)
    # a volume that is changed in the params is followed
    pl2 = simulate(p.with_(units_mean=p.units_mean * 2))["production_log"]
    assert pl2[DEN].mean() > 1.8 * pl[DEN].mean()


def test_material_batches_have_expiry_and_qc(ds):
    mb = ds.tables["material_batches"]
    assert not mb.empty
    assert (mb["expiry_date"] > mb["received_date"]).all()
    assert set(mb["qc_result"]) <= {"pass", "fail", "conditional"}
    assert (mb["supplier_id"] != "").all() and (mb["material_id"] != "").all()
    # a batch is already received when a shift uses it, and not expired in normal operation
    pl = ds.tables["production_log"].merge(mb, on="batch_id")
    assert (pl["shift_start"] >= pl["received_date"]).all()
    assert (pl["shift_start"].dt.normalize() <= pl["expiry_date"]).all()


def test_sop_table_from_config(ds):
    sop = ds.tables["sop"]
    assert set(sop["sop_id"]) == {s.id for s in CFG.sop}
    assert len(sop) == sum(len(s.steps) for s in CFG.sop)


# criterion 3: normal machine events
def test_normal_machine_events_exist_per_machine_and_stay_in_limits(ds):
    ml = ds.tables["machine_log"]
    for m in CFG.plant.machines:
        types = set(ml.loc[ml["machine_id"] == m, "event_type"])
        assert {"program_change", "alarm"} <= types, m
    assert set(ml["event_type"]) <= set(CFG.machine_log.event_types)
    sp = ml[ml["event_type"] == CFG.signals.setpoint_event]
    for _, r in sp.iterrows():
        lim = CFG.actions.limits[r["parameter"]]
        assert lim.min <= r["old_value"] <= lim.max and lim.min <= r["new_value"] <= lim.max
        assert r["old_value"] != r["new_value"]
    al = ml[ml["event_type"] == "alarm"]
    assert set(al["parameter"]) <= set(CFG.actions.parameters)
    pc = ml[ml["event_type"] == "program_change"]
    assert pc["note"].str.startswith("PRG-").all()


def test_normal_events_do_not_give_away_the_answer(ds):
    ml = ds.tables["machine_log"]
    sp = ml[(ml["event_type"] == CFG.signals.setpoint_event) & (ml["parameter"] == "zone3_setpoint_c")]
    # only the two injected anomalies touch the modelled setpoint
    assert len(sp) == 2 and set(sp["new_value"]) == {195.0}
    others = ml[ml["event_type"].isin(["program_change", "alarm"])]
    assert not others["note"].str.contains("planned|wrong|operator", case=False).any()


def test_no_events_when_horizon_is_zero():
    t = simulate(params_from_config().with_(days=0))
    assert t["machine_log"].empty and t["production_log"].empty and t["kpi_log"].empty
    assert list(t["production_log"].columns) == list(TABLE_SCHEMAS["production_log"])


# kpi_log is derived, and the injector pushes p (not the ratio)
def test_kpi_log_is_derived_from_production_log(ds):
    cfg = CFG.model_copy(update={"kpis": [KPI]})
    derived, notes = derive_kpi_log(ds.tables["production_log"], cfg)
    assert notes == []
    pd.testing.assert_frame_equal(derived, ds.tables["kpi_log"], check_dtype=False)


def test_injector_pushes_probability_keeps_volume(ds):
    normal = simulate(params_from_config(seed=42))["production_log"]
    pl = ds.tables["production_log"]
    assert pl[DEN].equals(normal[DEN])  # volume untouched
    for g in ds.ground_truth:
        m = (pl["machine_id"] == g.machine_id) & (pl["shift_start"] >= g.start) & (pl["shift_start"] < g.end)
        n = int(pl.loc[m, DEN].sum())
        se = math.sqrt(g.effect_value * (1 - g.effect_value) / n)
        assert abs(pl.loc[m, NUM].sum() / n - g.effect_value) <= 3 * se, g.id
        assert (pl.loc[m, NUM] <= pl.loc[m, DEN]).all()
    # counts are integers: the ratio is not stamped as a constant
    a1 = next(g for g in ds.ground_truth if g.id == "A1")
    m = (pl["machine_id"] == a1.machine_id) & (pl["shift_start"] >= a1.start)
    assert pl.loc[m, NUM].nunique() > 5
    assert np.issubdtype(pl[NUM].dtype, np.integer)


def test_setpoint_change_then_restore_returns_to_baseline_on_counts():
    p = params_from_config(seed=1)
    ch = (
        SetpointChange("M02", pd.Timestamp("2026-03-10T22:00:00"), 195.0),
        SetpointChange("M02", pd.Timestamp("2026-04-20T06:00:00"), 180.0),
    )
    pl = simulate(p.with_(setpoint_changes=ch))["production_log"]
    m2 = pl[pl["machine_id"] == "M02"]

    def rate(lo, hi):
        s = m2[(m2["shift_start"] >= pd.Timestamp(lo)) & (m2["shift_start"] < pd.Timestamp(hi))]
        return s[NUM].sum() / s[DEN].sum()

    assert rate("2026-03-10T22:00", "2026-04-20T06:00") > p.baseline + 0.03
    assert abs(rate("2026-04-20T06:00", "2027-01-01") - p.baseline) < 0.003
