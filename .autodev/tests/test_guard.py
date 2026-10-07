"""Guard: the "on main" check must look at the directory the command targets."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

GUARD = os.path.join(os.path.dirname(__file__), "..", "guard.py")


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def run_guard(command, cwd):
    data = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, GUARD], input=data, text=True, capture_output=True, cwd=cwd
    ).returncode


class GuardTargetDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name
        self.main = os.path.join(base, "main repo")
        self.feat = os.path.join(base, "feat repo")
        for path, branch in ((self.main, "main"), (self.feat, "chore/x")):
            os.makedirs(path)
            git(path, "init", "-q", "-b", branch)

    def tearDown(self):
        self.tmp.cleanup()

    def test_commit_on_main_blocked(self):
        self.assertEqual(run_guard('git commit -m "x"', self.main), 2)

    def test_cd_into_feature_worktree_allowed(self):
        cmd = f'cd "{self.feat}" && git commit -m "x" && git push -q'
        self.assertEqual(run_guard(cmd, self.main), 0)

    def test_git_dash_c_feature_allowed(self):
        cmd = f'git -C "{self.feat}" commit -m "x"'
        self.assertEqual(run_guard(cmd, self.main), 0)

    def test_cd_into_main_from_feature_blocked(self):
        cmd = f'cd "{self.main}" && git commit -m "x"'
        self.assertEqual(run_guard(cmd, self.feat), 2)

    def test_relative_cd_resolved_against_cwd(self):
        cmd = 'cd "../feat repo" && git commit -m "x"'
        self.assertEqual(run_guard(cmd, self.main), 0)


if __name__ == "__main__":
    unittest.main()
