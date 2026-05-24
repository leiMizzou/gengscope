#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_COMPOSE="$ROOT_DIR/infra/docker/docker-compose.yml"
DEMO_COMPOSE="$ROOT_DIR/infra/docker/docker-compose.demo.yml"
API_PORT="${GENGSCOPE_API_PORT:-8010}"
BASE_URL="http://127.0.0.1:${API_PORT}"
DEMO_KEY="${GENGSCOPE_DEMO_VERIFY_API_KEY:-demo-read}"

cd "$ROOT_DIR"

docker compose -f "$BASE_COMPOSE" -f "$DEMO_COMPOSE" config >/dev/null
docker compose -f "$BASE_COMPOSE" -f "$DEMO_COMPOSE" up -d --build api worker
scripts/db_migrate.sh
docker compose -f "$BASE_COMPOSE" -f "$DEMO_COMPOSE" run --rm demo-seed >/tmp/gengscope-demo-seed.json

for _ in $(seq 1 60); do
  if curl -fsS "${BASE_URL}/health/ready" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "${BASE_URL}/health/ready" >/dev/null
curl -fsS -H "X-API-Key: ${DEMO_KEY}" "${BASE_URL}/api/agent/doi/10.5555%2Fgengscope.demo.1" >/tmp/gengscope-demo-agent.json
python3 - <<'PY'
import json

with open("/tmp/gengscope-demo-agent.json", encoding="utf-8") as handle:
    payload = json.load(handle)

assert payload["paper"]["doi"] == "10.5555/gengscope.demo.1", payload
assert "不能据此直接认定" in payload["conclusion_boundary"], payload
PY

status_code="$(curl -sS -o /tmp/gengscope-demo-write.json -w '%{http_code}' \
  -H "X-API-Key: ${DEMO_KEY}" \
  -H "content-type: application/json" \
  -X POST "${BASE_URL}/api/admin/events" \
  -d '{"doi":"10.5555/gengscope.demo.1","event_type":"public_discussion","status_level":"public_discussion","source_type":"pubpeer","source_url":"https://example.org/demo","claim_summary":"demo write should be blocked"}')"
if [[ "$status_code" != "403" ]]; then
  printf 'Expected demo read key to be blocked from writes, got HTTP %s\n' "$status_code" >&2
  cat /tmp/gengscope-demo-write.json >&2
  exit 1
fi

printf 'GengScope public demo verification passed at %s with read key %s.\n' "$BASE_URL" "$DEMO_KEY"
