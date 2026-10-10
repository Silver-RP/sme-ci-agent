#!/usr/bin/env bash
# Demo: Postgres + backend (uvicorn) + dashboard (yarn dev). Stop everything with Ctrl+C.
#   scripts/demo.sh            # scripted (fake) LLM, no key needed
#   SME_LLM=real scripts/demo.sh   # real LLM: put ANTHROPIC_API_KEY and MODEL_REASONING in .env yourself
#   scripts/demo.sh --check    # start everything, probe /docs, run one whole run over HTTP (scripts/check_run.py:
#                              answers, approves, reaches learning_saved, calls the 5 read APIs), probe the dashboard
#                              page, stop; prints CHECK PASSED, or CHECK FAILED: <step> and exits 1
#   scripts/demo.sh --check --repeat N   # N runs in a row; prints time per run, passes and p95
#   scripts/demo.sh --fresh-db # run on database <name>_demo, dropped and created empty first (scripts/fresh_db.py);
#                              the main database is not touched. Combines with --check.
# Env: API_PORT (default 8000), DASH_PORT (default 3000), DB_PORT (default 5432),
#      DATABASE_URL (default built from DB_PORT; if it already connects, no new container is started),
#      SME_CORS_ORIGINS (default built from DASH_PORT), DB_WAIT (seconds to wait for Postgres, default 30).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
API_PORT="${API_PORT:-8000}"
DASH_PORT="${DASH_PORT:-3000}"
DB_PORT="${DB_PORT:-5432}"
DB_WAIT="${DB_WAIT:-30}"
CHECK=0
FRESH_DB=0
REPEAT=1
while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK=1 ;;
    --fresh-db) FRESH_DB=1 ;;
    --repeat) shift; REPEAT="${1:-}" ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
case "$REPEAT" in ''|*[!0-9]*|0) echo "--repeat needs a positive number" >&2; exit 2 ;; esac

if [ "${SME_LLM:-scripted}" = "real" ] && [ "$CHECK" = "0" ]; then
  unset SME_LLM
  if [ -f .env ]; then set -a; . ./.env; set +a; fi   # loaded by the shell only; this script never prints it
else
  export SME_LLM=scripted
fi

export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://${POSTGRES_USER:-sme}:${POSTGRES_PASSWORD:-sme}@localhost:${DB_PORT}/${POSTGRES_DB:-sme_ci}}"
export DB_PORT
export SME_CORS_ORIGINS="${SME_CORS_ORIGINS:-http://localhost:${DASH_PORT},http://127.0.0.1:${DASH_PORT}}"

PIDS=()
kill_tree() {
  local p="$1" c
  for c in $(pgrep -P "$p" 2>/dev/null || true); do kill_tree "$c"; done
  kill "$p" 2>/dev/null || true
}
cleanup() {
  trap - INT TERM EXIT
  echo
  echo "Stopping..."
  for p in "${PIDS[@]:-}"; do
    [ -n "$p" ] && kill_tree "$p"
  done
  wait 2>/dev/null || true
  echo "Stopped. Postgres is still running if this script started it (docker compose stop db to stop it)."
}
trap cleanup INT TERM EXIT

db_ok() {
  uv run python -c "
import sys
from sqlalchemy import create_engine, text
try:
    with create_engine(sys.argv[1], connect_args={'connect_timeout': 3}).connect() as c:
        c.execute(text('select 1'))
except Exception:
    sys.exit(1)
" "$DATABASE_URL" >/dev/null 2>&1
}

if db_ok; then
  echo "Postgres already reachable at DATABASE_URL; not starting a container."
else
  docker compose up -d db
  echo "Waiting for Postgres (up to ${DB_WAIT}s)..."
  ready=0
  for _ in $(seq 1 "$DB_WAIT"); do
    if db_ok; then ready=1; break; fi
    sleep 1
  done
  if [ "$ready" != "1" ]; then
    echo "ERROR: Postgres did not come up within ${DB_WAIT}s (DATABASE_URL port: ${DB_PORT}). Check 'docker compose logs db' or set DB_PORT/DATABASE_URL." >&2
    exit 1
  fi
fi
if [ "$FRESH_DB" = "1" ]; then
  DATABASE_URL="$(uv run python scripts/fresh_db.py "$DATABASE_URL")"
  export DATABASE_URL
  echo "Fresh demo database: ${DATABASE_URL##*/}"
fi
uv run alembic upgrade head

uv run uvicorn backend.api.app:create_app --factory --port "$API_PORT" &
PIDS+=($!)
(cd dashboard && NEXT_PUBLIC_API_URL="http://localhost:$API_PORT" exec yarn dev --port "$DASH_PORT") &
PIDS+=($!)

if [ "$CHECK" = "1" ]; then
  wait_url() {  # url, tries
    local i
    for i in $(seq 1 "$2"); do
      if curl -fsS -o /dev/null --max-time 60 "$1" 2>/dev/null; then return 0; fi
      sleep 1
    done
    return 1
  }
  fail() { echo "CHECK FAILED: $1" >&2; exit 1; }
  wait_url "http://localhost:$API_PORT/docs" 60 || fail "GET /docs"
  echo "ok: GET /docs"
  # check_run.py prints "CHECK FAILED: <step>" itself and exits 1; "CHECK PASSED" is printed below, after the dashboard probe
  uv run python scripts/check_run.py --api "http://localhost:$API_PORT" --repeat "$REPEAT" || exit 1
  wait_url "http://localhost:$DASH_PORT/?source=live" 120 || fail "dashboard page"
  echo "ok: dashboard page"
  echo "CHECK PASSED"
  exit 0
fi

echo
echo "Backend:   http://localhost:$API_PORT  (docs: /docs)"
echo "Dashboard: http://localhost:$DASH_PORT/?source=live"
echo "Press Ctrl+C to stop."
wait
