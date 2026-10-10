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


def _diff(path, removed=(), added=(), deleted=False):
    head = f"diff --git a/{path} b/{path}\n"
    head += "deleted file mode 100644\n" if deleted else ""
    head += f"--- a/{path}\n+++ {'/dev/null' if deleted else 'b/' + path}\n@@ -1 +1 @@\n"
    return head + "".join(f"-{ln}\n" for ln in removed) + "".join(f"+{ln}\n" for ln in added)


class TestGuardDiff(unittest.TestCase):
    """Proposal 1 of docs/autodev/research/2026-10-10-so-sanh-ben-ngoai.md: do not get green by loosening tests."""

    def test_clean_change_passes(self):
        d = _diff("tests/test_a.py", ["    assert f() == 1"], ["    assert f() == 2", "def test_new():", "    assert g()"])
        self.assertEqual(verify.weakening(d, set()), [])

    def test_removed_test_function(self):
        d = _diff("tests/test_a.py", ["def test_old():", "    assert x"], ["    assert y"])
        self.assertEqual(verify.weakening(d, set()), ["removed-test:tests/test_a.py::test_old"])

    def test_test_moved_to_another_file_is_not_removed(self):
        d = _diff("tests/test_a.py", ["def test_old():", "    assert x"]) + _diff("tests/test_b.py", [], ["def test_old():", "    assert x"])
        self.assertEqual(verify.weakening(d, set()), [])

    def test_deleted_test_file_reported_once(self):
        d = _diff("tests/test_a.py", ["def test_old():", "    assert x"], deleted=True)
        self.assertEqual(verify.weakening(d, set()), ["deleted-file:tests/test_a.py"])

    def test_added_skip_xfail_only(self):
        d = _diff("tests/test_a.py", [], ["@pytest.mark.skip(reason='later')", "def test_n():", "    assert 1"])
        d += _diff("tests/test_b.py", [], ["@pytest.mark.xfail", "def test_m():", "    pytest.skip('x')"])
        d += _diff("dashboard/tests/c.test.tsx", [], ["it.only('x', () => { expect(1).toBe(1) })"])
        keys = verify.weakening(d, set())
        self.assertEqual(sum(k.startswith("skip:tests/test_a.py") for k in keys), 1)
        self.assertEqual(sum(k.startswith("skip:tests/test_b.py") for k in keys), 2)
        self.assertTrue(any(k.startswith("skip:dashboard/tests/c.test.tsx") for k in keys))

    def test_marker_inside_a_string_is_not_a_skip(self):
        d = _diff("tests/test_a.py", [], ['    data = ["@pytest.mark.skip", "it.only(\'x\')"]', "    assert data"])
        self.assertEqual(verify.weakening(d, set()), [])

    def test_fewer_asserts(self):
        d = _diff("tests/test_a.py", ["    assert a", "    assert b", "    self.assertEqual(c, 1)"], ["    assert a"])
        self.assertEqual(verify.weakening(d, set()), ["fewer-asserts:-2:tests/test_a.py"])
        self.assertEqual(verify.weakening(d, {"tests/test_a.py"}), [])

    def test_non_test_files_ignored(self):
        d = _diff("backend/x.py", ["def test_helper():", "    assert x"], ["@pytest.mark.skip"])
        self.assertEqual(verify.weakening(d, set()), [])

    def test_allowed_by_plan_token(self):
        d = _diff("tests/test_a.py", ["def test_old():", "    assert x"], deleted=True)
        d += _diff("tests/test_b.py", ["def test_gone():", "    assert y"])
        self.assertEqual(verify.weakening(d, {"tests/test_a.py", "test_gone"}), [])

    def test_allow_tokens_need_a_reason(self):
        text = "x\nallow-test-change: tests/test_a.py gộp vào test_b (dev-03)\nallow-test-change: test_c\n"
        self.assertEqual(verify.allow_tokens(text), {"tests/test_a.py"})


class TestGuardGit(unittest.TestCase):
    """End to end on a throwaway repo: base = merge-base with main; allowances only from plan/ at the base."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        (self.cwd / "tests").mkdir()
        (self.cwd / "tests/test_a.py").write_text("def test_a():\n    assert 1\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "base")
        self.git("switch", "-q", "-c", "milestone/X")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        import subprocess
        subprocess.run(["git", *args], cwd=self.cwd, check=True, capture_output=True)

    def test_on_main_nothing_to_check(self):
        self.assertEqual(verify.test_guard(self.cwd), [])

    def test_uncommitted_weakening_is_caught(self):
        (self.cwd / "tests/test_a.py").write_text("import pytest\n@pytest.mark.skip\ndef test_a():\n    assert 1\n")
        self.assertEqual(verify.test_guard(self.cwd), ["skip:tests/test_a.py:@pytest.mark.skip"])

    def test_allowance_added_on_branch_does_not_count(self):
        (self.cwd / "tests/test_a.py").unlink()
        (self.cwd / "plan").mkdir()
        (self.cwd / "plan/X.md").write_text("allow-test-change: tests/test_a.py tự cho phép\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "drop test")
        self.assertEqual(verify.test_guard(self.cwd), ["deleted-file:tests/test_a.py"])

    def test_allowance_on_base_counts(self):
        self.git("switch", "-q", "main")
        (self.cwd / "plan").mkdir()
        (self.cwd / "plan/X.md").write_text("allow-test-change: tests/test_a.py thay bằng test_b (dev-02)\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "plan")
        self.git("switch", "-q", "-c", "milestone/Y")
        (self.cwd / "tests/test_a.py").unlink()
        self.assertEqual(verify.test_guard(self.cwd), [])

    def test_commit_justification_unblocks_but_is_listed(self):
        (self.cwd / "tests/test_a.py").write_text("def test_b():\n    assert 2\n")
        self.git("commit", "-q", "-am", "feat(R1/dev-01): x\n\nallow-test-change: test_a hành vi đổi theo dev-01")
        res = verify.guard_result(self.cwd)
        self.assertEqual(res["keys"], [])
        self.assertEqual(res["justified"], ["removed-test:tests/test_a.py::test_a"])

    def test_guard_result_blocks_with_hint(self):
        (self.cwd / "tests/test_a.py").unlink()
        res = verify.guard_result(self.cwd)
        found = verify.new_errors({"test_guard": res}, {"test_guard": []})
        self.assertEqual(found["test_guard"]["keys"], ["deleted-file:tests/test_a.py"])
        self.assertIn("allow-test-change:", found["test_guard"]["tail"])


if __name__ == "__main__":
    unittest.main()
