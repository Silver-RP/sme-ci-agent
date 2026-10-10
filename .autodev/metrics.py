"""Measurable plugin metrics (plugin milestone P6b): B1-B5 from files already in the repo.

    python3 .autodev/metrics.py           # print the report
    python3 .autodev/metrics.py --write   # also replace the marked section of docs/autodev/PROGRESS.md

Sources (read only):
  - plan/*.md: tasks (### dev-xx), review rounds ("**Số vòng:** N"), the "## Ước tính" table (P6a);
  - .autodev/runs/<stamp>-<milestone>-<role>.json: total_cost_usd, duration_ms, num_turns;
  - .autodev/runs/run.log: "STOP (exit N)" lines while a milestone runs (B4: a person had to step in);
    runs/ is gitignored, so a linked worktree (the supervisor's) reads the main worktree's runs/ (see runs_dir);
  - docs/audits/*.md: the "- Mốc:" scope line and the H-xx rows (B1: escaped defects).

Definitions: docs/autodev/ROADMAP.md, table B. Stdlib only (runs on python3.9). Never deletes anything.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- metrics:start (tự sinh bởi .autodev/metrics.py, đừng sửa tay) -->"
END = "<!-- metrics:end -->"

TASK_RE = re.compile(r"^### dev-\d+", re.MULTILINE)
ROUNDS_RE = re.compile(r"\*\*Số vòng:\*\*\s*(\d+)")
RANGE_RE = re.compile(r"(\d+(?:[.,]\d+)?)(?:\s*[–-]\s*(\d+(?:[.,]\d+)?))?")
RUN_FILE_RE = re.compile(r"^\d{8}-\d{6}-(.+)-(worker|supervisor)\.json$")
LOG_START_RE = re.compile(r"\bstart (\S+)-(worker|supervisor):")
LOG_END_RE = re.compile(r"\bend \S+-(?:worker|supervisor):")
SCOPE_RE = re.compile(r"\b([RM]\d+[a-z]*)\b")
GAP_RE = re.compile(r"^\|\s*(H-\d+)\s*\|\s*(cao|vừa|thấp)\s*\|")


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def parse_range(cell: str) -> tuple[float, float] | None:
    m = RANGE_RE.search(cell)
    if not m:
        return None
    lo = _num(m.group(1))
    return (lo, _num(m.group(2)) if m.group(2) else lo)


def parse_estimate(text: str) -> dict | None:
    """Minutes and USD ranges from the first data row of the "## Ước tính" table."""
    part = text.split("## Ước tính", 1)
    if len(part) < 2:
        return None
    rows = [ln for ln in part[1].splitlines() if ln.startswith("|")]
    if len(rows) < 3:
        return None
    cells = [c.strip() for c in rows[2].strip("|").split("|")]
    if len(cells) < 3:
        return None
    return {"minutes": parse_range(cells[1]), "usd": parse_range(cells[2])}


def ratio(actual: float, est: tuple[float, float] | None) -> float | None:
    """1.0 inside the estimated range, else actual / the nearest bound."""
    if not est:
        return None
    lo, hi = est
    if lo <= actual <= hi:
        return 1.0
    bound = hi if actual > hi else lo
    return actual / bound if bound else None


def runs_dir(root: Path) -> Path:
    """.autodev/runs of the main worktree: it holds runs/*.json and run.log, which git does not carry to the others."""
    own = root / ".autodev" / "runs"
    try:
        common = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return own
    main = Path(common).parent / ".autodev" / "runs"
    return main if common and main.is_dir() else own


def _plans(root: Path) -> dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted((root / "plan").glob("*.md")) if p.stem != "PROGRESS"}


def _from_log(runs: Path) -> tuple[dict[tuple[str, str], float], dict[str, int]]:
    """(wall-clock minutes per (milestone, role), STOP count per milestone) from run.log.

    A step lasts from its "start" line to the next "end" or "STOP" line. ``duration_ms`` in runs/*.json is not
    used: it can be far below the wall clock (R5 worker: 62 s for an 18-minute session)."""
    log = runs / "run.log"
    minutes: dict[tuple[str, str], float] = {}
    stops: dict[str, int] = {}
    if not log.exists():
        return minutes, stops
    current, role, since = None, None, None
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            ts = dt.datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007 - run.log is local wall clock
        except ValueError:
            continue
        m = LOG_START_RE.search(line)
        if m:
            current, role, since = m.group(1), m.group(2), ts
            continue
        is_stop = "STOP (exit" in line
        if current and since and (is_stop or LOG_END_RE.search(line)):
            key = (current, role)
            minutes[key] = minutes.get(key, 0.0) + (ts - since).total_seconds() / 60
            since = None
        if is_stop and current:
            stops[current] = stops.get(current, 0) + 1
    return minutes, stops


def milestones(root: Path = ROOT) -> list[dict]:
    plans = _plans(root)
    out = {
        mid: {
            "id": mid,
            "tasks": len(TASK_RE.findall(text)),
            "rounds": [int(r) for r in ROUNDS_RE.findall(text)],
            "estimate": parse_estimate(text),
            "usd": 0.0,
            "usd_supervisor": None,
            "usd_supervisor_assumed": None,
            "minutes": 0.0,
            "minutes_supervisor": 0.0,
            "turns": 0,
            "stops": 0,
            "ran": False,
        }
        for mid, text in plans.items()
    }
    runs = runs_dir(root)
    for f in sorted(runs.glob("*.json")):
        m = RUN_FILE_RE.match(f.name)
        if not m or m.group(1) not in out:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ms = out[m.group(1)]
        cost = float(data.get("total_cost_usd") or 0)
        ms["usd"] += cost
        ms["turns"] += int(data.get("num_turns") or 0)
        ms["ran"] = True
        if m.group(2) == "supervisor":
            ms["usd_supervisor"] = (ms["usd_supervisor"] or 0.0) + cost
    minutes, stops = _from_log(runs)
    for mid, ms in out.items():
        # the plan's estimate counts worker minutes only (P6a template), so B3 compares worker minutes
        ms["minutes"] = minutes.get((mid, "worker"), 0.0)
        ms["minutes_supervisor"] = minutes.get((mid, "supervisor"), 0.0)
        ms["stops"] = stops.get(mid, 0)
        ms["ran"] = ms["ran"] or (mid, "worker") in minutes
    # the supervisor writes B3 while it runs, before its own runs/*.json exists: add the mean of earlier supervisors
    sup = [ms["usd_supervisor"] for ms in out.values() if ms["usd_supervisor"] is not None]
    for ms in out.values():
        if ms["ran"] and ms["usd_supervisor"] is None and sup:
            ms["usd_supervisor_assumed"] = sum(sup) / len(sup)
    return list(out.values())


def audits(root: Path = ROOT) -> list[dict]:
    """B1 per audit: new high/medium gaps (not in an earlier audit) / tasks of the milestones in scope."""
    tasks = {m["id"]: m["tasks"] for m in milestones(root)}
    seen: set[str] = set()
    out = []
    for f in sorted((root / "docs" / "audits").glob("*.md")):
        text = f.read_text(encoding="utf-8")
        scope_line = next((ln for ln in text.splitlines() if ln.startswith("- Mốc:")), "")
        scope = list(dict.fromkeys(SCOPE_RE.findall(scope_line)))
        rows = [GAP_RE.match(ln) for ln in text.splitlines()]
        levels = {m.group(1): m.group(2) for m in rows if m}
        new = [g for g, lvl in levels.items() if g not in seen and lvl in ("cao", "vừa")]
        seen |= set(levels)
        n_tasks = sum(tasks.get(s, 0) for s in scope)
        out.append({
            "file": f.name,
            "scope": scope,
            "new_high_medium": len(new),
            "tasks": n_tasks,
            "b1": (len(new) / n_tasks) if n_tasks else None,
        })
    return out


def _f(x: float | None, nd: int = 2) -> str:
    return "–" if x is None else f"{x:.{nd}f}".replace(".", ",")


def report(root: Path = ROOT) -> str:
    ms = [m for m in milestones(root) if m["tasks"]]
    rounds = [r for m in ms for r in m["rounds"] if r >= 1]
    multi = sum(1 for r in rounds if r >= 2)
    lines = [
        "## Số đo plugin B1–B5 (định nghĩa: ROADMAP bảng B)",
        "",
        "### B1 Lỗi lọt qua review (lỗ hổng mới mức cao + vừa / task trong phạm vi audit; ngưỡng ≤ 0,5)",
        "",
        "| Audit | Phạm vi | Lỗ hổng mới cao+vừa | Task | B1 |",
        "|---|---|---|---|---|",
    ]
    for a in audits(root):
        lines.append(f"| {a['file']} | {', '.join(a['scope']) or '–'} | {a['new_high_medium']} | {a['tasks']} | {_f(a['b1'])} |")
    pct = (100 * multi / len(rounds)) if rounds else 0.0
    lines += [
        "",
        f"### B2 Độ chặt review: {multi}/{len(rounds)} task cần ≥ 2 vòng ({_f(pct, 0)}%). Đọc cùng B1: B2 thấp mà B1 cao là reviewer lỏng.",
        "",
        "### B3–B5 theo mốc (B3: thực tế / ước tính, 1,0 = trong khoảng, ngưỡng 0,5–2; B4: số lần runner dừng, ngưỡng 0; B5: chi phí trên task)",
        "",
        "| Mốc | Task | Phút worker | USD | Phút/task | USD/task | Lượt | B3 phút | B3 USD | B4 dừng |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in ms:
        est = m["estimate"] or {}
        n = m["tasks"]
        if not m["ran"]:
            lines.append(f"| {m['id']} | {n} | – | – | – | – | – | – | – | – |")
            continue
        assumed = m["usd_supervisor_assumed"]
        usd = m["usd"] + (assumed or 0.0)
        mark = "~" if assumed is not None else ""
        usd_cell = f"{_f(m['usd'])} + ~{_f(assumed)}" if assumed is not None else _f(m["usd"])
        lines.append(
            f"| {m['id']} | {n} | {_f(m['minutes'], 0)} | {usd_cell} | {_f(m['minutes'] / n, 1)} | "
            f"{mark}{_f(usd / n)} | {m['turns']} | {_f(ratio(m['minutes'], est.get('minutes')))} | "
            f"{mark}{_f(ratio(usd, est.get('usd')))} | {m['stops']} |"
        )
    lines += [
        "",
        (
            "– = mốc chưa chạy. Phút = giờ thật của worker trong `run.log` (ước tính chỉ tính worker); USD gồm worker"
            " + supervisor. `+ ~x`: chưa có `runs/*.json` của supervisor (nó đang chạy), cộng tạm chi phí supervisor"
            " trung bình; chạy lại `--write` sau khi mốc xong để có số thật. Mốc trước R4 chạy chế độ A"
            " (không có `runs/*.json`) nên hiện –."
        ),
    ]
    return "\n".join(lines) + "\n"


def write_section(path: Path, body: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    block = f"{START}\n{body.rstrip()}\n{END}\n"
    if START in text and END in text:
        head, rest = text.split(START, 1)
        text = head + block + rest.split(END, 1)[1].lstrip("\n")
    else:
        text = text.rstrip("\n") + "\n\n" + block
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="replace the marked section of docs/autodev/PROGRESS.md")
    args = ap.parse_args(argv)
    body = report(ROOT)
    print(body, end="")
    if args.write:
        write_section(ROOT / "docs" / "autodev" / "PROGRESS.md", body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
