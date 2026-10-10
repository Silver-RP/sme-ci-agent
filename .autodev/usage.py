"""Log the leader's plan usage (% of the 5-hour and weekly limits) before and after each task.

    python3 .autodev/usage.py start "<task>" [--est "<minutes / USD>"]   # at the start of a task
    python3 .autodev/usage.py end                                        # at the end: prints the change
    python3 .autodev/usage.py show [--last N]                            # current % and the last N logged tasks

Reads ~/.claude/usage-latest.json, written by the status line script (~/.claude/statusline-usage.sh) from the
`rate_limits` fields Claude Code gives it; the values are as of the last status line refresh. Appends one row to
.autodev/runs/usage-log.md (gitignored, main worktree). Stdlib only (python3.9).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

LATEST = Path.home() / ".claude" / "usage-latest.json"
LOG = Path(__file__).resolve().parent / "runs" / "usage-log.md"
OPEN = Path(__file__).resolve().parent / "runs" / "usage-open.json"
STALE_MINUTES = 30
HEADER = (
    "| Bắt đầu | Nhiệm vụ | Ước tính | Phút | 5h trước → sau (Δ) | Tuần trước → sau (Δ) |\n"
    "|---|---|---|---|---|---|\n"
)


def read_latest(path: Path = LATEST) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if data.get("five_hour") is not None else None


def age_note(latest: dict | None, now: float | None = None) -> str:
    """How old the snapshot is; asks for /usage when the status line has not refreshed recently."""
    at = (latest or {}).get("at")
    if at is None:
        return "không rõ thời điểm số liệu: hỏi leader 2 số từ /usage"
    minutes = round(((now if now is not None else time.time()) - at) / 60)
    note = f"số liệu {minutes} phút trước"
    if minutes > STALE_MINUTES:
        note += " (cũ: status line chỉ chạy trong terminal; hỏi leader 2 số từ /usage)"
    return note


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0f}%"


def _delta(a: float | None, b: float | None) -> str:
    if a is None or b is None:
        return f"{_pct(a)} → {_pct(b)}"
    d = b - a
    note = " (cửa sổ đã reset)" if d < 0 else ""
    return f"{_pct(a)} → {_pct(b)} ({d:+.0f}){note}"


def start(task: str, est: str, latest: dict | None, open_path: Path = OPEN) -> str:
    now = dt.datetime.now().astimezone()
    row = {"task": task, "est": est, "started": now.isoformat(timespec="minutes"),
           "five_hour": (latest or {}).get("five_hour"), "seven_day": (latest or {}).get("seven_day")}
    open_path.parent.mkdir(parents=True, exist_ok=True)
    open_path.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
    return (f"Bắt đầu \"{task}\": 5h {_pct(row['five_hour'])}, tuần {_pct(row['seven_day'])}"
            f" ({age_note(latest)})")


def end(latest: dict | None, open_path: Path = OPEN, log_path: Path = LOG) -> str:
    if not open_path.exists():
        return "Chưa có nhiệm vụ nào đang mở (chạy `start` trước)."
    row = json.loads(open_path.read_text(encoding="utf-8"))
    began = dt.datetime.fromisoformat(row["started"])
    minutes = round((dt.datetime.now().astimezone() - began).total_seconds() / 60)
    five, week = (latest or {}).get("five_hour"), (latest or {}).get("seven_day")
    line = (f"| {began:%Y-%m-%d %H:%M} | {row['task']} | {row['est'] or '–'} | {minutes} | "
            f"{_delta(row['five_hour'], five)} | {_delta(row['seven_day'], week)} |\n")
    if not log_path.exists():
        log_path.write_text("# Hạn mức theo nhiệm vụ (tự ghi bởi .autodev/usage.py)\n\n" + HEADER, encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)
    open_path.unlink()
    return (f"Xong \"{row['task']}\" sau {minutes} phút: 5h {_delta(row['five_hour'], five)}, "
            f"tuần {_delta(row['seven_day'], week)} ({age_note(latest)})")


def show(latest: dict | None, log_path: Path = LOG, now: float | None = None, last: int = 10) -> str:
    current = (f"Hiện tại: 5h {_pct((latest or {}).get('five_hour'))}, tuần {_pct((latest or {}).get('seven_day'))}"
               f" ({age_note(latest, now)})")
    if not log_path.exists():
        return f"{current}\nchưa có lịch sử ({log_path})"
    rows = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.startswith("| 2")]
    return f"{current}\nLịch sử ({len(rows)} dòng, {last} dòng cuối; đủ ở {log_path}):\n{HEADER}" + "\n".join(rows[-last:])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("task")
    s.add_argument("--est", default="")
    sub.add_parser("end")
    sh = sub.add_parser("show")
    sh.add_argument("--last", type=int, default=10)
    args = ap.parse_args(argv)
    latest = read_latest()
    if latest is None:
        print("Chưa có ~/.claude/usage-latest.json (status line chưa chạy hoặc không có rate_limits); ghi –.")
    if args.cmd == "show":
        print(show(latest, last=args.last))
    else:
        print(start(args.task, args.est, latest) if args.cmd == "start" else end(latest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
