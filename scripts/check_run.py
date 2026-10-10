"""Check one whole run over HTTP against a running API (used by ``scripts/demo.sh --check``).

    uv run python scripts/check_run.py --api http://127.0.0.1:8000 [--repeat N]

Starts a run, plays the demo person (answers questions, approves as the first name of /config/approvers) until the
run ends with ``learning_saved``, then calls the 5 read APIs and checks the status code and the keys of the payload.
Prints ``CHECK PASSED`` or ``CHECK FAILED: <step>`` (exit 1). With ``--repeat N`` it does N runs in a row and prints
the time of each run, the number of passes and the p95 (metric A8). The run is a DEMO of the loop, not proof of accuracy.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAX_ROUNDS = 25
ANSWER = "I have no further information about this."


class CheckFailed(Exception):
    """``step`` names the failing step, e.g. ``GET /metrics``."""

    def __init__(self, step: str, detail: str = "") -> None:
        super().__init__(f"{step}: {detail}" if detail else step)
        self.step = step
        self.detail = detail


def call(client: Any, method: str, path: str, step: str | None = None, ok: tuple[int, ...] = (200,), **kw: Any) -> Any:
    step = step or f"{method} {path.split('?')[0]}"
    try:
        r = client.request(method, path, **kw)
    except Exception as e:  # connection refused, timeout, wrong URL
        raise CheckFailed(step, f"{type(e).__name__}: {e}") from e
    if r.status_code not in ok:
        raise CheckFailed(step, f"HTTP {r.status_code}: {r.text[:200]}")
    try:
        return r.json()
    except ValueError as e:
        raise CheckFailed(step, "response is not JSON") from e


def need_keys(step: str, obj: Any, keys: set[str]) -> None:
    if not isinstance(obj, dict) or not keys <= set(obj):
        raise CheckFailed(step, f"expected keys {sorted(keys)}, got {sorted(obj) if isinstance(obj, dict) else type(obj).__name__}")


def drive(client: Any) -> str:
    """Start a run and play the person until it finishes. Returns the run id."""
    approvers = call(client, "GET", "/config/approvers").get("approvers") or []
    if not approvers:
        raise CheckFailed("GET /config/approvers", "empty approver list")
    who = approvers[0]
    st = call(client, "POST", "/runs", ok=(201,), json={})
    run_id = st.get("run_id")
    if not run_id:
        raise CheckFailed("POST /runs", f"no run_id in {st}")
    for _ in range(MAX_ROUNDS):
        state = st.get("state")
        if state == "error":
            raise CheckFailed("run", f"run {run_id} ended in error: {st.get('error')}")
        if state == "finished":
            return run_id
        pending = st.get("pending") or {}
        if pending.get("type") == "answer":
            st = call(client, "POST", f"/runs/{run_id}/answer", json={"answer": ANSWER})
        elif pending.get("type") == "approval":
            kind = pending.get("kind", "proposal")
            decision = "finish" if kind == "halt" else "approved"
            st = call(
                client, "POST", f"/runs/{run_id}/approval",
                json={"proposal_id": pending.get("proposal_id", ""), "kind": kind, "decision": decision,
                      "decided_by": who, "reason": "demo check"},
            )
        else:
            st = call(client, "GET", f"/runs/{run_id}")
            if st.get("state") == "running":
                time.sleep(0.5)
    raise CheckFailed("run", f"run {run_id} did not finish within {MAX_ROUNDS} rounds")


def check_run(client: Any, kpi: str, sop_id: str) -> str:
    """One whole run + the read APIs. Raises CheckFailed; returns the run id."""
    run_id = drive(client)
    exported = call(client, "GET", f"/runs/{run_id}/export")
    types = [e.get("type") for e in exported.get("events", [])]
    if "learning_saved" not in types:
        raise CheckFailed("run", f"run {run_id} finished without learning_saved (last events: {types[-3:]})")
    print(f"ok: run {run_id} reached learning_saved", flush=True)

    runs = call(client, "GET", "/runs")
    need_keys("GET /runs", runs, {"runs"})
    mine = [r for r in runs["runs"] if r.get("run_id") == run_id]
    if not mine:
        raise CheckFailed("GET /runs", f"run {run_id} not listed")
    need_keys("GET /runs", mine[0], {"run_id", "state", "started_at", "finished_at", "outcome", "pending"})
    print("ok: GET /runs", flush=True)

    series = call(client, "GET", f"/kpi/series?kpi={kpi}")
    need_keys("GET /kpi/series", series, {"kpi", "points", "baseline", "upper_limit", "anomalies"})
    print("ok: GET /kpi/series", flush=True)

    audit = call(client, "GET", f"/audit?run_id={run_id}")
    need_keys("GET /audit", audit, {"rows"})
    if not audit["rows"]:
        raise CheckFailed("GET /audit", f"no audit rows for {run_id}")
    need_keys("GET /audit", audit["rows"][0], {"id", "ts", "run_id", "actor", "action", "params"})
    print("ok: GET /audit", flush=True)

    sop = call(client, "GET", f"/sop/{sop_id}/versions")
    need_keys("GET /sop/{id}/versions", sop, {"sop_id", "versions"})
    if not sop["versions"]:
        raise CheckFailed("GET /sop/{id}/versions", "no versions")
    need_keys("GET /sop/{id}/versions", sop["versions"][0], {"version", "created_by", "run_id", "created_at", "content"})
    print("ok: GET /sop/{id}/versions", flush=True)

    metrics = call(client, "GET", "/metrics")
    need_keys("GET /metrics", metrics, {"metrics"})
    if len(metrics["metrics"]) != 3:
        raise CheckFailed("GET /metrics", f"expected 3 metrics, got {len(metrics['metrics'])}")
    need_keys("GET /metrics", metrics["metrics"][0], {"name", "unit", "before", "after", "available", "reason", "run_id"})
    print("ok: GET /metrics", flush=True)
    return run_id


def p95(values: list[float]) -> float:
    """Nearest-rank 95th percentile; 0.0 for no values."""
    if not values:
        return 0.0
    s = sorted(values)
    return s[max(0, math.ceil(0.95 * len(s)) - 1)]


def check_many(client: Any, kpi: str, sop_id: str, repeat: int = 1) -> bool:
    """``repeat`` runs in a row; prints CHECK PASSED / CHECK FAILED: <step>. True when all passed."""
    times: list[float] = []
    failed: CheckFailed | None = None
    for i in range(1, repeat + 1):
        t0 = time.monotonic()
        try:
            check_run(client, kpi, sop_id)
        except CheckFailed as e:
            failed = failed or e
            print(f"run {i}/{repeat}: FAILED ({e}) after {time.monotonic() - t0:.1f}s", flush=True)
            continue
        times.append(time.monotonic() - t0)
        print(f"run {i}/{repeat}: {times[-1]:.1f}s", flush=True)
    if repeat > 1:
        print(f"passed {len(times)}/{repeat}; p95 {p95(times):.1f}s", flush=True)
    if failed is not None:
        print(f"CHECK FAILED: {failed.step}" + (f" ({failed.detail})" if failed.detail else ""), file=sys.stderr, flush=True)
        return False
    print("RUN CHECK PASSED", flush=True)  # demo.sh prints the final CHECK PASSED after its own probes
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api", required=True)
    p.add_argument("--repeat", type=int, default=1)
    args = p.parse_args(argv)
    if args.repeat < 1:
        p.error("--repeat must be >= 1")
    import httpx

    from backend.domain_config import load_domain_config

    cfg = load_domain_config()
    with httpx.Client(base_url=args.api.rstrip("/"), timeout=180) as client:
        ok = check_many(client, cfg.kpis[0].name, cfg.sop[0].id, args.repeat)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
