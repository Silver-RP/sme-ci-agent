"""Reviewer bench (proposal 4): replay old tasks whose bugs escaped review and measure recall per reviewer config.

    python3 .autodev/bench_reviewer.py run --cases p1,p2 --configs old,new [--dry-run] [--max-usd 6]
    python3 .autodev/bench_reviewer.py summary .autodev/runs/bench/<stamp>.json

Cases: .autodev/bench/cases.json (task range base..head, the hole and its answer: files + keyword regex).
Configs: .autodev/bench/configs.json (reviewer prompt at a git ref, or the current file; model).
Each run checks out `head` in the fixed worktree ../<repo>-bench and calls `claude -p` headless with the
reviewer body + the case input (never the answer). Results go to .autodev/runs/bench/ (gitignored), saved
after every run so a kill keeps what finished. Design: docs/autodev/research/2026-10-10-bo-thu-reviewer.md.
Stdlib only. Real runs cost money: ask the leader before each `run` without --dry-run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

AUTODEV = Path(__file__).resolve().parent
ROOT = AUTODEV.parent
BENCH = AUTODEV / "bench"
OUT = AUTODEV / "runs" / "bench"
WORKTREE = ROOT.parent / f"{ROOT.name}-bench"
REVIEWER = ".claude/agents/reviewer.md"
TOOLS = "Read,Grep,Glob,Bash"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5:].lstrip("\n")
    return text


def build_prompt(body: str, case: dict) -> str:
    return (
        f"{body.rstrip()}\n\n## Đầu vào của lượt này\n"
        f"- task_id: {case['task_id']}\n"
        f"- khoảng commit: {case['base']}..HEAD (HEAD = {case['head']}, đang checkout tách rời)\n"
        f"- plan: {case['plan']}\n"
        "Làm đủ các bước bắt buộc rồi trả về đúng MỘT khối JSON theo schema.\n"
    )


def claude_cmd() -> list[str]:
    return shlex.split(os.environ.get("AUTODEV_CLAUDE", "claude"))


def build_cmd(prompt: str, model: str, base_cmd: list[str] | None = None) -> list[str]:
    return (base_cmd or claude_cmd()) + [
        "-p", prompt,
        "--model", model,
        "--permission-mode", "auto",
        "--permission-prompts", "none",
        "--output-format", "json",
        "--allowedTools", TOOLS,
    ]


def extract_json(text: str) -> dict | None:
    """The last top-level JSON object in the text that has a `status` key."""
    found, depth, start = None, 0, None
    for i, ch in enumerate(text or ""):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                except ValueError:
                    continue
                if isinstance(obj, dict) and "status" in obj:
                    found = obj
    return found


def score(case: dict, review: dict | None) -> str:
    if review is None:
        return "run_error"
    failed = str(review.get("status", "")).upper() == "FAIL"
    if not case.get("hole"):
        return "false_alarm" if failed else "clean_pass"
    if not failed:
        return "missed"
    kw = re.compile(case["keywords"], re.IGNORECASE)
    for issue in review.get("blocking_issues") or []:
        text = f"{issue.get('description', '')} {issue.get('required_action', '')}"
        where = f"{issue.get('file', '')} {text}"
        if any(f in where for f in case["files"]) and kw.search(text):
            return "caught"
    return "missed"


def summarize(rows: list[dict]) -> dict:
    out: dict = {}
    for r in rows:
        s = out.setdefault(r["config"], {"caught": 0, "bugs": 0, "alarms": 0, "clean": 0, "run_errors": 0,
                                         "cost": 0.0, "minutes": 0.0})
        s["cost"] += r.get("cost") or 0.0
        s["minutes"] += r.get("minutes") or 0.0
        o = r["outcome"]
        if o == "run_error":
            s["run_errors"] += 1
        elif o in ("caught", "missed"):
            s["bugs"] += 1
            s["caught"] += o == "caught"
        else:
            s["clean"] += 1
            s["alarms"] += o == "false_alarm"
    for s in out.values():
        s["recall"] = f"{s['caught']}/{s['bugs']}"
        s["false_alarms"] = f"{s['alarms']}/{s['clean']}"
    return out


def summary_table(s: dict) -> str:
    lines = ["| Cấu hình | Recall | Bắt nhầm | Lỗi chạy | USD | Phút |", "|---|---|---|---|---|---|"]
    for name, v in s.items():
        lines.append(f"| {name} | {v['recall']} | {v['false_alarms']} | {v['run_errors']} | "
                     f"{v['cost']:.2f} | {v['minutes']:.0f} |")
    return "\n".join(lines)


def reviewer_body(config: dict) -> str:
    ref = config.get("prompt_ref")
    if ref:
        text = subprocess.run(["git", "show", f"{ref}:{REVIEWER}"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout
    else:
        text = (ROOT / REVIEWER).read_text(encoding="utf-8")
    return strip_frontmatter(text)


def checkout(head: str) -> None:
    if not WORKTREE.exists():
        subprocess.run(["git", "worktree", "add", "-q", "--detach", str(WORKTREE), head], cwd=ROOT, check=True)
    else:
        subprocess.run(["git", "checkout", "-q", "-f", "--detach", head], cwd=WORKTREE, check=True)


def run(case_ids: list[str], config_names: list[str], dry: bool, max_usd: float) -> int:
    cases = {c["id"]: c for c in load_json(BENCH / "cases.json")}
    configs = load_json(BENCH / "configs.json")
    missing = [c for c in case_ids if c not in cases] + [c for c in config_names if c not in configs]
    if missing:
        print(f"Không có ca/cấu hình: {missing}", file=sys.stderr)
        return 1
    plan = [(cases[c], n) for c in case_ids for n in config_names]
    if dry:
        for case, name in plan:
            cmd = build_cmd("<reviewer.md + đầu vào>", configs[name]["model"])
            print(f"{case['id']} × {name}: checkout {case['head']} trong {WORKTREE}; {shlex.join(cmd)}")
        print(f"{len(plan)} lượt; ước ~0,4–0,6 USD/lượt Sonnet, 5–10 phút/lượt")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    rows: list[dict] = []
    for case, name in plan:
        spent = sum(r.get("cost") or 0.0 for r in rows)
        if spent >= max_usd:
            print(f"Dừng: đã tiêu {spent:.2f} USD ≥ --max-usd {max_usd}")
            break
        checkout(case["head"])
        started = time.time()
        proc = subprocess.run(build_cmd(build_prompt(reviewer_body(configs[name]), case), configs[name]["model"]),
                              cwd=WORKTREE, capture_output=True, text=True, check=False)
        try:
            result = json.loads(proc.stdout or "{}")
        except ValueError:
            result = {"result": proc.stdout[-4000:]}
        review = extract_json(result.get("result", ""))
        row = {"case": case["id"], "hole": case["hole"], "config": name, "outcome": score(case, review),
               "cost": result.get("total_cost_usd"), "minutes": round((time.time() - started) / 60, 1),
               "exit": proc.returncode, "review": review, "raw_tail": (result.get("result") or "")[-1500:],
               "stderr_tail": proc.stderr[-800:]}
        rows.append(row)
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{case['id']} × {name}: {row['outcome']} ({row['cost']} USD, {row['minutes']} phút)", flush=True)
    print(summary_table(summarize(rows)))
    print(f"Kết quả: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--cases", required=True)
    r.add_argument("--configs", required=True)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--max-usd", type=float, default=6.0)
    s = sub.add_parser("summary")
    s.add_argument("file")
    args = ap.parse_args(argv)
    if args.cmd == "summary":
        print(summary_table(summarize(load_json(Path(args.file)))))
        return 0
    return run(args.cases.split(","), args.configs.split(","), args.dry_run, args.max_usd)


if __name__ == "__main__":
    sys.exit(main())
