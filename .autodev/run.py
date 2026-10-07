# ruff: noqa: DTZ005, DTZ006, FLY002  (usage-limit reset times are local wall-clock times, so naive local datetimes are intended)
"""Mode B runner (plugin milestone P4): run several milestones unattended.

For each milestone: move the worker worktree to origin/main -> worker headless (/run-milestone)
-> check the worker opened a PR -> supervisor headless review (/supervise <M> --review-only,
which merges) -> check the PR is merged -> next milestone. A macOS notification is sent when
the run stops or finishes.

Usage-limit handling (ROADMAP P4, approved 2026-10-08):
  1. detect the limit message in the run result, read the reset time;
  2. wait until reset + 5 minutes (unparsable reset time: wait 30 minutes);
  3. re-run the same step in a NEW session (state lives in files, so it resumes);
  4. weekly limit: stop, write .autodev/runs/STOPPED.md, exit 3.

Stdlib only (runs on the system python3, which may be 3.9). Never deletes anything.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".autodev" / "runs"
RESET_MARGIN = dt.timedelta(minutes=5)
UNKNOWN_RESET_WAIT = dt.timedelta(minutes=30)
MAX_LIMIT_WAITS = 6
MAX_ERROR_RETRIES = 1

LIMIT_RE = re.compile(r"(hit|reached|exceeded)[^.\n]{0,40}\blimit\b|usage limit|rate[_ ]limit", re.IGNORECASE)
WEEKLY_RE = re.compile(r"weekly|week(ly)?\s+limit|7-day", re.IGNORECASE)
RESET_RE = re.compile(r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?", re.IGNORECASE)

WORKER_ALLOWED = ""  # worker uses the worktree's .claude/settings.local.json
SUPERVISOR_ALLOWED = ",".join(
    [
        "Bash(gh pr view *)",
        "Bash(gh pr diff *)",
        "Bash(gh pr list *)",
        "Bash(gh pr create *)",
        "Bash(gh pr merge *)",
        "Bash(git fetch *)",
        "Bash(git switch *)",
        "Bash(git add *)",
        "Bash(git commit *)",
        "Bash(git push -u origin chore/*)",
        "Bash(git push origin chore/*)",
        "Bash(uv run *)",
        "Bash(python3 *)",
    ]
)


# ---------------------------------------------------------------- classification


def classify(result: dict, stderr: str = "") -> tuple[str, str]:
    """Return (kind, text). kind: ok | usage_limit | weekly_limit | error."""
    text = f"{result.get('result', '')}\n{stderr}"
    if LIMIT_RE.search(text):
        return ("weekly_limit" if WEEKLY_RE.search(text) else "usage_limit"), text
    if result.get("is_error") or result.get("_exit", 0) != 0:
        return "error", text
    return "ok", text


def reset_time(text: str, now: dt.datetime) -> dt.datetime | None:
    """Next local time matching 'resets 3:45pm' / 'resets 15:00' after now."""
    m = RESET_RE.search(text)
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ampm.startswith("p") and hour < 12:
        hour += 12
    if ampm.startswith("a") and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    t = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if t <= now:
        t += dt.timedelta(days=1)
    return t


def wait_seconds(text: str, now: dt.datetime) -> float:
    t = reset_time(text, now)
    target = (t + RESET_MARGIN) if t else (now + UNKNOWN_RESET_WAIT)
    return max(0.0, (target - now).total_seconds())


# ---------------------------------------------------------------- running claude


def claude_cmd() -> list[str]:
    return shlex.split(os.environ.get("AUTODEV_CLAUDE", "claude"))


def run_claude(prompt: str, cwd: Path, allowed: str, label: str) -> dict:
    cmd = claude_cmd() + [
        "-p", prompt,
        "--model", os.environ.get("AUTODEV_MODEL", "sonnet"),
        "--permission-mode", "auto",
        "--permission-prompts", "none",
        "--output-format", "json",
    ]
    if allowed:
        cmd += ["--allowedTools", allowed]
    log(f"start {label}: {prompt} (cwd={cwd})")
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    try:
        result = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        result = {"result": proc.stdout[-2000:], "is_error": True}
    result["_exit"] = proc.returncode
    result["_stderr"] = proc.stderr[-2000:]
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    save(RUNS / f"{stamp}-{label}.json", result)
    log(f"end {label}: exit={proc.returncode} cost={result.get('total_cost_usd')}")
    return result


def run_step(prompt: str, cwd: Path, allowed: str, label: str, sleeper=time.sleep, clock=None) -> dict:
    """Run one step; handle usage limits and one retry on error."""
    clock = clock or dt.datetime.now
    waits = errors = 0
    while True:
        result = run_claude(prompt, cwd, allowed, label)
        kind, text = classify(result, result.get("_stderr", ""))
        if kind == "ok":
            return result
        if kind == "weekly_limit":
            stop(f"Hết hạn mức tuần ở bước {label}.\n\n{text[-1000:]}", 3)
        if kind == "usage_limit":
            waits += 1
            if waits > MAX_LIMIT_WAITS:
                stop(f"Chạm hạn mức {waits - 1} lần liên tiếp ở bước {label}.", 3)
            secs = wait_seconds(text, clock())
            log(f"usage limit at {label}; waiting {int(secs // 60)} min then re-running")
            sleeper(secs)
            continue
        errors += 1
        if errors > MAX_ERROR_RETRIES:
            stop(f"Bước {label} lỗi.\n\n{text[-1500:]}", 2)
        log(f"error at {label}; retry in 2 min")
        sleeper(120)


# ---------------------------------------------------------------- helpers


def log(msg: str) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(RUNS / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def notify(title: str, message: str) -> None:
    """One-way macOS notification (Q1). Off with AUTODEV_NOTIFY=0 or on other systems."""
    if os.environ.get("AUTODEV_NOTIFY", "1") == "0" or sys.platform != "darwin":
        return
    script = f"display notification {json.dumps(message[:200])} with title {json.dumps(title)} sound name \"Glass\""
    subprocess.run(["osascript", "-e", script], capture_output=True, check=False)


def stop(reason: str, code: int) -> None:
    save_text = f"# Dừng lúc {dt.datetime.now():%Y-%m-%d %H:%M}\n\n{reason}\n"
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / "STOPPED.md").write_text(save_text, encoding="utf-8")
    log(f"STOP (exit {code}): {reason.splitlines()[0]}")
    notify(f"auto-dev dừng (exit {code})", reason.splitlines()[0])
    sys.exit(code)


def archive_stopped() -> None:
    """Keep an old STOPPED.md from an earlier run under a timestamped name (never delete)."""
    old = RUNS / "STOPPED.md"
    if old.exists():
        stamp = dt.datetime.fromtimestamp(old.stat().st_mtime).strftime("%Y%m%d-%H%M%S")
        old.rename(RUNS / f"STOPPED-{stamp}.md")


def git_out(cwd: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def prepare_worker(milestone: str, worker: Path) -> None:
    """Put the worker worktree on origin/main before /run-milestone (it reads plan/<M>.md first).

    An unmerged milestone/<M> branch (resume after a stop) is kept; a dirty worktree stops the run.
    """
    code, out = git_out(worker, "fetch", "-q", "origin")
    if code:
        stop(f"git fetch ở worktree worker lỗi:\n\n{out}", 2)
    _, dirty = git_out(worker, "status", "--porcelain")
    if dirty:
        stop(f"Worktree worker {worker} có thay đổi chưa commit; cần người xem trước khi chạy {milestone}.\n\n{dirty}", 2)
    _, branch = git_out(worker, "branch", "--show-current")
    _, ahead = git_out(worker, "log", "--oneline", "origin/main..HEAD")
    if has_milestone_head([branch], milestone) and ahead:
        log(f"worker giữ nhánh {branch} (còn commit chưa merge)")
    else:
        code, out = git_out(worker, "switch", "-q", "--detach", "origin/main")
        if code:
            stop(f"Không chuyển được worktree worker về origin/main:\n\n{out}", 2)
        log(f"worker chuyển về origin/main (trước đó: {branch or 'detached'})")
    if not (worker / "plan" / f"{milestone}.md").exists():
        stop(f"Không có plan/{milestone}.md trong worktree worker (sau khi cập nhật từ origin/main).", 2)


def has_milestone_head(heads: list[str], milestone: str) -> bool:
    return any(h == f"milestone/{milestone}" or h.startswith(f"milestone/{milestone}-r") for h in heads)


def pr_heads(cwd: Path, state: str) -> list[str]:
    out = subprocess.run(
        ["gh", "pr", "list", "--state", state, "--json", "headRefName", "--limit", "50"],
        cwd=cwd, capture_output=True, text=True, check=False,
    ).stdout
    try:
        return [p["headRefName"] for p in json.loads(out or "[]")]
    except json.JSONDecodeError:
        return []


def pr_merged(milestone: str, cwd: Path) -> bool:
    return has_milestone_head(pr_heads(cwd, "merged"), milestone)


# ---------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("milestones", nargs="+", help="ví dụ: R4 R5")
    ap.add_argument("--worker-dir", default=str(ROOT.parent / f"{ROOT.name}-autodev"))
    ap.add_argument("--supervisor-dir", default=str(ROOT.parent / f"{ROOT.name}-supervisor"))
    ap.add_argument("--skip-merge-check", action="store_true", help="chỉ dùng khi thử nghiệm")
    args = ap.parse_args(argv)

    worker, supervisor = Path(args.worker_dir), Path(args.supervisor_dir)
    for d in (worker, supervisor):
        if not d.is_dir():
            stop(f"Thiếu worktree {d}. Tạo bằng git worktree add (xem docs/autodev/HANDOFF.md).", 2)

    archive_stopped()
    total = 0.0
    for m in args.milestones:
        prepare_worker(m, worker)
        w = run_step(f"/run-milestone {m}", worker, WORKER_ALLOWED, f"{m}-worker")
        if not args.skip_merge_check and not has_milestone_head(pr_heads(worker, "all"), m):
            stop(f"Worker {m} kết thúc mà không mở PR (có thể không làm gì); không chuyển sang supervisor.\n\n{w.get('result', '')[-1500:]}", 4)
        s = run_step(f"/supervise {m} --review-only", supervisor, SUPERVISOR_ALLOWED, f"{m}-supervisor")
        total += float(w.get("total_cost_usd") or 0) + float(s.get("total_cost_usd") or 0)
        if not args.skip_merge_check and not pr_merged(m, supervisor):
            stop(f"PR của {m} chưa merge sau bước supervisor; cần xem báo cáo.\n\n{s.get('result', '')[-1500:]}", 4)
        log(f"{m} xong; tổng chi phí ước tính đến giờ {total:.2f} USD")
    log(f"Hoàn tất {' '.join(args.milestones)}; tổng chi phí ước tính {total:.2f} USD")
    notify("auto-dev xong", f"{' '.join(args.milestones)} đã merge; ~{total:.2f} USD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
