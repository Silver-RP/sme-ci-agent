"""Tests for .autodev/usage.py (% of the 5-hour / weekly limits before and after a task). Run: python3 -m unittest discover .autodev/tests"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("autodev_usage", HERE.parent / "usage.py")
usage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usage)


class Usage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.open, self.log, self.latest = d / "open.json", d / "log.md", d / "latest.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_start_then_end_appends_one_row_with_the_change(self):
        usage.start("viết báo cáo", "~30 phút", {"five_hour": 20.4, "seven_day": 40.0}, self.open)
        msg = usage.end({"five_hour": 31.0, "seven_day": 42.6}, self.open, self.log)
        self.assertIn("20% → 31% (+11)", msg)
        rows = [ln for ln in self.log.read_text(encoding="utf-8").splitlines() if ln.startswith("| 20")]
        self.assertEqual(len(rows), 1)
        self.assertIn("| viết báo cáo | ~30 phút |", rows[0])
        self.assertIn("40% → 43% (+3)", rows[0])
        self.assertFalse(self.open.exists())

    def test_reset_window_and_missing_values(self):
        usage.start("x", "", None, self.open)
        msg = usage.end({"five_hour": 5.0, "seven_day": 50.0}, self.open, self.log)
        self.assertIn("– → 5%", msg)
        usage.start("y", "", {"five_hour": 90.0, "seven_day": 50.0}, self.open)
        self.assertIn("(cửa sổ đã reset)", usage.end({"five_hour": 3.0, "seven_day": 51.0}, self.open, self.log))

    def test_end_without_start_does_nothing(self):
        self.assertIn("Chưa có nhiệm vụ", usage.end({"five_hour": 1.0}, self.open, self.log))
        self.assertFalse(self.log.exists())

    def test_read_latest(self):
        self.assertIsNone(usage.read_latest(self.latest))
        self.latest.write_text(json.dumps({"five_hour": 12.5, "seven_day": 3.0}), encoding="utf-8")
        self.assertEqual(usage.read_latest(self.latest)["five_hour"], 12.5)


if __name__ == "__main__":
    unittest.main()
