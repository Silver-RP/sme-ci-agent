"""Record one run from a running API into a fixture file the dashboard can replay.

    uv run python scripts/record_run.py --api http://127.0.0.1:8000 --run-id run_ab12cd34 [--out FILE]

Calls ``GET /runs/{id}/export`` (same format as docs/schema/examples/run-*.json; no traceback, no internal data)
and writes it. Default output: docs/schema/examples/recorded-<run-id>.json.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "schema" / "examples"


def default_out(run_id: str) -> Path:
    return EXAMPLES / f"recorded-{run_id}.json"


def record(client: Any, run_id: str, out: Path) -> Path:
    """``client``: httpx.Client or a Starlette TestClient. Nothing is written when the API call fails."""
    resp = client.get(f"/runs/{run_id}/export")
    if resp.status_code != 200:
        raise SystemExit(f"export of {run_id!r} failed: HTTP {resp.status_code}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(resp.json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api", required=True, help="base URL of the API, e.g. http://127.0.0.1:8000")
    p.add_argument("--run-id", required=True)
    p.add_argument("--out", type=Path, default=None, help="default: docs/schema/examples/recorded-<run-id>.json")
    args = p.parse_args(argv)
    import httpx

    with httpx.Client(base_url=args.api.rstrip("/"), timeout=30) as client:
        path = record(client, args.run_id, args.out or default_out(args.run_id))
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
