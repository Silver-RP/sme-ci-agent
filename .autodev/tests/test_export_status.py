"""Tests for .autodev/export_status.py (plugin P5: datasets of the status page). Run: python3 -m unittest discover .autodev/tests"""

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("autodev_export_status", HERE.parent / "export_status.py")
export_status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_status)

PLAN = """# {mid}: x

## Ước tính
| Số task | Phút (worker) | USD (worker + supervisor) | Số vòng review |
|---|---|---|---|
| 1 | 20–30 | 2–4 | 1 |

### dev-01: a
- **Trạng thái:** DONE · **Số vòng:** 1
"""

STATE = {
    "goals": [{"id": 1, "text": "g1", "percent": 0, "estimate_old": 30, "metrics": ["A1", "A2"]}],
    "open_gaps": [{"id": "H-11", "severity": "cao", "summary": "s", "audit": "a"}],
    "milestones": {
        "runs": [{"id": "R1", "status": "merged", "pr": 1}],
        "plugin": [{"id": "P5", "status": "in_progress", "note": "n"}, {"id": "P7", "status": "todo"}],
    },
    "outlook": [{"id": "R2", "date": "12/10", "goal": "x", "needs_team": True}],
}


class Export(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.root = Path(self.tmp.name)
        (root / "plan").mkdir()
        for mid in ("R1", "R2", "R3"):
            (root / "plan" / f"{mid}.md").write_text(PLAN.format(mid=mid), encoding="utf-8")
        (root / "docs" / "autodev").mkdir(parents=True)
        (root / "docs" / "audits").mkdir()
        (root / "docs" / "autodev" / "state.json").write_text(json.dumps(STATE), encoding="utf-8")
        runs = root / ".autodev" / "runs"
        runs.mkdir(parents=True)
        (runs / "20260101-010000-R1-worker.json").write_text(json.dumps({"total_cost_usd": 3.0}), encoding="utf-8")
        (runs / "20260101-013000-R1-supervisor.json").write_text(json.dumps({"total_cost_usd": 1.0}), encoding="utf-8")
        self.log = runs / "run.log"
        self.log.write_text(
            "2026-01-01 01:00:00 start R1-worker: /run-milestone R1\n"
            "2026-01-01 01:25:00 end R1-worker: exit=0 cost=3.0\n"
            "2026-01-01 01:30:00 start R1-supervisor: /supervise R1\n"
            "2026-01-01 01:40:00 end R1-supervisor: exit=0 cost=1.0\n"
            "2026-01-01 02:00:00 start R2-worker: /run-milestone R2\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_dataset_is_exported(self):
        data = export_status.export(self.root)
        self.assertEqual(set(data), set(export_status.NAMES))
        self.assertEqual(data["goals"][0]["metrics"], "A1, A2")
        self.assertEqual(data["gaps"], [{"id": "H-11", "severity": "cao", "summary": "s"}])
        self.assertEqual(data["plugin"][1], {"milestone": "P7", "status": "todo", "note": ""})
        self.assertEqual(data["outlook"][0]["needs_team"], "có")

    def test_milestone_status_cost_and_estimate_ratio(self):
        rows = {r["milestone"]: r for r in export_status.export(self.root)["milestones"]}
        r1 = rows["R1"]
        self.assertEqual((r1["status"], r1["minutes"], r1["usd"]), ("merged", 25, 4.0))
        self.assertEqual((r1["est_minutes"], r1["est_usd"], r1["b3_minutes"], r1["b3_usd"]), ("20–30", "2–4", 1.0, 1.0))
        self.assertEqual(rows["R2"]["status"], "running")  # started in run.log, no end line yet
        self.assertEqual(rows["R3"]["status"], "planned")
        self.assertIsNone(rows["R3"]["minutes"])

    def test_runner_state_from_the_last_log_line(self):
        self.assertEqual(export_status.runner(self.root)["state"], "running")
        self.log.write_text(self.log.read_text(encoding="utf-8") + "2026-01-01 02:10:00 STOP (exit 2): x\n", encoding="utf-8")
        self.assertEqual(export_status.runner(self.root)["state"], "stopped")
        self.log.write_text("2026-01-01 03:00:00 Hoàn tất R2; tổng chi phí ước tính 1 USD\n", encoding="utf-8")
        self.assertEqual(export_status.runner(self.root)["state"], "idle")

    def test_main_writes_one_json_file_per_dataset(self):
        out = self.root / "out"
        export_status.ROOT, old = self.root, export_status.ROOT
        try:
            export_status.main(["--out", str(out)])
        finally:
            export_status.ROOT = old
        self.assertEqual(sorted(p.stem for p in out.glob("*.json")), sorted(export_status.NAMES))
        shutil.rmtree(out)


if __name__ == "__main__":
    unittest.main()
