"""Báo cáo kiểm tra dữ liệu sandbox (T-031).

Dùng: uv run python scripts/data_report.py [--seed 42]
In: khoảng ngày, số dòng mỗi bảng, anomaly Detect tìm được so với ground truth.
Ground truth chỉ dùng để chấm trong báo cáo này, không đưa vào Detect.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.detect import detect_anomalies
from backend.domain_config import load_domain_config
from backend.sandbox import generate_dataset
from backend.sandbox.simulator import DEFAULT_SCENARIO_PATH

DAY = pd.Timedelta(days=1)


def build_report(seed: int = 42, scenario_path: str | Path = DEFAULT_SCENARIO_PATH) -> dict[str, Any]:
    """Generate the dataset, run Detect on the tables only, and compare with ground truth."""
    ds = generate_dataset(seed=seed, scenario_path=scenario_path)
    config = load_domain_config()
    ts = pd.to_datetime(ds.tables["kpi_log"]["timestamp"])
    anomalies = detect_anomalies(ds.tables, config)

    def matches(a, g) -> bool:
        return a.machine_id == g.machine_id and g.start - DAY <= a.start < g.end + DAY

    truth = []
    for g in ds.ground_truth:
        hit = [a for a in anomalies if matches(a, g)]
        truth.append(
            {
                "id": g.id,
                "machine": g.machine_id,
                "start": g.start,
                "end": g.end,
                "planned": g.planned,
                "detected": bool(hit),
                # real anomaly must be found; planned maintenance must NOT be reported
                "ok": bool(hit) != g.planned,
            }
        )
    unmatched = [a for a in anomalies if not any(matches(a, g) for g in ds.ground_truth)]
    return {
        "seed": seed,
        "date_from": ts.min(),
        "date_to": ts.max(),
        "span_days": (ts.max() - ts.min()).days,
        "rows": {name: len(df) for name, df in ds.tables.items()},
        "anomalies": anomalies,
        "truth": truth,
        "unmatched": unmatched,
    }


def format_report(r: dict[str, Any]) -> str:
    lines = [
        "seed={}  range: {:%Y-%m-%d} .. {:%Y-%m-%d} ({} days)".format(
            r["seed"], r["date_from"], r["date_to"], r["span_days"]
        ),
        "rows per table:",
    ]
    lines += [f"  {name}: {n}" for name, n in r["rows"].items()]
    lines.append(f"detected anomalies: {len(r['anomalies'])}")
    for a in r["anomalies"]:
        lines.append(f"  {a.machine_id} {a.kpi} {a.start:%Y-%m-%d %H:%M} .. {a.end:%Y-%m-%d %H:%M}")
    lines.append("vs ground truth:")
    for t in r["truth"]:
        kind = "planned (must NOT alarm)" if t["planned"] else "real (must alarm)"
        status = "OK" if t["ok"] else "MISS"
        lines.append(
            f"  {t['id']} {t['machine']} {t['start']:%Y-%m-%d} {kind}: "
            f"{'detected' if t['detected'] else 'not detected'} -> {status}"
        )
    lines.append(f"unmatched detections (false alarms): {len(r['unmatched'])}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--scenario", default=str(DEFAULT_SCENARIO_PATH))
    args = ap.parse_args(argv)
    report = build_report(args.seed, args.scenario)
    print(format_report(report))
    return report


if __name__ == "__main__":
    main()
