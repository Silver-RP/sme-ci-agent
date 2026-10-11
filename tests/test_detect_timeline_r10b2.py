"""R10b2/dev-02: Detect theo dòng thời gian (không rò rỉ tương lai)."""

from functools import cache

import pandas as pd

from backend.detect import detect_anomalies, replay_detect
from backend.domain_config import load_domain_config
from backend.sandbox import generate_dataset

CFG = load_domain_config()
KPI = CFG.kpis[0].name
SHIFT_H = 24 / len(CFG.plant.shifts)


@cache
def ds(seed):
    return generate_dataset(seed=seed)


@cache
def replayed(seed):
    return replay_detect(ds(seed).tables, CFG, KPI)


def cut(tables, t):
    out = dict(tables)
    for name in ("kpi_log", "machine_log"):
        df = tables[name]
        out[name] = df[pd.to_datetime(df["timestamp"]) <= t]
    return out


def test_as_of_equals_result_on_data_cut_after_t():
    t = ds(42).tables
    for ts in ("2026-03-11 06:00", "2026-03-14 22:00", "2026-04-20 14:00", "2026-06-05 06:00", "2026-07-01"):
        ts = pd.Timestamp(ts)
        assert detect_anomalies(t, CFG, KPI, as_of=ts) == detect_anomalies(cut(t, ts), CFG, KPI), ts
        # the cut data itself is a fixed point of as_of (idempotent)
        assert detect_anomalies(cut(t, ts), CFG, KPI, as_of=ts) == detect_anomalies(cut(t, ts), CFG, KPI)


def test_as_of_none_keeps_lookback_and_does_not_mutate_input():
    t = ds(42).tables
    before = len(t["kpi_log"])
    full = detect_anomalies(t, CFG, KPI)
    assert detect_anomalies(t, CFG, KPI, as_of=None) == full
    assert detect_anomalies(t, CFG, KPI, as_of="2100-01-01") == full
    assert len(t["kpi_log"]) == before


def test_as_of_before_data_or_in_reference_is_empty():
    t = ds(42).tables
    assert detect_anomalies(t, CFG, KPI, as_of="2000-01-01") == []
    assert detect_anomalies(t, CFG, KPI, as_of="2026-01-10") == []


def test_no_future_leak_anomaly_not_seen_before_its_data():
    t = ds(42).tables
    g = next(x for x in ds(42).ground_truth if x.id == "A1")
    early = detect_anomalies(t, CFG, KPI, as_of=g.start - pd.Timedelta(hours=1))
    assert not [a for a in early if a.machine_id == g.machine_id]


def test_replay_seed42_a1_a2_within_shift_limit():
    d = ds(42)
    res = replayed(42)
    limit = pd.Timedelta(hours=SHIFT_H * CFG.detect.max_detect_delay_shifts)
    for gid in ("A1", "A2_recurrence"):
        g = next(x for x in d.ground_truth if x.id == gid)
        hits = [r for r in res if r.anomaly.machine_id == g.machine_id and g.start <= r.anomaly.start <= g.start + limit]
        assert len(hits) == 1, gid
        r = hits[0]
        assert g.start <= r.detected_at <= g.start + limit, (gid, r.detected_at)
        assert r.detected_at >= r.anomaly.start


def test_replay_is_repeatable_and_all_detected_not_before_start():
    t = ds(42).tables
    a = replayed(42)
    assert a == replay_detect(t, CFG, KPI)
    assert all(r.detected_at >= r.anomaly.start for r in a)


def test_replay_empty_input():
    empty = {"kpi_log": pd.DataFrame(columns=["timestamp", "date", "shift", "machine_id", "kpi", "value"]), "machine_log": pd.DataFrame()}
    assert replay_detect(empty, CFG) == []
    assert replay_detect({}, CFG) == []
