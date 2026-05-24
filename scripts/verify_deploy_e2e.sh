#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker/docker-compose.yml"
API_PORT="${GENGSCOPE_API_PORT:-8010}"
BASE_URL="http://127.0.0.1:${API_PORT}"

cd "$ROOT_DIR"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

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

post_json() {
  local path="$1"
  local body="$2"
  local output="$3"
  curl_api -X POST "${BASE_URL}${path}" \
    -H "content-type: application/json" \
    -H "X-GengScope-Actor: deploy-e2e" \
    -d "$body" >"$output"
}

json_get() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
print(eval(sys.argv[2], {"payload": payload}))
PY
}

assert_json() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
if not eval(sys.argv[2], {"payload": payload}):
    raise SystemExit(f"JSON assertion failed: {sys.argv[2]}\n{json.dumps(payload, ensure_ascii=False, indent=2)}")
PY
}

docker compose -f "$COMPOSE_FILE" exec -T api gengscope-demo-seed >"$tmpdir/seed.json"
author_id="$(json_get "$tmpdir/seed.json" "payload['author']['id']")"
institution_id="$(json_get "$tmpdir/seed.json" "payload['institution']['id']")"
primary_doi="$(json_get "$tmpdir/seed.json" "payload['primary_doi']")"
run_id="$(date +%s%N)"

curl_api "${BASE_URL}/api/entities/author/${author_id}/profile" >"$tmpdir/profile-before.json"
assert_json "$tmpdir/profile-before.json" "payload['paper_count'] >= 2 and '不能直接认定' in payload['conclusion_boundary']"

post_json "/api/entities/groups" "{\"display_name\":\"Deploy E2E Demo Lab ${run_id}\",\"description\":\"Synthetic local group for deployed smoke testing\",\"members\":[{\"entity_type\":\"author\",\"entity_id\":\"${author_id}\",\"label\":\"PI\"},{\"entity_type\":\"institution\",\"entity_id\":\"${institution_id}\",\"label\":\"Institute\"}]}" "$tmpdir/group.json"
group_id="$(json_get "$tmpdir/group.json" "payload['entity']['id']")"
assert_json "$tmpdir/group.json" "payload['entity']['entity_type'] == 'group' and payload['profile']['paper_count'] >= 2 and 'group/lab' in payload['conclusion_boundary']"

curl_api "${BASE_URL}/api/entities/group/${group_id}/profile" >"$tmpdir/group-profile.json"
assert_json "$tmpdir/group-profile.json" "payload['paper_count'] >= 2 and len(payload['entity']['members']) == 2"

curl_api "${BASE_URL}/api/entities/institution/${institution_id}/breakdown?limit=10" >"$tmpdir/institution-breakdown.json"
assert_json "$tmpdir/institution-breakdown.json" "payload['author_count'] >= 1 and payload['top_authors'] and '不能作为院系归属' in payload['conclusion_boundary']"

post_json "/api/audits/metadata" "{\"entity_type\":\"group\",\"entity_id\":\"${group_id}\",\"min_cluster_size\":2,\"priority\":6}" "$tmpdir/group-metadata.json"
assert_json "$tmpdir/group-metadata.json" "payload['entity_type'] == 'group' and payload['paper_count'] >= 2"

curl_api "${BASE_URL}/api/reports/entity?entity_type=group&entity_id=${group_id}" >"$tmpdir/group-report.json"
assert_json "$tmpdir/group-report.json" "payload['entity']['entity_type'] == 'group' and '不能据此直接认定' in payload['conclusion_boundary']"

cat >"$tmpdir/source-data.csv" <<'CSV'
replicate,tumor_a,tumor_b,tumor_copy,last_digit
r1,1.10,4.11,1.10,10
r2,2.20,5.12,2.20,20
r3,3.30,6.13,3.30,30
r4,4.40,7.14,4.40,40
r5,5.50,8.15,5.50,50
r6,6.60,9.16,6.60,60
r7,7.70,10.17,7.70,70
r8,8.80,11.18,8.80,80
r9,9.90,12.19,9.90,90
r10,10.00,13.10,10.00,100
CSV

curl_api -X POST "${BASE_URL}/api/artifacts/upload" \
  -H "X-GengScope-Actor: deploy-e2e" \
  -F "doi=${primary_doi}" \
  -F "artifact_type=source_data" \
  -F "source_url=local-upload://deploy-e2e-${run_id}.csv" \
  -F "license_status=manual_upload" \
  -F "file=@${tmpdir}/source-data.csv;type=text/csv" >"$tmpdir/upload.json"
artifact_id="$(json_get "$tmpdir/upload.json" "payload['artifact']['id']")"
assert_json "$tmpdir/upload.json" "payload['material_status'] in {'source_data_found', 'full_auditable'} and payload['artifact']['checksum_sha256']"

post_json "/api/audits/numeric" "{\"artifact_id\":\"${artifact_id}\",\"min_duplicate_length\":3,\"min_last_digit_sample\":10,\"priority\":8}" "$tmpdir/audit.json"
assert_json "$tmpdir/audit.json" "payload['signal_count'] >= 2 and payload['created_review_tasks'] >= 1 and '不能单独证明' in payload['conclusion_boundary']"
signal_id="$(json_get "$tmpdir/audit.json" "payload['signals'][0]['id']")"

curl_api "${BASE_URL}/api/review/tasks?status=open&limit=20" >"$tmpdir/tasks.json"
task_id="$(json_get "$tmpdir/tasks.json" "next(item['id'] for item in payload['items'] if item.get('signal', {}).get('id') == '${signal_id}')")"
post_json "/api/review/tasks/${task_id}/decision" '{"decision":"false_positive","reviewer_note":"deploy e2e smoke check","assigned_to":"deploy-e2e"}' "$tmpdir/decision.json"
assert_json "$tmpdir/decision.json" "payload['status'] == 'closed' and payload['decision'] == 'false_positive'"

post_json "/api/reports/entity/archive" "{\"entity_type\":\"author\",\"entity_id\":\"${author_id}\",\"formats\":[\"json\",\"markdown\"]}" "$tmpdir/archive.json"
assert_json "$tmpdir/archive.json" "payload['total'] == 2 and '不能作为' in payload['conclusion_boundary']"

post_json "/api/jobs/entity-cycle" "{\"entity_type\":\"author\",\"entity_id\":\"${author_id}\",\"discover_artifacts\":false,\"run_metadata_audit\":true,\"min_cluster_size\":2,\"priority\":6}" "$tmpdir/job.json"
job_id="$(json_get "$tmpdir/job.json" "payload['id']")"
post_json "/api/jobs/${job_id}/run" '{}' "$tmpdir/job-run.json"
assert_json "$tmpdir/job-run.json" "payload['status'] == 'succeeded' and payload['result']['profile']['paper_count'] >= 2"

post_json "/api/jobs/schedules/entity-cycle" "{\"name\":\"deploy e2e author audit\",\"interval_seconds\":3600,\"run_immediately\":false,\"job\":{\"entity_type\":\"author\",\"entity_id\":\"${author_id}\",\"discover_artifacts\":false,\"run_metadata_audit\":true,\"min_cluster_size\":2}}" "$tmpdir/schedule.json"
assert_json "$tmpdir/schedule.json" "payload['status'] == 'active' and payload['job_type'] == 'entity_audit_cycle'"

curl_api "${BASE_URL}/api/audit-log?entity_type=author&entity_id=${author_id}&limit=50" >"$tmpdir/audit-log.json"
assert_json "$tmpdir/audit-log.json" "payload['total'] >= 3 and '不能' in payload['conclusion_boundary']"

printf 'GengScope deploy E2E verification passed at %s for author %s.\n' "$BASE_URL" "$author_id"
