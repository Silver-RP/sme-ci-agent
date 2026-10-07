# ruff: noqa: DTZ001  (usage-limit reset times are local wall-clock times, so naive local datetimes are intended)
"""Tests for .autodev/run.py (mode B runner). Run: python3 -m unittest discover .autodev/tests

Uses a fake `claude` (AUTODEV_CLAUDE) so no quota is used and no network is needed.
"""

import datetime as dt
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("autodev_run", HERE.parent / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

FAKE = """import json, sys
from pathlib import Path
q = Path(sys.argv[0]).with_suffix(".queue")
items = json.loads(q.read_text())
item = items.pop(0)
q.write_text(json.dumps(items))
print(json.dumps(item["out"]))
sys.exit(item.get("exit", 0))
"""


class Parsing(unittest.TestCase):
    now = dt.datetime(2026, 10, 8, 15, 0)

    def test_reset_pm(self):
        t = run.reset_time("You've hit your session limit · resets 3:45pm", self.now)
        self.assertEqual(t, dt.datetime(2026, 10, 8, 15, 45))

    def test_reset_already_passed_means_tomorrow(self):
        t = run.reset_time("limit reached, resets 9am", self.now)
        self.assertEqual(t, dt.datetime(2026, 10, 9, 9, 0))

    def test_reset_24h_and_noon_midnight(self):
        self.assertEqual(run.reset_time("resets 16:30", self.now), dt.datetime(2026, 10, 8, 16, 30))
        self.assertEqual(run.reset_time("resets 12am", self.now), dt.datetime(2026, 10, 9, 0, 0))
        self.assertEqual(run.reset_time("resets 12pm", self.now), dt.datetime(2026, 10, 9, 12, 0))

    def test_no_reset_time(self):
        self.assertIsNone(run.reset_time("usage limit", self.now))
        self.assertEqual(run.wait_seconds("usage limit", self.now), 30 * 60)

    def test_wait_includes_margin(self):
        self.assertEqual(run.wait_seconds("resets 3:45pm", self.now), 50 * 60)

    def test_classify(self):
        self.assertEqual(run.classify({"result": "done"})[0], "ok")
        self.assertEqual(run.classify({"result": "You've hit your session limit · resets 4pm"})[0], "usage_limit")
        self.assertEqual(run.classify({"result": "You've hit your weekly limit"})[0], "weekly_limit")
        self.assertEqual(run.classify({"result": "boom", "is_error": True})[0], "error")
        self.assertEqual(run.classify({"result": "x", "_exit": 1})[0], "error")
        # a milestone report that merely mentions limits in passing must not count
        self.assertEqual(run.classify({"result": "Cả 3 task PASS. Giới hạn số bước đọc từ config."})[0], "ok")


class Loop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.fake = tmp / "fake_claude.py"
        self.fake.write_text(FAKE)
        self.queue = self.fake.with_suffix(".queue")
        os.environ["AUTODEV_CLAUDE"] = f"{sys.executable} {self.fake}"
        self.old_runs = run.RUNS
        run.RUNS = tmp / "runs"
        self.slept = []

    def tearDown(self):
        run.RUNS = self.old_runs
        os.environ.pop("AUTODEV_CLAUDE", None)
        self.tmp.cleanup()

    def _queue(self, *items):
        self.queue.write_text(json.dumps(list(items)))

    def _step(self):
        clock = lambda: dt.datetime(2026, 10, 8, 15, 0)
        return run.run_step("/run-milestone M9", Path(self.tmp.name), "", "M9-worker", self.slept.append, clock)

    def test_limit_then_resume(self):
        self._queue(
            {"out": {"result": "You've hit your session limit · resets 3:45pm", "is_error": True}, "exit": 1},
            {"out": {"result": "M9 xong", "total_cost_usd": 1.0}},
        )
        res = self._step()
        self.assertEqual(res["result"], "M9 xong")
        self.assertEqual(self.slept, [50 * 60])
        self.assertEqual(json.loads(self.queue.read_text()), [])
        self.assertTrue(any(run.RUNS.glob("*-M9-worker.json")))

    def test_weekly_limit_stops_with_code_3(self):
        self._queue({"out": {"result": "You've hit your weekly limit · resets Oct 12"}, "exit": 1})
        with self.assertRaises(SystemExit) as cm:
            self._step()
        self.assertEqual(cm.exception.code, 3)
        self.assertTrue((run.RUNS / "STOPPED.md").exists())

    def test_error_retries_once_then_stops(self):
        self._queue(
            {"out": {"result": "crash", "is_error": True}, "exit": 1},
            {"out": {"result": "crash again", "is_error": True}, "exit": 1},
        )
        with self.assertRaises(SystemExit) as cm:
            self._step()
        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(self.slept, [120])

    def test_error_then_ok(self):
        self._queue({"out": {"result": "crash", "is_error": True}, "exit": 1}, {"out": {"result": "ok"}})
        self.assertEqual(self._step()["result"], "ok")


if __name__ == "__main__":
    unittest.main()
