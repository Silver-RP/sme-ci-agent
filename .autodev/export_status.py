"""Export the 7 datasets of the private status page (plugin P5, Artifact of type Dashboard).

    python3 .autodev/export_status.py                 # writes .autodev/runs/status/*.json (gitignored)
    python3 .autodev/export_status.py --out DIR

Sources (read only): docs/autodev/state.json (goals, open gaps, plugin milestones, outlook, merged runs),
.autodev/metrics.py (milestones, audits) and the last lines of .autodev/runs/run.log (runner).
Stdlib only (python3.9).

The page (https://claude.ai/artifact/X6TLNZGZmzraP36WKgBKxF, private) is a snapshot, refreshed ONLY when the leader
asks (leader choice 2026-10-10, not part of /session-end):
  1. run this script;
  2. upload each of the 7 files as an asset of the page (Artifact publish, url, asset: true, one file_path per call);
  3. ArtifactData batch: for each datasets/<name>, update source = {kind: "file", name: "<name>.json", url: <blob url>}
     and updated = {at: <ISO time>, by: "Claude (.autodev/export_status.py)"}, pinned to the version just read.
Old assets stay unless the leader approves deleting them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NAMES = ("goals", "milestones", "audits", "gaps", "plugin", "outlook", "runner")
LOG_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}):\d{2} (.*)$")
LOG_START_RE = re.compile(r"^start (\S+)-(worker|supervisor|audit)\b")

_spec = importlib.util.spec_from_file_location("autodev_metrics", HERE / "metrics.py")
metrics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(metrics)


def _range(r: tuple[float, float] | None) -> str | None:
    if not r:
        return None
    lo, hi = (f"{x:g}".replace(".", ",") for x in r)
    return lo if lo == hi else f"{lo}–{hi}"


def _round(x: float | None, nd: int = 2) -> float | None:
    return None if x is None else round(x, nd)


def runner(root: Path) -> dict:
    """Last step of run.log: running (a "start" with no end yet), stopped (STOP) or idle."""
    log = metrics.runs_dir(root) / "run.log"
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if LOG_LINE_RE.match(ln)] if log.exists() else []
    row = {"milestone": None, "step": None, "state": "idle", "since": None, "last_line": None,
           "exported_at": dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")}
    if not lines:
        return row
    since, last = LOG_LINE_RE.match(lines[-1]).groups()
    row.update(since=since, last_line=last)
    if last.startswith("STOP"):
        row["state"] = "stopped"
    m = LOG_START_RE.match(last)
    if m:
        row.update(milestone=m.group(1), step=m.group(2), state="running")
    return row


def export(root: Path = ROOT) -> dict[str, list]:
    state = json.loads((root / "docs" / "autodev" / "state.json").read_text(encoding="utf-8"))
    run = runner(root)
    merged = {r["id"]: r for r in state["milestones"]["runs"] if r.get("status") == "merged"}
    rows = []
    for m in metrics.milestones(root):
        if not m["id"].startswith("R") or not m["tasks"]:
            continue
        est = m["estimate"] or {}
        usd = m["usd"] + (m["usd_supervisor_assumed"] or 0.0) if m["ran"] else None
        if run["state"] == "running" and run["milestone"] == m["id"]:
            status = "running"
        else:
            status = "merged" if m["id"] in merged else ("ran" if m["ran"] else "planned")
        rows.append({
            "milestone": m["id"],
            "status": status,
            "tasks": m["tasks"],
            "minutes": _round(m["minutes"], 0) if m["ran"] else None,
            "usd": _round(usd),
            "est_minutes": _range(est.get("minutes")),
            "est_usd": _range(est.get("usd")),
            "b3_minutes": _round(metrics.ratio(m["minutes"], est.get("minutes"))) if m["ran"] else None,
            "b3_usd": _round(metrics.ratio(usd, est.get("usd"))) if m["ran"] else None,
            "stops": m["stops"] if m["ran"] else None,
        })
    return {
        "goals": [
            {"goal": g["id"], "name": g["text"], "percent": g["percent"], "estimate_old": g.get("estimate_old"),
             "metrics": ", ".join(g.get("metrics", []))}
            for g in state["goals"]
        ],
        "milestones": rows,
        "audits": [
            {"audit": a["file"].removesuffix(".md"),
             "scope": ", ".join(a["scope"]), "new_high_medium": a["new_high_medium"], "tasks": a["tasks"],
             "b1": _round(a["b1"])}
            for a in metrics.audits(root)
        ],
        "gaps": [{"id": g["id"], "severity": g["severity"], "summary": g["summary"]} for g in state["open_gaps"]],
        "plugin": [
            {"milestone": p["id"], "status": p["status"], "note": p.get("note", "")}
            for p in state["milestones"]["plugin"]
        ],
        "outlook": [
            {"milestone": o["id"], "date": o.get("date", ""), "goal": o.get("goal", ""),
             "needs_team": "có" if o.get("needs_team") else "không", "status": o.get("status", "chưa chạy")}
            for o in state["outlook"]
        ],
        "runner": [run],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=None, help="output directory (default .autodev/runs/status)")
    args = ap.parse_args(argv)
    out = args.out or metrics.runs_dir(ROOT) / "status"
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in export(ROOT).items():
        (out / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(NAMES)} file trong {out}: " + ", ".join(f"{n}.json" for n in NAMES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
