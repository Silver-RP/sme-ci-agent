"""R10b1/dev-03: tools read the contract tables; post_change regenerates counts, then derives kpi_log."""

from functools import cache

import numpy as np
import pandas as pd
import pytest

from backend.domain_config import load_domain_config
from backend.sandbox import generate_dataset
from backend.sandbox.post_change import action_level, build_post_change_tables
from backend.tools.readonly import ToolContext, correlate, query_logs

CFG = load_domain_config()
KPI_CFG = CFG.kpis[0]
KPI = KPI_CFG.name
T0 = pd.Timestamp("2026-03-20")


@cache
def _tables():
    return generate_dataset(seed=42).tables


@pytest.fixture
def ctx(db_session):
    return ToolContext(tables=_tables(), session=db_session, run_id=None)


# ---- correlate reads material_batches + production_log.batch_id ----


def test_correlate_material_signal_does_not_read_inventory(ctx):
    tables = {k: v for k, v in _tables().items() if k != "inventory"}
    c = ToolContext(tables=tables, session=ctx.session)
    r = correlate(c, kpi=KPI, machine_id="M02", start="2026-03-03", end="2026-03-17",
                  hypotheses=["material_batch"])
    assert r["correlations"][0]["status"] in ("ok", "constant")  # a signal exists without inventory
    assert r["correlations"][0]["n"] > 0


def test_correlate_material_signal_comes_from_material_batches(ctx):
    base = _tables()
    # drop the lots table: lots of production_log can no longer be resolved -> no data
    tables = {**base, "material_batches": base["material_batches"].iloc[0:0]}
    r = correlate(ToolContext(tables=tables, session=ctx.session), kpi=KPI, machine_id="M02",
                  hypotheses=["material_batch"])
    assert r["correlations"][0]["status"] == "no_data"


def test_correlate_material_signal_detects_lot_effect(ctx):
    """KPI jumps with the lot: a strong material_batch signal, built only from the contract tables."""
    base = generate_dataset(seed=42).tables
    pl = base["production_log"].copy()
    kl = base["kpi_log"].copy()
    m = pl["machine_id"] == "M01"
    lot = pl.loc[m, "batch_id"]
    odd = pd.Series(np.where(lot.ne(lot.shift()) & lot.shift().notna(), 1.0, 0.0), index=lot.index)
    key = pl.loc[m, ["shift_start"]].assign(odd=odd.to_numpy())
    kl = kl.merge(key.rename(columns={"shift_start": "timestamp"}), on="timestamp", how="left")
    on = (kl["machine_id"] == "M01") & (kl["kpi"] == KPI)
    kl.loc[on, "value"] = 0.02 + 0.05 * kl.loc[on, "odd"].fillna(0.0)
    kl = kl.drop(columns="odd")
    c = ToolContext(tables={**base, "kpi_log": kl}, session=ctx.session)
    r = correlate(c, kpi=KPI, machine_id="M01", hypotheses=["material_batch"])
    assert r["correlations"][0]["strength"] > 0.9


def test_correlate_m03_much_weaker_than_m02_for_setpoint(ctx):
    a = correlate(ctx, kpi=KPI, machine_id="M02", start="2026-03-03", end="2026-03-17",
                  hypotheses=["wrong_setpoint"])["correlations"][0]
    b = correlate(ctx, kpi=KPI, machine_id="M03", start="2026-03-03", end="2026-03-17",
                  hypotheses=["wrong_setpoint"])["correlations"][0]
    assert a["strength"] > 0.3 and a["strength"] > b["strength"] + 0.15


# ---- query_logs on production_log ----


def test_query_logs_production_log(ctx):
    r = query_logs(ctx, kpi=KPI, source="production_log", machine_id="M02",
                   start="2026-03-10", end="2026-03-12")
    assert r["count"] == 6 and len(r["rows"]) == 6
    assert {x["machine_id"] for x in r["rows"]} == {"M02"}
    assert all("2026-03-10" <= x["shift_start"] < "2026-03-12" for x in r["rows"])
    assert "units_produced" in r["rows"][0]
    again = query_logs(ctx, kpi=KPI, source="production_log", machine_id="M02",
                       start="2026-03-10", end="2026-03-12")
    assert again["count"] == r["count"]  # repeat call, no leaked state
    assert query_logs(ctx, kpi=KPI, source="production_log", start="2030-01-01")["rows"] == []
    with pytest.raises(ValueError):
        query_logs(ctx, kpi=KPI, source="material_batches")


def test_tools_do_not_modify_contract_tables(ctx):
    before = {k: v.copy(deep=True) for k, v in ctx.tables.items()}
    query_logs(ctx, kpi=KPI, source="production_log")
    correlate(ctx, kpi=KPI, machine_id="M02")
    for k, v in before.items():
        pd.testing.assert_frame_equal(ctx.tables[k], v)
    for name in ("production_log", "material_batches", "sop"):
        assert name in ctx.tables


# ---- post_change: counts regenerated, kpi_log derived ----


def _post(level=None, fixed=True, machine="M02", run_id="r", tables=None):
    return build_post_change_tables(
        tables or _tables(), kpi=KPI, change_time=T0, machine_id=machine, fixed=fixed,
        anomaly_start="2026-03-10T22:00:00", level=level, baseline=0.02, noise_sd=0.004, run_id=run_id,
    )


def _mean_after(df, machine="M02"):
    sel = (df["kpi"] == KPI) & (df["machine_id"] == machine) & (df["timestamp"] >= T0)
    return df.loc[sel & (df["timestamp"] < T0 + pd.Timedelta(days=7)), "value"].mean()


def test_post_change_does_not_modify_source_tables():
    src = _tables()
    before = {k: v.copy(deep=True) for k, v in src.items()}
    out = _post()
    for k, v in before.items():
        pd.testing.assert_frame_equal(src[k], v)
    assert out["kpi_log"] is not src["kpi_log"] and out["production_log"] is not src["production_log"]


def test_post_change_regenerates_counts_then_derives_kpi_log():
    src = _tables()
    out = _post()
    pl0, pl1 = src["production_log"], out["production_log"]
    num, den = KPI_CFG.numerator, KPI_CFG.denominator
    after = pl1["shift_start"] >= T0
    mach = pl1["machine_id"] == "M02"
    # counts changed only for the machine after the change; denominators and earlier rows untouched
    pd.testing.assert_series_equal(pl0[den], pl1[den])
    assert (pl0.loc[~(after & mach), num] == pl1.loc[~(after & mach), num]).all()
    assert (pl0.loc[after & mach, num] != pl1.loc[after & mach, num]).any()
    assert (pl1[num] <= pl1[den]).all() and (pl1[num] >= 0).all()
    # kpi_log is exactly numerator / denominator of the new counts
    k = out["kpi_log"]
    k = k[(k["kpi"] == KPI) & (k["machine_id"] == "M02") & (k["timestamp"] >= T0)].set_index("timestamp")
    p = pl1[after & mach].set_index("shift_start")
    np.testing.assert_allclose(k["value"].to_numpy(), (p[num] / p[den]).reindex(k.index).to_numpy())
    # shape of kpi_log unchanged
    assert out["kpi_log"].drop(columns="value").equals(src["kpi_log"].drop(columns="value"))


def test_post_change_direction_right_and_wrong_action():
    before = _mean_after(_tables()["kpi_log"])
    assert before > 0.04  # anomaly still running in the source data
    fixed = _mean_after(_post(fixed=True)["kpi_log"])
    assert abs(fixed - 0.02) < 0.006 and fixed < before
    wrong_level = action_level(None, "M02", 0.02)  # nothing changes -> problem continues
    stays = _mean_after(_post(fixed=False, level=wrong_level)["kpi_log"])
    assert stays > 0.04 and abs(stays - before) < 0.01
    sop_level = action_level({"machine_id": "M02", "parameter": "zone3_setpoint_c", "value": 180}, "M02", 0.02)
    right = _mean_after(_post(fixed=False, level=sop_level)["kpi_log"])
    assert abs(right - 0.02) < 0.006


def test_post_change_other_machine_and_repeat_calls_are_independent():
    a = _post(machine="M01")
    b = _post(machine="M01")
    pd.testing.assert_frame_equal(a["kpi_log"], b["kpi_log"])
    pd.testing.assert_frame_equal(a["production_log"], b["production_log"])
    other = _post(machine="M02", run_id="other")
    assert not other["kpi_log"]["value"].equals(a["kpi_log"]["value"])
    # M02 rows untouched when only M01 was asked for
    def m2(d):
        return d[(d["machine_id"] == "M02")]["value"].reset_index(drop=True)

    pd.testing.assert_series_equal(m2(a["kpi_log"]), m2(_tables()["kpi_log"]))


def test_post_change_with_empty_production_log_falls_back_without_crash():
    t = _tables()
    empty = {**t, "production_log": t["production_log"].iloc[0:0], "kpi_log": t["kpi_log"].iloc[0:0]}
    out = _post(tables=empty)
    assert len(out["kpi_log"]) == 0 and len(out["production_log"]) == 0
