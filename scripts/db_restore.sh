#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s /path/to/gengscope_backup.sql\n' "$0" >&2
  exit 2
fi

if [[ "${GENGSCOPE_ALLOW_RESTORE:-0}" != "1" ]]; then
  printf 'Refusing to restore without GENGSCOPE_ALLOW_RESTORE=1. Restore replaces data in the local PostgreSQL database.\n' >&2
  exit 3
fi

BACKUP_FILE="$1"
if [[ ! -f "$BACKUP_FILE" ]]; then
  printf 'Backup file not found: %s\n' "$BACKUP_FILE" >&2
  exit 4
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose -f infra/docker/docker-compose.yml exec -T postgres \
  psql --username gengscope --dbname gengscope --set ON_ERROR_STOP=on \
  < "$BACKUP_FILE"

printf 'Restored PostgreSQL backup: %s\n' "$BACKUP_FILE"
