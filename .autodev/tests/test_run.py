# ruff: noqa: DTZ001, UP017  (usage-limit reset times are local wall-clock times, so naive local datetimes are intended)
"""Tests for .autodev/run.py (mode B runner). Run: python3 -m unittest discover .autodev/tests

Uses a fake `claude` (AUTODEV_CLAUDE) so no quota is used and no network is needed.
"""

import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["AUTODEV_NOTIFY"] = "0"  # no real macOS notifications from tests
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
        limit = "You've hit your session limit · resets 4pm"
        self.assertEqual(run.classify({"result": limit, "is_error": True})[0], "usage_limit")
        self.assertEqual(run.classify({"result": "You've hit your weekly limit", "_exit": 1})[0], "weekly_limit")
        # a successful report that mentions limits must not make the runner wait (2026-10-08 hardening)
        self.assertEqual(run.classify({"result": "Tăng retry khi gặp rate limit; weekly report xong."})[0], "ok")
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


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class PrepareWorker(unittest.TestCase):
    """The worker worktree is moved to origin/main before /run-milestone (R4 no-op, 2026-10-08)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.old_runs = run.RUNS
        run.RUNS = base / "runs"
        origin, seed = base / "origin.git", base / "seed"
        git(base, "init", "-q", "--bare", "-b", "main", str(origin))
        git(base, "clone", "-q", str(origin), str(seed))
        for args in (("config", "user.email", "t@t"), ("config", "user.name", "t")):
            git(seed, *args)
        (seed / "plan").mkdir()
        (seed / "plan" / "M1.md").write_text("old\n")
        git(seed, "add", ".")
        git(seed, "commit", "-q", "-m", "init")
        git(seed, "push", "-q", "origin", "main")
        self.worker = base / "worker"
        git(base, "clone", "-q", str(origin), str(self.worker))
        for args in (("config", "user.email", "t@t"), ("config", "user.name", "t")):
            git(self.worker, *args)
        git(self.worker, "switch", "-q", "-c", "milestone/M1")
        # main moves on: plan for R4 lands after the worker last synced
        (seed / "plan" / "R4.md").write_text("new\n")
        git(seed, "add", ".")
        git(seed, "commit", "-q", "-m", "plan R4")
        git(seed, "push", "-q", "origin", "main")
        self.seed = seed

    def tearDown(self):
        run.RUNS = self.old_runs
        self.tmp.cleanup()

    def test_stale_worktree_moved_to_origin_main(self):
        run.prepare_worker("R4", self.worker)
        self.assertTrue((self.worker / "plan" / "R4.md").exists())
        self.assertEqual(git(self.worker, "rev-parse", "HEAD"), git(self.seed, "rev-parse", "HEAD"))

    def test_unmerged_branch_of_same_milestone_kept(self):
        git(self.worker, "fetch", "-q", "origin")
        git(self.worker, "switch", "-q", "-c", "milestone/R4", "origin/main")
        (self.worker / "work.txt").write_text("wip\n")
        git(self.worker, "add", ".")
        git(self.worker, "commit", "-q", "-m", "wip")
        head = git(self.worker, "rev-parse", "HEAD")
        run.prepare_worker("R4", self.worker)
        self.assertEqual(git(self.worker, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.worker, "branch", "--show-current"), "milestone/R4")

    def test_dirty_worktree_stops(self):
        (self.worker / "plan" / "M1.md").write_text("edited\n")
        with self.assertRaises(SystemExit) as cm:
            run.prepare_worker("R4", self.worker)
        self.assertEqual(cm.exception.code, 2)

    def test_missing_plan_stops(self):
        with self.assertRaises(SystemExit) as cm:
            run.prepare_worker("R9", self.worker)
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("plan/R9.md", (run.RUNS / "STOPPED.md").read_text())


class Helpers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_runs = run.RUNS
        run.RUNS = Path(self.tmp.name) / "runs"

    def tearDown(self):
        run.RUNS = self.old_runs
        self.tmp.cleanup()

    def test_old_stopped_file_archived_not_deleted(self):
        run.RUNS.mkdir(parents=True)
        (run.RUNS / "STOPPED.md").write_text("old stop\n")
        run.archive_stopped()
        self.assertFalse((run.RUNS / "STOPPED.md").exists())
        archived = list(run.RUNS.glob("STOPPED-*.md"))
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0].read_text(), "old stop\n")

    def test_milestone_pr_match(self):
        heads = ["chore/x", "milestone/R4-r2", "milestone/R40"]
        self.assertTrue(run.has_milestone_head(heads, "R4"))
        self.assertFalse(run.has_milestone_head(heads, "R5"))
        self.assertFalse(run.has_milestone_head(["milestone/R40"], "R4"))


class Hardening(unittest.TestCase):
    """2026-10-08: per-role model/effort, PR of this run only, auto-merge of docs-only chore PRs."""

    def test_cmd_has_model_and_effort(self):
        cmd = run.build_cmd("/supervise R8 --review-only", "", model="opus", effort="medium")
        self.assertEqual(cmd[cmd.index("--model") + 1], "opus")
        self.assertEqual(cmd[cmd.index("--effort") + 1], "medium")
        self.assertNotIn("--effort", run.build_cmd("/run-milestone R8", "", model="sonnet", effort=""))

    def test_role_defaults(self):
        for k in ("AUTODEV_WORKER_MODEL", "AUTODEV_SUPERVISOR_MODEL", "AUTODEV_SUPERVISOR_EFFORT", "AUTODEV_MODEL"):
            os.environ.pop(k, None)
        self.assertEqual(run.role_model("worker"), ("sonnet", ""))
        self.assertEqual(run.role_model("supervisor"), ("opus", "medium"))
        os.environ["AUTODEV_SUPERVISOR_MODEL"] = "sonnet"
        os.environ["AUTODEV_SUPERVISOR_EFFORT"] = "high"
        try:
            self.assertEqual(run.role_model("supervisor"), ("sonnet", "high"))
        finally:
            os.environ.pop("AUTODEV_SUPERVISOR_MODEL")
            os.environ.pop("AUTODEV_SUPERVISOR_EFFORT")

    def test_only_prs_created_after_step_start_count(self):
        since = dt.datetime(2026, 10, 8, 22, 0, tzinfo=dt.timezone.utc)
        prs = [
            {"number": 19, "headRefName": "milestone/R4", "createdAt": "2026-10-07T16:00:00Z", "state": "MERGED"},
            {"number": 40, "headRefName": "milestone/R4-r2", "createdAt": "2026-10-08T22:30:00Z", "state": "OPEN"},
            {"number": 41, "headRefName": "milestone/R40", "createdAt": "2026-10-08T22:31:00Z", "state": "OPEN"},
        ]
        self.assertEqual(run.new_milestone_pr(prs, "R4", since)["number"], 40)
        self.assertIsNone(run.new_milestone_pr(prs[:1], "R4", since))

    def test_docs_only(self):
        self.assertTrue(run.docs_only(["docs/autodev/PROGRESS.md", "docs/autodev/HANDOFF.md"]))
        self.assertFalse(run.docs_only(["docs/autodev/PROGRESS.md", "plan/R8.md"]))
        self.assertFalse(run.docs_only([]))

    def test_docs_only_accepts_audit_reports(self):
        self.assertTrue(run.docs_only(["docs/audits/2026-10-09.md", "docs/autodev/PROJECT_STATE.md"]))
        self.assertFalse(run.docs_only(["docs/audits/2026-10-09.md", "backend/x.py"]))


class ResumeUnfinished(unittest.TestCase):
    """R9 2026-10-09: worker -p session ended while a background sub-agent was still working."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.worker = Path(self.tmp.name)
        (self.worker / ".autodev").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def state(self, milestone, statuses):
        tasks = {f"dev-0{i + 1}": {"status": s} for i, s in enumerate(statuses)}
        (self.worker / ".autodev" / "state.json").write_text(json.dumps({"milestone": milestone, "tasks": tasks}))

    def test_open_tasks_count(self):
        self.state("R9", ["DONE", "IN_PROGRESS", "TODO"])
        self.assertEqual(run.unfinished_tasks(self.worker, "R9"), ["dev-02", "dev-03"])

    def test_done_or_blocked_is_finished(self):
        self.state("R9", ["DONE", "BLOCKED"])
        self.assertEqual(run.unfinished_tasks(self.worker, "R9"), [])

    def test_other_milestone_or_missing_state(self):
        self.state("R8", ["TODO"])
        self.assertEqual(run.unfinished_tasks(self.worker, "R9"), [])
        (self.worker / ".autodev" / "state.json").write_text("{bad")
        self.assertEqual(run.unfinished_tasks(self.worker, "R9"), [])


class AuditEvery(unittest.TestCase):
    """P5: a headless /audit runs after every N merged R milestones (counter survives across runs)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.old = (run.RUNS, run.run_step, run.prepare_worker, run.merge_docs_chore_prs)
        run.RUNS = base / "runs"
        self.prompts = []
        run.run_step = lambda prompt, cwd, allowed, label, **kw: self.prompts.append(prompt) or {"total_cost_usd": 0.1}
        run.prepare_worker = lambda m, w: None
        run.merge_docs_chore_prs = lambda cwd, since: None
        self.dirs = [f"--worker-dir={base}", f"--supervisor-dir={base}", "--skip-merge-check"]
        os.environ.pop("AUTODEV_AUDIT_EVERY", None)

    def tearDown(self):
        run.RUNS, run.run_step, run.prepare_worker, run.merge_docs_chore_prs = self.old
        os.environ.pop("AUTODEV_AUDIT_EVERY", None)
        self.tmp.cleanup()

    def audits(self):
        return [p for p in self.prompts if p.startswith("/audit")]

    def test_default_every_two(self):
        run.main(["R9", "R10", "R11", *self.dirs])
        self.assertEqual(self.audits(), ["/audit R9 R10"])
        self.assertEqual(self.prompts.index("/audit R9 R10"), 4)  # after R10's supervisor step
        self.assertEqual(run.audit_pending(), ["R11"])

    def test_counter_survives_runs(self):
        run.main(["R9", *self.dirs])
        self.assertEqual(self.audits(), [])
        run.main(["R10", *self.dirs])
        self.assertEqual(self.audits(), ["/audit R9 R10"])
        self.assertEqual(run.audit_pending(), [])

    def test_disabled_with_zero(self):
        run.main(["R9", "R10", "--audit-every", "0", *self.dirs])
        self.assertEqual(self.audits(), [])

    def test_env_default(self):
        os.environ["AUTODEV_AUDIT_EVERY"] = "1"
        run.main(["R9", "R10", *self.dirs])
        self.assertEqual(self.audits(), ["/audit R9", "/audit R10"])

    def test_audit_only(self):
        run.main(["--audit-only", *self.dirs])
        self.assertEqual(self.prompts, ["/audit"])


if __name__ == "__main__":
    unittest.main()
