"""dev-01 (R7): 6-month data + report, T-031."""

import importlib.util
from pathlib import Path

import pandas as pd
import yaml

from backend.sandbox.simulator import DEFAULT_SCENARIO_PATH

PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_report.py"


def _load():
    spec = importlib.util.spec_from_file_location("data_report", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()
REPORT = MOD.build_report(42)


def test_seed42_covers_scenario_horizon():
    scenario = yaml.safe_load(Path(DEFAULT_SCENARIO_PATH).read_text(encoding="utf-8"))
    start = pd.Timestamp(scenario["plant"]["start_date"])
    end = start + pd.DateOffset(months=int(scenario["plant"]["horizon_months"]))
    assert REPORT["date_from"] <= start + pd.Timedelta(days=1)
    assert REPORT["date_to"] >= end - pd.Timedelta(days=2)
    assert REPORT["span_days"] >= 178
    assert all(n > 0 for n in REPORT["rows"].values())


def test_detect_matches_ground_truth_and_skips_planned():
    truth = {t["id"]: t for t in REPORT["truth"]}
    assert truth["A1"]["detected"] and truth["A2_recurrence"]["detected"]
    assert truth["FP1"]["planned"] and not truth["FP1"]["detected"]
    assert all(t["ok"] for t in REPORT["truth"])
    assert REPORT["unmatched"] == []
    # no alarm on the planned machine inside the maintenance window
    fp = truth["FP1"]
    assert not [
        a
        for a in REPORT["anomalies"]
        if a.machine_id == fp["machine"] and fp["start"] <= a.start < fp["end"]
    ]


def test_report_main_prints_summary_and_repeats(capsys):
    mod = _load()
    r1 = mod.main(["--seed", "42"])
    out1 = capsys.readouterr().out
    r2 = mod.main(["--seed", "42"])
    out2 = capsys.readouterr().out
    assert out1 == out2 and r1["rows"] == r2["rows"]
    assert "kpi_log:" in out1 and "A1" in out1 and "FP1" in out1 and "MISS" not in out1
    assert len(out1.splitlines()) < 40
