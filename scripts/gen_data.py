"""Sinh dữ liệu mô phỏng 6 tháng từ data/scenarios/*.yaml (T-010/T-011), xuất theo hợp đồng dữ liệu.

Dùng: uv run python scripts/gen_data.py --seed 42 [--out-dir <thư mục>] [--ground-truth <file>]
Ghi 5 file CSV của hợp đồng (docs/schema/data_contract.md mục 2-3: production_log, machine_log, shift_schedule,
material_batches, sop) vào thư mục xuất (mặc định data/generated/). Thư mục xuất không chứa đáp án.
Ground truth ghi file riêng ngoài thư mục xuất (mặc định: <thư mục xuất>_ground_truth.json, cạnh thư mục).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.dataset_store import SOURCE_TABLES
from backend.sandbox import generate_dataset
from backend.sandbox.schema import TABLE_SCHEMAS
from backend.sandbox.simulator import DEFAULT_SCENARIO_PATH

DEFAULT_OUT_DIR = ROOT / "data" / "generated"
DATE_COLUMNS = {"date", "received_date", "expiry_date"}  # contract kind "date" (the rest of "datetime" are datetimes)


def default_ground_truth_path(out_dir: Path) -> Path:
    out = out_dir.resolve()
    return out.parent / f"{out.name}_ground_truth.json"


def contract_frame(table: str, df: pd.DataFrame) -> pd.DataFrame:
    """Format a sandbox table as text the way the contract says (section 1.1); empty cell = missing value."""
    out = pd.DataFrame(index=df.index)
    for col, kind in TABLE_SCHEMAS[table].items():
        if col not in df.columns:
            continue
        s = df[col]
        if kind == "datetime":
            fmt = "%Y-%m-%d" if col in DATE_COLUMNS else "%Y-%m-%dT%H:%M:%S"
            out[col] = pd.to_datetime(s).dt.strftime(fmt)
        elif kind == "bool":
            out[col] = s.map(lambda v: "" if pd.isna(v) else ("true" if bool(v) else "false"))
        elif kind == "int":
            out[col] = s.map(lambda v: "" if pd.isna(v) else str(int(v)))
        elif kind == "float":
            out[col] = s.map(lambda v: "" if pd.isna(v) else repr(float(v)))
        else:
            out[col] = s.map(lambda v: "" if pd.isna(v) else str(v))
    return out


def main(
    argv: list[str] | None = None, out_dir: str | Path | None = None, ground_truth: str | Path | None = None
) -> dict[str, int]:
    """Generate the dataset, write the contract CSVs + ground truth (separate file), print a short summary.

    Returns the row count per written table.
    """
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--scenario", default=str(DEFAULT_SCENARIO_PATH))
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--ground-truth", default=None, help="file ground truth (mặc định cạnh thư mục xuất)")
    args = ap.parse_args(argv)

    target = Path(out_dir or args.out_dir or DEFAULT_OUT_DIR)
    truth_path = Path(ground_truth or args.ground_truth or default_ground_truth_path(target))
    target.mkdir(parents=True, exist_ok=True)
    truth_path.parent.mkdir(parents=True, exist_ok=True)
    ds = generate_dataset(seed=args.seed, scenario_path=args.scenario)

    counts: dict[str, int] = {}
    for name in SOURCE_TABLES:
        df = ds.tables[name]
        contract_frame(name, df).to_csv(target / f"{name}.csv", index=False, encoding="utf-8")
        counts[name] = len(df)
    truth_path.write_text(
        json.dumps([g.to_dict() for g in ds.ground_truth], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"seed={args.seed} -> {target}")
    for name, n in counts.items():
        print(f"  {name}: {n} rows")
    print(f"  ground truth: {len(ds.ground_truth)} entries -> {truth_path} (separate, outside the export)")
    return counts


if __name__ == "__main__":
    main()
