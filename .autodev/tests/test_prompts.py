"""Rules in the plugin prompts that broke runs when missing (rules as tests, LESSONS 5).

Run: python3 -m unittest discover .autodev/tests
"""

import unittest
from pathlib import Path

CMDS = Path(__file__).resolve().parents[2] / ".claude" / "commands"


class Foreground(unittest.TestCase):
    """R9 2026-10-09: sub-agents default to background; a headless -p session then ends mid-task."""

    def test_commands_that_spawn_agents_require_foreground(self):
        for name in ("run-milestone.md", "audit.md"):
            with self.subTest(cmd=name):
                self.assertIn("run_in_background: false", (CMDS / name).read_text(encoding="utf-8"))

    def test_run_milestone_never_ends_turn_with_open_tasks(self):
        text = (CMDS / "run-milestone.md").read_text(encoding="utf-8")
        self.assertIn("Không kết thúc lượt khi còn task", text)


class AutodevGoal(unittest.TestCase):
    """P10 (design 6.16): rules the /autodev-goal planner must keep."""

    def setUp(self):
        self.text = (CMDS / "autodev-goal.md").read_text(encoding="utf-8")

    def test_writes_the_goal_folder_checks_it_and_opens_a_goal_pr(self):
        for s in ("docs/goals/<slug>/", "goal_check.py", "goal/<slug>", "status: approved"):
            with self.subTest(s=s):
                self.assertIn(s, self.text)

    def test_never_changes_code_or_runs_autodev_or_real_llm(self):
        self.assertIn("Không sửa code dự án, không chạy auto-dev", self.text)

    def test_one_numbered_question_per_message_with_a_recommendation(self):
        self.assertIn("chỉ một câu", self.text)
        self.assertIn("(khuyến nghị)", self.text)

    def test_stops_at_the_roadmap(self):
        self.assertIn("plan mốc (`plan/Rx.md`) là việc của P11", self.text)

    def test_estimates_come_from_measured_runs(self):
        self.assertIn("PROGRESS.md", self.text)


if __name__ == "__main__":
    unittest.main()
