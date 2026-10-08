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
        [sys.executable, GUARD], input=data, text=True, capture_output=True, cwd=cwd, check=False
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


class GuardRulesTest(unittest.TestCase):
    """2026-10-08 hardening: destructive variants that slipped through, and baseline tampering."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "r")
        os.makedirs(self.repo)
        git(self.repo, "init", "-q", "-b", "chore/x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_blocked(self):
        for cmd in [
            "gh pr merge 12 --merge -d",
            "rm -r -f build",
            "rm --recursive --force build",
            "rm -fr build",
            "git restore .",
            "git checkout -- .",
            "find . -name '*.pyc' -delete",
            "python3 .autodev/verify.py --snapshot",
            "uv run python .autodev/verify.py --snapshot",
            "echo '{}' > .autodev/baseline.json",
            "sed -i '' 's/x/y/' .autodev/baseline.json",
        ]:
            with self.subTest(cmd=cmd):
                self.assertEqual(run_guard(cmd, self.repo), 2)

    def test_allowed(self):
        for cmd in [
            "gh pr merge 12 --merge",
            "rm build/out.txt",
            "git restore src/a.py",
            "find . -name '*.pyc'",
            "python3 .autodev/verify.py --smoke",
            "cat .autodev/baseline.json",
        ]:
            with self.subTest(cmd=cmd):
                self.assertEqual(run_guard(cmd, self.repo), 0)


if __name__ == "__main__":
    unittest.main()
