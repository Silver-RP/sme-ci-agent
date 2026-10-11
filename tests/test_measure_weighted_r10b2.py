"""R10b2/dev-01: Measure KPI is pooled over units (sum numerator / sum denominator), not a mean of shift ratios."""

import pandas as pd
import pytest

from backend.domain_config import MeasureParams, load_domain_config
from backend.tools.actions import measure
from backend.tools.readonly import ToolContext

CFG = load_domain_config()
KPI = CFG.kpis[0]
T0 = "2026-03-10T06:00:00"


def _tables(rows):
    """rows: (shift_start, produced, nonconforming) on one machine."""
    pl = pd.DataFrame(
        {
            "shift_start": pd.to_datetime([r[0] for r in rows]),
            "shift": "morning",
            "machine_id": "M01",
            "units_produced": [r[1] for r in rows],
            "units_nonconforming": [r[2] for r in rows],
            "units_reworked": 0,
        }
    )
    k = pd.DataFrame(
        {
            "timestamp": pl["shift_start"],
            "date": pl["shift_start"].dt.normalize(),
            "shift": "morning",
            "machine_id": "M01",
            "kpi": KPI.name,
            "value": pl["units_nonconforming"] / pl["units_produced"],
        }
    )
    return {"production_log": pl, "kpi_log": k}


@pytest.fixture
def ctx(db_session):
    rows = [
        ("2026-03-09T06:00:00", 1000, 10),  # 1 %
        ("2026-03-09T14:00:00", 10, 5),  # 50 %, tiny shift
        ("2026-03-10T06:00:00", 100, 1),  # 1 %
        ("2026-03-10T14:00:00", 1000, 100),  # 10 %
    ]
    return ToolContext(tables=_tables(rows), session=db_session, run_id=None)


def test_pooled_rate_differs_from_mean_of_rates(ctx):
    r = measure(ctx, kpi=KPI.name, change_time=T0, window_days=2)
    assert r["before"] == pytest.approx(15 / 1010)
    assert r["after"] == pytest.approx(101 / 1100)
    assert r["before"] != pytest.approx((0.01 + 0.5) / 2)
    assert r["after"] != pytest.approx((0.01 + 0.1) / 2)
    assert r["delta"] == pytest.approx(r["after"] - r["before"])


def test_n_counts_are_units(ctx):
    r = measure(ctx, kpi=KPI.name, change_time=T0, window_days=2)
    assert (r["n_before"], r["n_after"]) == (1010, 1100)


def test_min_units_threshold_in_units_from_config(ctx):
    few = measure(ctx, kpi=KPI.name, change_time=T0, window_days=2, min_units_after=1101)
    assert few["sufficient"] is False and few["after"] is None and few["n_after"] == 1100
    ok = measure(ctx, kpi=KPI.name, change_time=T0, window_days=2, min_units_after=1100)
    assert ok["sufficient"] is True
    assert MeasureParams().min_units_after == CFG.measure.min_units_after > 0


def test_repeat_call_same_result_and_no_machine_leak(ctx):
    a = measure(ctx, kpi=KPI.name, change_time=T0, window_days=2)
    assert measure(ctx, kpi=KPI.name, change_time=T0, window_days=2) == a
    assert measure(ctx, kpi=KPI.name, change_time=T0, window_days=2, machine_id="M99", min_units_after=1)["sufficient"] is False


def test_empty_window_raises_without_threshold(ctx):
    with pytest.raises(ValueError):
        measure(ctx, kpi=KPI.name, change_time="2030-01-01")


def test_falls_back_to_kpi_log_without_production_log(db_session):
    t = _tables([("2026-03-09T06:00:00", 100, 10), ("2026-03-10T06:00:00", 100, 20)])
    c = ToolContext(tables={"kpi_log": t["kpi_log"]}, session=db_session)
    r = measure(c, kpi=KPI.name, change_time=T0, window_days=2)
    assert r["before"] == pytest.approx(0.1) and r["after"] == pytest.approx(0.2)
