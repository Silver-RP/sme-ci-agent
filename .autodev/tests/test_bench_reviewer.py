"""Tests for .autodev/bench_reviewer.py (proposal 4: measure reviewer recall on escaped bugs). No LLM is called."""

import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("autodev_bench", HERE.parent / "bench_reviewer.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

BUG = {"id": "p1", "hole": "H-57", "task_id": "R10a/dev-02", "base": "aaa", "head": "bbb", "plan": "plan/R10a.md",
       "files": ["backend/api/kpi_series.py"], "keywords": "múi giờ|timezone|tz"}
CLEAN = {"id": "p4", "hole": None, "task_id": "R10a/dev-03", "base": "ccc", "head": "ddd", "plan": "plan/R10a.md",
         "files": [], "keywords": ""}


def review(status, issues=()):
    return {"status": status, "blocking_issues": [dict(i) for i in issues]}


class Prompt(unittest.TestCase):
    def test_strip_frontmatter(self):
        self.assertEqual(bench.strip_frontmatter("---\nname: reviewer\n---\n\nBody\n"), "Body\n")
        self.assertEqual(bench.strip_frontmatter("Body"), "Body")

    def test_prompt_has_body_and_case_input(self):
        p = bench.build_prompt("Bạn là reviewer.", BUG)
        self.assertTrue(p.startswith("Bạn là reviewer."))
        for s in ("R10a/dev-02", "aaa..HEAD", "plan/R10a.md"):
            self.assertIn(s, p)
        self.assertNotIn("H-57", p)  # never leak the answer
        self.assertNotIn("kpi_series", p)

    def test_cmd_restricts_tools_and_sets_model(self):
        cmd = bench.build_cmd("x", "sonnet", ["claude"])
        self.assertEqual(cmd[:3], ["claude", "-p", "x"])
        self.assertEqual(cmd[cmd.index("--model") + 1], "sonnet")
        self.assertEqual(cmd[cmd.index("--allowedTools") + 1], "Read,Grep,Glob,Bash")
        self.assertIn("--output-format", cmd)


class Extract(unittest.TestCase):
    def test_last_json_block(self):
        text = 'blah {"a": 1}\n```json\n{"status": "PASS", "x": {"y": [1]}}\n```'
        self.assertEqual(bench.extract_json(text)["status"], "PASS")

    def test_no_json(self):
        self.assertIsNone(bench.extract_json("no json here"))


class Score(unittest.TestCase):
    def test_hit_needs_fail_file_and_keyword(self):
        issue = {"file": "backend/api/kpi_series.py", "description": "start có múi giờ gây TypeError → 500"}
        self.assertEqual(bench.score(BUG, review("FAIL", [issue])), "caught")

    def test_file_mentioned_in_description_counts(self):
        issue = {"file": "", "description": "backend/api/kpi_series.py:32 so sánh timezone-aware"}
        self.assertEqual(bench.score(BUG, review("FAIL", [issue])), "caught")

    def test_wrong_mechanism_or_file_is_missed(self):
        self.assertEqual(bench.score(BUG, review("FAIL", [{"file": "backend/api/kpi_series.py",
                                                              "description": "thiếu docstring"}])), "missed")
        self.assertEqual(bench.score(BUG, review("FAIL", [{"file": "backend/api/app.py",
                                                              "description": "timezone"}])), "missed")
        self.assertEqual(bench.score(BUG, review("PASS")), "missed")

    def test_clean_case(self):
        self.assertEqual(bench.score(CLEAN, review("PASS")), "clean_pass")
        self.assertEqual(bench.score(CLEAN, review("FAIL", [{"file": "x", "description": "y"}])), "false_alarm")

    def test_no_review_is_run_error(self):
        self.assertEqual(bench.score(BUG, None), "run_error")


class Summary(unittest.TestCase):
    def test_recall_and_false_alarms_per_config(self):
        rows = [
            {"case": "p1", "config": "old", "outcome": "missed", "cost": 0.5, "minutes": 6},
            {"case": "p2", "config": "old", "outcome": "caught", "cost": 0.4, "minutes": 5},
            {"case": "p4", "config": "old", "outcome": "false_alarm", "cost": 0.3, "minutes": 4},
            {"case": "p1", "config": "new", "outcome": "caught", "cost": 0.6, "minutes": 7},
            {"case": "p2", "config": "new", "outcome": "run_error", "cost": 0.1, "minutes": 1},
        ]
        s = bench.summarize(rows)
        self.assertEqual(s["old"]["recall"], "1/2")
        self.assertEqual(s["old"]["false_alarms"], "1/1")
        self.assertEqual(s["new"]["recall"], "1/1")
        self.assertEqual(s["new"]["run_errors"], 1)
        self.assertAlmostEqual(s["new"]["cost"], 0.7)
        self.assertIn("| new | 1/1 |", bench.summary_table(s))


class Cases(unittest.TestCase):
    def test_pilot_cases_file_is_valid(self):
        cases = json.loads((HERE.parent / "bench" / "cases.json").read_text(encoding="utf-8"))
        ids = [c["id"] for c in cases]
        self.assertEqual(len(ids), len(set(ids)))
        for c in cases:
            for k in ("id", "hole", "task_id", "base", "head", "plan", "files", "keywords"):
                self.assertIn(k, c)
            self.assertEqual(bool(c["hole"]), bool(c["files"]) and bool(c["keywords"]))


if __name__ == "__main__":
    unittest.main()
