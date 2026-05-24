#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${1:-$ROOT_DIR/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_FILE="$OUTPUT_DIR/gengscope_${TIMESTAMP}.sql"

mkdir -p "$OUTPUT_DIR"
cd "$ROOT_DIR"

docker compose -f infra/docker/docker-compose.yml exec -T postgres \
  pg_dump --username gengscope --dbname gengscope --clean --if-exists --no-owner --no-privileges \
  > "$OUTPUT_FILE"

printf 'Wrote PostgreSQL backup: %s\n' "$OUTPUT_FILE"
