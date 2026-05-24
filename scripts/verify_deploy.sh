#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker/docker-compose.yml"
API_PORT="${GENGSCOPE_API_PORT:-8010}"
BASE_URL="http://127.0.0.1:${API_PORT}"

cd "$ROOT_DIR"

api_key="${GENGSCOPE_DEPLOY_VERIFY_API_KEY:-${GENGSCOPE_API_KEY:-}}"
if [[ -z "$api_key" && -n "${GENGSCOPE_API_KEYS:-}" ]]; then
  api_key="${GENGSCOPE_API_KEYS%%,*}"
fi
curl_api() {
  if [[ -n "$api_key" ]]; then
    curl -fsS -H "X-API-Key: ${api_key}" "$@"
  else
    curl -fsS "$@"
  fi
}

docker compose -f "$COMPOSE_FILE" build api worker
docker compose -f "$COMPOSE_FILE" up -d api worker

scripts/db_migrate.sh

curl -fsS "${BASE_URL}/health/ready" >/dev/null
curl_api "${BASE_URL}/api/reports/archive" >/dev/null
curl_api "${BASE_URL}/api/jobs/schedules?limit=1" >/dev/null
curl_api -X POST "${BASE_URL}/api/reports/archive/prune" \
  -H "content-type: application/json" \
  -d '{"keep_latest":20,"older_than_days":180,"dry_run":true}' >/dev/null
curl_api -X POST "${BASE_URL}/api/jobs/schedules/run-due" >/dev/null

openapi="$(curl -fsS "${BASE_URL}/openapi.json")"
for path in \
  "/api/entities/corpus" \
  "/api/entities/corpus/import" \
  "/api/entities/groups" \
  "/api/entities/groups/corpus" \
  "/api/entities/{entity_type}/{entity_id}/breakdown" \
  "/api/artifacts/discover" \
  "/api/artifacts/fetch" \
  "/api/audits/entity-cycle" \
  "/api/jobs/entity-corpus" \
  "/api/jobs/entity-cycle" \
  "/api/jobs/schedules/entity-cycle" \
  "/api/jobs/schedules/run-due" \
  "/api/jobs/schedules/{schedule_id}/status" \
  "/api/reports/entity/archive" \
  "/api/reports/archive/prune"; do
  grep -q "$path" <<<"$openapi"
done

scripts/verify_deploy_e2e.sh

docker compose -f "$COMPOSE_FILE" ps
printf 'GengScope deploy verification passed at %s.\n' "$BASE_URL"
