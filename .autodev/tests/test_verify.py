"""Tests for .autodev/verify.py: smoke runs of user-facing commands, baseline hygiene (2026-10-08)."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("autodev_verify", HERE.parent / "verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class Smoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pass_fail_timeout_and_skip(self):
        steps = [
            {"name": "ok", "cmd": "true"},
            {"name": "broken", "cmd": "echo boom >&2; exit 3"},
            {"name": "hangs", "cmd": "sleep 5", "timeout": 1},
            {"name": "not yet", "cmd": "false", "if_exists": "scripts/missing.sh"},
        ]
        res = verify.run_smoke(steps, self.cwd)
        by = {r["name"]: r for r in res}
        self.assertEqual(by["ok"]["status"], "ok")
        self.assertEqual(by["broken"]["status"], "fail")
        self.assertIn("boom", by["broken"]["tail"])
        self.assertEqual(by["hangs"]["status"], "timeout")
        self.assertEqual(by["not yet"]["status"], "skipped")

    def test_if_exists_present_runs(self):
        (self.cwd / "x.sh").write_text("")
        res = verify.run_smoke([{"name": "runs", "cmd": "false", "if_exists": "x.sh"}], self.cwd)
        self.assertEqual(res[0]["status"], "fail")


class Baseline(unittest.TestCase):
    def test_exit_keys_never_baselined(self):
        results = {
            "lint": {"keys": ["a.py:E501"], "tail": ""},
            "dashboard": {"keys": ["exit:1"], "tail": "x"},
        }
        self.assertEqual(verify.baseline_from(results), {"lint": ["a.py:E501"], "dashboard": []})


if __name__ == "__main__":
    unittest.main()
