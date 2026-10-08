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


if __name__ == "__main__":
    unittest.main()
