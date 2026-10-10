"""Tests for .autodev/metrics.py (plugin P6b: measurable plugin metrics B1-B5). Run: python3 -m unittest discover .autodev/tests"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("autodev_metrics", HERE.parent / "metrics.py")
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)

PLAN_A = """# R1: x

## Ước tính
| Số task | Phút (worker) | USD (worker + supervisor) | Số vòng review |
|---|---|---|---|
| 2 | 20–30 | 2–4 | 2 |

## Task

### dev-01: a
- **Trạng thái:** DONE · **Số vòng:** 1 (commit abc)

### dev-02: b
- **Trạng thái:** DONE · **Số vòng:** 2 (commit def)
"""

PLAN_B = """# R2: y

## Task

### dev-01: a
- **Trạng thái:** DONE · **Số vòng:** 1
"""

AUDIT_1 = """# Audit 1

## Phạm vi
- Mốc: R1 (PR #1); code tại main.

| Mã | Mức | Tóm tắt | Chỗ | Tái hiện | Test | Xác nhận | Trạng thái |
|---|---|---|---|---|---|---|---|
| H-01 | cao | a | f | r | t | chạy | mở |
| H-02 | thấp | b | f | r | t | đọc | mở |
"""

AUDIT_2 = """# Audit 2

## Phạm vi
- Mốc: R2 (PR #2), R2h (PR #3).

| Mã | Mức | Tóm tắt | Chỗ | Tái hiện | Test | Xác nhận | Trạng thái |
|---|---|---|---|---|---|---|---|
| H-01 | cao | a | f | r | t | chạy | đóng: test_x::test_y (R2) |
| H-03 | vừa | c | f | r | t | đọc | mở |
| H-04 | cao | d | f | r | t | đọc | mở |
| H-05 | thấp | e | f | r | t | đọc | mở |
"""


def run_json(cost, ms, turns):
    return {"total_cost_usd": cost, "duration_ms": ms, "num_turns": turns, "_exit": 0}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "plan").mkdir()
        (root / "plan" / "R1.md").write_text(PLAN_A, encoding="utf-8")
        (root / "plan" / "R2.md").write_text(PLAN_B, encoding="utf-8")
        (root / "plan" / "PROGRESS.md").write_text("# nhật ký\n", encoding="utf-8")
        (root / "docs" / "audits").mkdir(parents=True)
        (root / "docs" / "audits" / "2026-01-01.md").write_text(AUDIT_1, encoding="utf-8")
        (root / "docs" / "audits" / "2026-01-01_2.md").write_text(AUDIT_2, encoding="utf-8")
        runs = root / ".autodev" / "runs"
        runs.mkdir(parents=True)
        files = {
            "20260101-010000-R1-worker.json": run_json(1.5, 20 * 60_000, 30),
            "20260101-012000-R1-supervisor.json": run_json(0.5, 5 * 60_000, 10),
            "20260101-020000-R2-worker.json": run_json(1.0, 10 * 60_000, 15),
            "20260101-021000-R2h-worker.json": run_json(0.2, 2 * 60_000, 5),
            "20260101-030000-audit.json": run_json(0.9, 9 * 60_000, 40),
        }
        for name, data in files.items():
            (runs / name).write_text(json.dumps(data), encoding="utf-8")
        (runs / "run.log").write_text(
            "2026-01-01 01:00:00 start R1-worker: /run-milestone R1\n"
            "2026-01-01 01:10:00 STOP (exit 2): Bước R1-worker lỗi.\n"
            "2026-01-01 01:15:00 start R1-worker: /run-milestone R1\n"
            "2026-01-01 01:35:00 end R1-worker: exit=0 cost=1.5\n"
            "2026-01-01 01:36:00 start R1-supervisor: /supervise R1 --review-only\n"
            "2026-01-01 01:41:00 end R1-supervisor: exit=0 cost=0.5\n"
            "2026-01-01 02:00:00 start R2-worker: /run-milestone R2\n"
            "2026-01-01 02:12:00 end R2-worker: exit=0 cost=1.0\n",
            encoding="utf-8",
        )
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()


class Milestones(Fixture):
    def test_plan_tasks_rounds_and_estimate(self):
        ms = {m["id"]: m for m in metrics.milestones(self.root)}
        self.assertEqual(ms["R1"]["tasks"], 2)
        self.assertEqual(ms["R1"]["rounds"], [1, 2])
        self.assertEqual(ms["R1"]["estimate"], {"minutes": (20.0, 30.0), "usd": (2.0, 4.0)})
        self.assertIsNone(ms["R2"]["estimate"])
        self.assertNotIn("PROGRESS", ms)

    def test_actual_cost_minutes_turns_per_milestone(self):
        ms = {m["id"]: m for m in metrics.milestones(self.root)}
        self.assertAlmostEqual(ms["R1"]["usd"], 2.0)
        self.assertAlmostEqual(ms["R1"]["minutes"], 35.0)  # wall clock from run.log: failed try 10 + 20 + supervisor 5
        self.assertAlmostEqual(ms["R2"]["minutes"], 12.0)
        self.assertEqual(ms["R1"]["turns"], 40)
        self.assertAlmostEqual(ms["R2"]["usd"], 1.0)  # R2h is a different milestone, not part of R2

    def test_interventions_count_stops_inside_the_milestone(self):
        ms = {m["id"]: m for m in metrics.milestones(self.root)}
        self.assertEqual(ms["R1"]["stops"], 1)
        self.assertEqual(ms["R2"]["stops"], 0)

    def test_estimate_ratio(self):
        self.assertEqual(metrics.ratio(25.0, (20.0, 30.0)), 1.0)  # inside the range
        self.assertAlmostEqual(metrics.ratio(60.0, (20.0, 30.0)), 2.0)  # vs the upper bound
        self.assertAlmostEqual(metrics.ratio(10.0, (20.0, 30.0)), 0.5)  # vs the lower bound
        self.assertIsNone(metrics.ratio(10.0, None))


class Audits(Fixture):
    def test_escaped_defects_are_new_high_or_medium_gaps_per_task_in_scope(self):
        au = metrics.audits(self.root)
        self.assertEqual([a["file"] for a in au], ["2026-01-01.md", "2026-01-01_2.md"])
        first, second = au
        self.assertEqual(first["scope"], ["R1"])
        self.assertEqual(first["new_high_medium"], 1)  # H-01 cao; H-02 thấp does not count
        self.assertEqual(first["tasks"], 2)
        self.assertAlmostEqual(first["b1"], 0.5)
        self.assertEqual(second["scope"], ["R2", "R2h"])
        self.assertEqual(second["new_high_medium"], 2)  # H-03, H-04; H-01 is not new
        self.assertEqual(second["tasks"], 1)  # R2h has no plan file: 0 tasks
        self.assertAlmostEqual(second["b1"], 2.0)


class Report(Fixture):
    def test_report_has_every_metric_and_overall_rows(self):
        text = metrics.report(self.root)
        for code in ("B1", "B2", "B3", "B4", "B5"):
            self.assertIn(code, text)
        self.assertIn("| R1 |", text)
        self.assertIn("2026-01-01_2.md", text)
        # B2: 1 of 3 tasks needed >= 2 rounds
        self.assertIn("1/3", text)

    def test_write_replaces_only_the_marked_section(self):
        progress = self.root / "PROGRESS.md"
        progress.write_text("# head\n\nkeep me\n", encoding="utf-8")
        metrics.write_section(progress, "TABLE 1")
        metrics.write_section(progress, "TABLE 2")
        body = progress.read_text(encoding="utf-8")
        self.assertIn("keep me", body)
        self.assertIn("TABLE 2", body)
        self.assertNotIn("TABLE 1", body)
        self.assertEqual(body.count(metrics.START), 1)


if __name__ == "__main__":
    unittest.main()
