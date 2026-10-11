"""Numbers for GET /metrics: the report written by scripts/metrics_report.py for this dataset and seed.

Read only. A report of another dataset or seed is never used (also when its file name says otherwise), and
the app never recomputes (a replay takes minutes): it says how to produce the report. "before" is the arm without
the agent, "after" the arm with it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ENV_DIR = "SME_REPORTS_DIR"
REPORT_COMMAND = "uv run python scripts/metrics_report.py --months 6 --seed {seed}"


def reports_dir() -> Path:
    env = os.environ.get(ENV_DIR, "").strip()
    return Path(env) if env else ROOT / "data" / "reports"


def report_path(dataset: str, seed: int) -> Path:
    return reports_dir() / f"metrics_{dataset}_seed{seed}.json"  # same name as scripts/metrics_report.report_paths


def load_report(dataset: str, seed: int) -> tuple[dict[str, Any] | None, str]:
    """(report, "") when a readable report of this dataset and seed exists, else (None, reason)."""
    hint = f"run `{REPORT_COMMAND.format(seed=seed)}` for dataset {dataset!r}"
    path = report_path(dataset, seed)
    if not path.is_file():
        return None, f"no metrics report for dataset {dataset!r}, seed {seed}: {hint}"
    try:
        rep = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, f"metrics report for dataset {dataset!r}, seed {seed} is unreadable: {hint}"
    if not isinstance(rep, dict) or rep.get("dataset") != dataset or rep.get("seed") != seed:
        return None, f"metrics report file does not hold dataset {dataset!r}, seed {seed}: {hint}"
    return rep, ""


def _num(arm: Any, *keys: str) -> float | None:
    if not isinstance(arm, dict):
        return None
    total = 0.0
    for k in keys:
        v = arm.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        total += float(v)
    return total


def _metric(name: str, unit: str, rep: dict[str, Any] | None, reason: str, *keys: str) -> dict[str, Any]:
    before = after = None
    if rep is not None:
        before, after = _num(rep.get("manual"), *keys), _num(rep.get("agent"), *keys)
        if before is None or after is None:
            before = after = None
            reason = f"the report has no value for {' + '.join(keys)} in both arms"
    ok = before is not None
    return {"name": name, "unit": unit, "before": before, "after": after, "available": ok,
            "reason": None if ok else reason, "run_id": None}


def build_metrics(kpi_name: str, kpi_unit: str, dataset: str, seed: int) -> dict[str, Any]:
    rep, reason = load_report(dataset, seed)
    return {
        "dataset": dataset,
        "seed": seed,
        "generated_at": rep.get("generated_at") if rep else None,
        "assumptions": rep.get("assumptions", []) if rep else [],
        "metrics": [
            # period rate of the whole replay, weighted by output; both arms over the same period
            _metric(kpi_name, kpi_unit, rep, reason, "period_rate"),
            # detection plus repair time per problem, from its start to the fix
            _metric("mttd_mttr", "hours", rep, reason, "mttd_hours", "mttr_hours"),
            _metric("recurrence_rate", "ratio", rep, reason, "recurrence_rate"),
        ],
    }
