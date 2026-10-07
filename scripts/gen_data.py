"""Sinh dữ liệu mô phỏng 6 tháng từ data/scenarios/*.yaml (T-010/T-011).

Dùng: uv run python scripts/gen_data.py --seed 42
Ghi CSV các bảng vào data/generated/ và ground truth vào file riêng ground_truth.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.sandbox import generate_dataset
from backend.sandbox.simulator import DEFAULT_SCENARIO_PATH

DEFAULT_OUT_DIR = ROOT / "data" / "generated"
GROUND_TRUTH_FILE = "ground_truth.json"


def main(argv: list[str] | None = None, out_dir: str | Path | None = None) -> dict[str, int]:
    """Generate the dataset, write CSVs + ground truth, print a short summary.

    Returns the row count per table.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--scenario", default=str(DEFAULT_SCENARIO_PATH))
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)

    target = Path(out_dir or args.out_dir or DEFAULT_OUT_DIR)
    target.mkdir(parents=True, exist_ok=True)
    ds = generate_dataset(seed=args.seed, scenario_path=args.scenario)

    counts: dict[str, int] = {}
    for name, df in ds.tables.items():
        df.to_csv(target / f"{name}.csv", index=False)
        counts[name] = len(df)
    (target / GROUND_TRUTH_FILE).write_text(
        json.dumps([g.to_dict() for g in ds.ground_truth], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"seed={args.seed} -> {target}")
    for name, n in counts.items():
        print(f"  {name}: {n} rows")
    print(f"  ground truth: {len(ds.ground_truth)} entries ({GROUND_TRUTH_FILE}, separate)")
    return counts


if __name__ == "__main__":
    main()
