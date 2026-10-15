"""Tests for .autodev/goal_check.py (P10, design 6.16). Run: python3 -m unittest discover .autodev/tests"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("autodev_goal_check", HERE.parent / "goal_check.py")
gc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gc)


def valid() -> dict:
    return {
        "slug": "demo-goal",
        "goal": "Qua cổng thử",
        "status": "approved",
        "done_when": [{"id": "A1", "cmd": "echo 1", "threshold": ">= 0.7"}],
        "milestones": [
            {"id": "R1", "title": "Mốc một", "depends_on": [], "metrics": ["A1"],
             "est_usd": 5, "est_hours": 2, "status": "planned"},
            {"id": "R2", "title": "Mốc hai", "depends_on": ["R1"], "reason": "dọn nợ giao diện",
             "est_usd": 3.5, "est_hours": 1, "status": "planned", "plan_file": "plan/R2.md"},
        ],
        "cut_order": ["R2"],
        "human_only": ["bug bash bấm tay"],
    }


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "plan").mkdir()
        (self.root / "plan" / "R2.md").write_text("# R2\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self, data):
        return gc.check(data, self.root)

    def assertError(self, data, needle):
        errs = self.errors(data)
        self.assertTrue(any(needle in e for e in errs), f"không có lỗi chứa {needle!r}: {errs}")


class Check(Base):
    def test_valid_goal_has_no_errors(self):
        self.assertEqual(self.errors(valid()), [])

    def test_not_an_object(self):
        self.assertError([], "object")

    def test_missing_top_level_field(self):
        d = valid()
        del d["done_when"]
        self.assertError(d, "done_when")

    def test_bad_goal_status(self):
        d = valid()
        d["status"] = "ok"
        self.assertError(d, "status")

    def test_lists_must_be_lists(self):
        d = valid()
        d["milestones"] = {}
        self.assertError(d, "milestones")

    def test_approved_goal_needs_done_when_but_draft_does_not(self):
        d = valid()
        d["done_when"] = []
        self.assertError(d, "done_when")
        d["status"] = "draft"
        self.assertEqual(self.errors(d), [])

    def test_done_when_item_needs_id_cmd_threshold(self):
        d = valid()
        d["done_when"] = [{"id": "A1", "cmd": ""}]
        self.assertError(d, "cmd")
        self.assertError(d, "threshold")

    def test_milestone_missing_field(self):
        d = valid()
        del d["milestones"][0]["est_hours"]
        self.assertError(d, "est_hours")

    def test_duplicate_milestone_id(self):
        d = valid()
        d["milestones"][1]["id"] = "R1"
        d["cut_order"] = []
        self.assertError(d, "trùng")

    def test_bad_milestone_status(self):
        d = valid()
        d["milestones"][0]["status"] = "planned_file"
        self.assertError(d, "status")

    def test_milestone_needs_metrics_or_reason(self):
        d = valid()
        d["milestones"][0]["metrics"] = []
        self.assertError(d, "reason")

    def test_est_usd_must_be_a_positive_number(self):
        for bad in (0, -1, "6", True):
            with self.subTest(est_usd=bad):
                d = valid()
                d["milestones"][0]["est_usd"] = bad
                self.assertError(d, "est_usd")

    def test_plan_file_must_exist(self):
        d = valid()
        d["milestones"][1]["plan_file"] = "plan/R9.md"
        self.assertError(d, "plan/R9.md")

    def test_unknown_dependency(self):
        d = valid()
        d["milestones"][1]["depends_on"] = ["R7"]
        self.assertError(d, "R7")

    def test_dependency_cycle_and_self_dependency(self):
        d = valid()
        d["milestones"][0]["depends_on"] = ["R2"]
        self.assertError(d, "vòng")
        d = valid()
        d["milestones"][0]["depends_on"] = ["R1"]
        self.assertError(d, "vòng")

    def test_cut_order_unknown_milestone(self):
        d = valid()
        d["cut_order"] = ["R5"]
        self.assertError(d, "R5")


class CheckFile(Base):
    def write(self, data, slug="demo-goal", raw=None):
        folder = self.root / "docs" / "goals" / slug
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "goal.json"
        path.write_text(raw if raw is not None else json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = gc.main(argv, self.root)
        return code, out.getvalue()

    def test_check_file_ok(self):
        self.assertEqual(gc.check_file(self.write(valid()), self.root), [])

    def test_check_file_bad_json_is_an_error_not_a_crash(self):
        errs = gc.check_file(self.write(None, raw='{"slug": "demo-goal",}'), self.root)
        self.assertEqual(len(errs), 1)
        self.assertIn("JSON", errs[0])

    def test_check_file_missing_file(self):
        errs = gc.check_file(self.root / "docs" / "goals" / "x" / "goal.json", self.root)
        self.assertIn("JSON", errs[0])

    def test_check_file_slug_must_match_folder(self):
        errs = gc.check_file(self.write(valid(), slug="other-goal"), self.root)
        self.assertTrue(any("slug" in e for e in errs), errs)

    def test_main_exit_codes(self):
        good = self.write(valid())
        bad_data = valid()
        bad_data["status"] = "ok"
        bad_data["slug"] = "bad-goal"
        bad = self.write(bad_data, slug="bad-goal")
        self.assertEqual(self.run_main([])[0], 2)
        code, out = self.run_main([str(good)])
        self.assertEqual(code, 0)
        self.assertIn("ok", out)
        code, out = self.run_main([str(good), str(bad)])
        self.assertEqual(code, 1)
        self.assertIn("status", out)


if __name__ == "__main__":
    unittest.main()
