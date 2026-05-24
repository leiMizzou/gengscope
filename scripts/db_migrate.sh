#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATIONS_DIR="$ROOT_DIR/infra/migrations"

cd "$ROOT_DIR"

psql_cmd=(
  docker compose -f infra/docker/docker-compose.yml exec -T postgres
  psql --username gengscope --dbname gengscope --set ON_ERROR_STOP=on
)

scalar() {
  "${psql_cmd[@]}" --no-align --tuples-only -c "$1" | tr -d '[:space:]'
}

checksum_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

"${psql_cmd[@]}" <<'SQL'
create table if not exists schema_migrations (
  version text primary key,
  checksum text not null,
  applied_at timestamptz not null default now()
);
SQL

if [[ "$(scalar "select exists(select 1 from schema_migrations);")" == "t" ]] \
  && [[ "$(scalar "select to_regclass('public.papers') is null;")" == "t" ]]; then
  "${psql_cmd[@]}" -c "truncate table schema_migrations;"
  printf 'Detected stale migration ledger without application tables; migrations will be reapplied.\n'
fi

if [[ "$(scalar "select to_regclass('public.papers') is not null;")" == "t" ]] \
  && [[ "$(scalar "select exists(select 1 from schema_migrations where version = '0001_initial');")" == "f" ]]; then
  initial_file="$MIGRATIONS_DIR/0001_initial.sql"
  initial_checksum="$(checksum_file "$initial_file")"
  "${psql_cmd[@]}" \
    -c "insert into schema_migrations(version, checksum) values ('0001_initial', '$initial_checksum');"
  printf 'Baselined existing schema as 0001_initial.\n'
fi

for migration_file in "$MIGRATIONS_DIR"/*.sql; do
  version="$(basename "$migration_file" .sql)"
  checksum="$(checksum_file "$migration_file")"
  if [[ "$(scalar "select exists(select 1 from schema_migrations where version = '$version');")" == "t" ]]; then
    if [[ "${GENGSCOPE_REAPPLY_IDEMPOTENT_MIGRATIONS:-0}" == "1" && "$version" != "0001_initial" ]]; then
      printf 'Reapplying idempotent migration: %s\n' "$version"
      "${psql_cmd[@]}" < "$migration_file"
      continue
    fi
    printf 'Skipping already applied migration: %s\n' "$version"
    continue
  fi
  printf 'Applying migration: %s\n' "$version"
  "${psql_cmd[@]}" < "$migration_file"
  "${psql_cmd[@]}" \
    -c "insert into schema_migrations(version, checksum) values ('$version', '$checksum');"
done

"${psql_cmd[@]}" <<'SQL'
do $$
declare
  missing_tables text[];
begin
  select array_agg(table_name order by table_name)
    into missing_tables
  from unnest(array[
    'algorithmic_signals',
    'audit_logs',
    'authors',
    'authorships',
    'entity_group_members',
    'entity_groups',
    'entity_search_cache',
    'evidence_pointers',
    'institutions',
    'integrity_events',
    'job_runs',
    'job_schedules',
    'papers',
    'report_snapshots',
    'review_tasks',
    'source_artifacts',
    'source_records'
  ]) as expected(table_name)
  where to_regclass('public.' || table_name) is null;

  if coalesce(array_length(missing_tables, 1), 0) > 0 then
    raise exception 'database schema missing required tables: %', array_to_string(missing_tables, ', ');
  end if;
end $$;
SQL

printf 'Database migrations are up to date.\n'
