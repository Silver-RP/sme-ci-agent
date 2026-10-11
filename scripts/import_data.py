"""Nhập dữ liệu CSV của khách vào một dataset có tên (hợp đồng: docs/schema/data_contract.md mục 3).

Dùng: uv run python scripts/import_data.py <thư mục> [--check-only] [--name <tên>]
  1. Kiểm hợp lệ (mục 4) và in báo cáo: số dòng mỗi bảng, lỗi, cảnh báo, ghi chú.
  2. Có lỗi: không nạp gì, thoát mã 1. Chỉ có cảnh báo: vẫn nạp.
  3. Không lỗi và không có --check-only: lưu dataset (data/datasets/<tên>/); chạy agent với SME_DATASET=<tên>.
File nguồn không bị sửa. Mã thoát 2: tham số hoặc việc lưu hỏng.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.dataset_store import DatasetError, save_dataset
from backend.domain_config import load_domain_config
from backend.sandbox.validate import Validation, read_directory

SEVERITY_ORDER = ("error", "warning", "note")


def _fmt(item: dict) -> str:
    where = item.get("table") or "-"
    if item.get("row") is not None:
        where += f" dòng {item['row']}"
    if item.get("column"):
        where += f" cột {item['column']}"
    val = f" giá trị={item['value']!r}" if item.get("value") not in (None, "") else ""
    fix = f" -> {item['fix']}" if item.get("fix") else ""
    return f"  {item['code']} {where}{val}{fix}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("directory", help="thư mục chứa các file CSV")
    ap.add_argument("--check-only", action="store_true", help="chỉ kiểm, không ghi gì")
    ap.add_argument("--name", default=None, help="tên dataset (mặc định: tên thư mục)")
    args = ap.parse_args(argv)

    src = Path(args.directory)
    if not src.is_dir():
        print(f"Không thấy thư mục: {src}", file=sys.stderr)
        return 2

    # The validator's own config: the dataset in SME_DATASET (if any) must not change what is checked.
    cfg = load_domain_config()
    tables, extras = read_directory(src)
    issues = Validation(tables, list(extras), cfg).run()

    counts = {n: len(t.rows) for n, t in tables.items() if t.status == "ok"}
    print(f"Thư mục: {src}")
    print("Số dòng mỗi bảng:")
    for name, t in tables.items():
        print(f"  {name}: {counts[name]}" if name in counts else f"  {name}: (không đọc được: {t.status})")
    for sev, label in zip(SEVERITY_ORDER, ("Lỗi", "Cảnh báo", "Ghi chú"), strict=True):
        items = [i for i in issues if i["severity"] == sev]
        print(f"{label}: {len(items)}")
        for i in items:
            print(_fmt(i))

    n_err = sum(1 for i in issues if i["severity"] == "error")
    if n_err:
        print(f"KHÔNG NẠP: {n_err} lỗi.", file=sys.stderr)
        return 1
    if args.check_only:
        print("Kiểm xong (--check-only): không ghi gì.")
        return 0
    name = args.name or src.resolve().name
    try:
        path = save_dataset(src, name, counts)
    except DatasetError as e:
        print(f"Không lưu được: {e}", file=sys.stderr)
        return 2
    print(f"Đã nạp dataset {name!r} tại {path}. Dùng: SME_DATASET={name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
