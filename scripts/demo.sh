#!/usr/bin/env bash
# Demo: Postgres + backend (uvicorn) + dashboard (yarn dev). Stop everything with Ctrl+C.
#   scripts/demo.sh            # scripted (fake) LLM, no key needed
#   SME_LLM=real scripts/demo.sh   # real LLM: put ANTHROPIC_API_KEY and MODEL_REASONING in .env yourself
# Env: API_PORT (default 8000), DASH_PORT (default 3000), DB_PORT (default 5432; also set it in DATABASE_URL).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
API_PORT="${API_PORT:-8000}"
DASH_PORT="${DASH_PORT:-3000}"

if [ "${SME_LLM:-scripted}" = "real" ]; then
  unset SME_LLM
  if [ -f .env ]; then set -a; . ./.env; set +a; fi   # loaded by the shell only; this script never prints it
else
  export SME_LLM=scripted
fi

PIDS=()
cleanup() {
  trap - INT TERM EXIT
  echo
  echo "Stopping..."
  for p in "${PIDS[@]:-}"; do
    [ -n "$p" ] && kill "$p" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "Stopped. Postgres is still running (docker compose stop db to stop it)."
}
trap cleanup INT TERM EXIT

docker compose up -d db
echo "Waiting for Postgres..."
for _ in $(seq 1 30); do
  if docker compose exec -T db pg_isready -U "${POSTGRES_USER:-sme}" >/dev/null 2>&1; then break; fi
  sleep 1
done
uv run alembic upgrade head

uv run uvicorn backend.api.app:create_app --factory --port "$API_PORT" &
PIDS+=($!)
(cd dashboard && NEXT_PUBLIC_API_URL="http://localhost:$API_PORT" yarn dev --port "$DASH_PORT") &
PIDS+=($!)

echo
echo "Backend:   http://localhost:$API_PORT  (docs: /docs)"
echo "Dashboard: http://localhost:$DASH_PORT/?source=live"
echo "Press Ctrl+C to stop."
wait
