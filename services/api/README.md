# GengScope API

FastAPI backend for the entity-driven GengScope MVP.

This is a local HTTP API service, not an MCP server. Codex, scripts, notebooks, curl, or any HTTP client can call it through `localhost`.

The current vertical slice supports:

- DOI normalization.
- DOI metadata import from OpenAlex and Crossref.
- Author/institution search through OpenAlex.
- Persistent local cache for entity search candidates, with explicit live refresh when needed.
- Entity-driven corpus import for authors and institutions, including batch corpus builds.
- Local group/lab entities that aggregate resolved authors and institutions into one auditable corpus.
- Entity-level coverage and risk profiles.
- Review task creation for auditable papers.
- Source data, PDF and image artifact registration, upload, PMC/landing-page and publisher-aware link discovery, and HTTP/HTTPS fetch into local storage.
- CSV/TSV/XLSX numeric audit for duplicate sequences and last-digit anomalies.
- Image audit for duplicate, flipped, rotated and local crop/patch-similar figure panels.
- Entity metadata audit for publication-year clusters, journal clusters, title-template similarity and signal/event density.
- Golden regression cases for numeric, image and metadata analyzers.
- Synchronous entity audit cycle for artifact discovery, review queue creation and metadata audit in one API call.
- Persistent background job queue plus `gengscope-worker` for corpus builds and entity audit cycles.
- Signal browser for entity-level and global signal lists.
- Entity report export as JSON or Markdown, plus database-backed report archives.
- Review task listing and reviewer decisions.
- Operation audit logs for corpus builds, artifact operations, audit runs, report exports, report archives and review decisions.
- Optional API key protection for `/api/*` when `GENGSCOPE_API_KEY` or `GENGSCOPE_API_KEYS` is configured.
- Idempotent paper/authorship/institution upsert.
- Raw source provenance records with payload hashes.
- Manual integrity event entry with source/status validation.
- Derived risk card endpoint.
- Agent-oriented DOI summary and batch risk-card endpoints.

## Run Locally

From this directory:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e . pytest
gengscope serve --reload
```

The API will be available at:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

`/` serves the local GengScope Workbench. Use it to search authors/institutions, build an entity corpus, create a local group/lab from resolved members, view coverage, upload source data, run numeric audit, and close review tasks.

By default the service uses SQLite at `./gengscope_api.db`. Use `--database-url` or set `DATABASE_URL` to point at PostgreSQL when running against the docker-compose database.

```bash
gengscope serve --reload \
  --database-url postgresql+psycopg://gengscope:gengscope@localhost:54329/gengscope
```

Useful local options:

```bash
gengscope serve --host 127.0.0.1 --port 8010 --reload
```

Optional local API key protection:

```bash
GENGSCOPE_API_KEY=local-secret gengscope serve --host 127.0.0.1 --port 8010
curl -H "X-API-Key: local-secret" http://127.0.0.1:8010/api/papers
```

`GENGSCOPE_API_KEYS` accepts a comma-separated list. Health checks and the workbench shell remain reachable, while `/api/*` requires `X-API-Key`, `X-GengScope-API-Key` or `Authorization: Bearer <key>`.

Assign optional roles to keys with `GENGSCOPE_API_KEY_ROLES`:

```bash
GENGSCOPE_API_KEYS=read-key,reviewer-key,admin-key \
GENGSCOPE_API_KEY_ROLES=read-key:read,reviewer-key:reviewer,admin-key:admin \
gengscope serve --host 127.0.0.1 --port 8010
```

Roles are intentionally simple for local deployment:

- `read`: can call `GET /api/*`.
- `reviewer`: can run corpus, artifact, audit, review, report and job workflows, but cannot call `/api/admin/*` or prune report archives.
- `admin`: full `/api/*` access.

Keys without an explicit role default to `admin` for backward compatibility.

## Run With Docker Compose

From the repo root:

```bash
cd /Users/mac/Documents/GitHub/gengscope
cp infra/docker/.env.example infra/docker/.env
docker compose -f infra/docker/docker-compose.yml up --build api worker
```

The workbench and API docs will be available at:

```text
http://127.0.0.1:8010/
http://127.0.0.1:8010/docs
```

This starts PostgreSQL, the API service and the background worker. The API and worker containers use:

```text
postgresql+psycopg://gengscope:gengscope@postgres:5432/gengscope
```

The compose host port defaults to `8010` to avoid conflicts with other local FastAPI projects. Override it when needed:

```bash
GENGSCOPE_API_PORT=8000 docker compose -f infra/docker/docker-compose.yml up --build api
```

The compose file passes through `GENGSCOPE_API_KEY`, `GENGSCOPE_API_KEYS`, `GENGSCOPE_API_KEY_ROLES`, `OPENALEX_EMAIL`, `HTTP_TIMEOUT_SECONDS`, `ENTITY_SEARCH_CACHE_TTL_SECONDS`, `ARTIFACT_FETCH_MAX_BYTES`, `ARTIFACT_FETCH_ALLOW_PRIVATE_NETWORKS` and `ARTIFACT_FETCH_MIN_INTERVAL_SECONDS`. Keep `infra/docker/.env` local and rotate keys before exposing the service beyond a trusted machine. Remote artifact fetching blocks private, loopback, link-local, multicast and reserved network addresses by default; enable private network fetching only for a trusted internal mirror.

Run the deploy smoke test from the repo root:

```bash
scripts/verify_deploy.sh
```

It builds API/worker images, starts the compose stack, runs migrations, checks `/health/ready`, verifies core OpenAPI routes, calls the report archive prune endpoint in dry-run mode, then runs a deterministic deployed E2E flow with synthetic demo data: entity profile, local group/lab profile, artifact upload, numeric audit, review decision, report archive, job execution and recurring schedule creation.

If you only need to re-run the deployed E2E portion against an already running compose stack:

```bash
scripts/verify_deploy_e2e.sh
```

Compose waits for PostgreSQL readiness before starting the API and worker, checks API readiness through `/health/ready` for database reachability, required migrations and artifact-volume writability, and persists uploaded artifacts in the `gengscope_artifacts` Docker volume at `/data/artifacts`.

Back up and restore the local PostgreSQL database:

```bash
cd /Users/mac/Documents/GitHub/gengscope
scripts/db_migrate.sh
scripts/db_backup.sh
GENGSCOPE_ALLOW_RESTORE=1 scripts/db_restore.sh backups/gengscope_YYYYMMDD_HHMMSS.sql
```

`scripts/db_migrate.sh` records applied SQL files in `schema_migrations`. If it sees an existing schema created by SQLAlchemy before migrations were introduced, it baselines `0001_initial` and then applies later idempotent migrations.
After disposable test resets or manual table recreation, repair idempotent indexes/columns with:

```bash
GENGSCOPE_REAPPLY_IDEMPOTENT_MIGRATIONS=1 scripts/db_migrate.sh
```

When upgrading an older local SQLite database, delete the old development database or run the matching migration before using the new entity-corpus fields.

## Test

```bash
python -m pytest
```

The test suite uses in-memory SQLite and fake OpenAlex/Crossref clients, so it does not require network access.

For live OpenAlex/Crossref and PostgreSQL integration checks, see [TESTING.md](TESTING.md).

## Core Endpoints

```text
GET  /health
GET  /health/ready
GET  /api/papers?query=
GET  /api/papers/{doi}
GET  /api/papers/{doi}/risk-card
POST /api/admin/import/doi
POST /api/admin/events
GET  /api/entities/search?entity_type=author&query=
POST /api/entities/corpus
POST /api/entities/corpus/batch
POST /api/entities/corpus/import
POST /api/entities/groups
POST /api/entities/groups/corpus
GET  /api/entities/{entity_type}/{entity_id}/profile
GET  /api/entities/{entity_type}/{entity_id}/breakdown
POST /api/entities/review-queue
POST /api/artifacts/register
POST /api/artifacts/upload
POST /api/artifacts/discover
POST /api/artifacts/fetch
GET  /api/artifacts/papers/{paper_id}
POST /api/audits/numeric
POST /api/audits/image
POST /api/audits/metadata
POST /api/audits/entity-cycle
GET  /api/signals
GET  /api/entities/{entity_type}/{entity_id}/signals
GET  /api/reports/entity
POST /api/reports/entity/archive
GET  /api/reports/archive
POST /api/reports/archive/prune
GET  /api/reports/archive/{snapshot_id}
GET  /api/review/tasks
POST /api/review/tasks/{task_id}/decision
GET  /api/audit-log
GET  /api/jobs
GET  /api/jobs/{job_id}
POST /api/jobs/entity-corpus
POST /api/jobs/entity-cycle
POST /api/jobs/entity-cycle/batch
GET  /api/jobs/schedules
POST /api/jobs/schedules/entity-cycle
POST /api/jobs/schedules/run-due
POST /api/jobs/schedules/{schedule_id}/status
POST /api/jobs/{job_id}/run
POST /api/jobs/{job_id}/retry
GET  /api/agent/doi/{doi}
POST /api/agent/batch-risk-cards
```

DOIs contain `/`; URL-encode them when calling path endpoints directly. For example:

```bash
curl "http://localhost:8000/api/agent/doi/10.1234%2Fexample.paper"
```

## CLI Commands

The `gengscope` CLI is the stable local automation surface for shell users, CI jobs and AI skills:

```bash
gengscope init
gengscope health --base-url http://127.0.0.1:8010
gengscope search "Alice Zhang" --entity-type author --base-url http://127.0.0.1:8010
gengscope build-corpus "Tsinghua University" --entity-type institution --limit 50 --year-from 2020 --year-to 2026
gengscope import-doi "10.1038/s41586-024-08248-5"
gengscope risk-card "10.1038/s41586-024-08248-5"
gengscope agent-summary "10.1038/s41586-024-08248-5"
gengscope batch-risk-cards "10.x/a" "10.x/b"
gengscope entity-profile author <entity_id>
gengscope audit-cycle institution <entity_id> --inspect-landing-pages
gengscope report institution <entity_id>
gengscope archive-report institution <entity_id>
```

Add `--api-key` for protected deployments and `--actor` when you want audit-log attribution.

## Example Loop

```bash
curl -X POST http://localhost:8000/api/admin/import/doi \
  -H "content-type: application/json" \
  -d '{"doi":"10.1038/s41586-024-08248-5","sources":["openalex","crossref"]}'

curl -X POST http://localhost:8000/api/admin/events \
  -H "content-type: application/json" \
  -d '{
    "doi": "10.1038/s41586-024-08248-5",
    "event_type": "institution_notice",
    "status_level": "institution_investigation",
    "source_type": "institution",
    "source_name": "Example University",
    "source_url": "https://example.edu/notice",
    "claim_summary": "机构公告称已成立调查组。",
    "verification_status": "source_verified"
  }'

curl "http://localhost:8000/api/agent/doi/10.1038%2Fs41586-024-08248-5"
```

## Entity-Driven Corpus Loop

Search for an author or institution:

```bash
curl "http://localhost:8000/api/entities/search?entity_type=author&query=Alice%20Zhang"
```

The first search may use live OpenAlex and can take seconds. The response is persisted in the local `entity_search_cache`; repeating the same `entity_type` + normalized query + `limit` returns immediately from the database:

```json
{
  "items": [],
  "cached": true,
  "source": "cache",
  "cache_status": "fresh",
  "fetched_at": "2026-05-23T00:00:00+00:00",
  "expires_at": "2026-05-30T00:00:00+00:00"
}
```

By default the API prefers responsiveness and will serve an expired cache entry as `cache_status: "stale"` until you force a refresh. Use `refresh=true` when you explicitly want to wait for a live OpenAlex update:

```bash
curl "http://localhost:8000/api/entities/search?entity_type=author&query=Alice%20Zhang&refresh=true"
```

The cache TTL defaults to 7 days and can be changed with `ENTITY_SEARCH_CACHE_TTL_SECONDS`.

Build a local corpus from OpenAlex:

```bash
curl -X POST http://localhost:8000/api/entities/corpus \
  -H "content-type: application/json" \
  -d '{
    "entity_type": "author",
    "query": "Alice Zhang",
    "limit": 25,
    "year_from": 2020,
    "year_to": 2026
  }'
```

The response includes an entity profile:

```json
{
  "paper_count": 25,
  "auditable_paper_count": 8,
  "audited_paper_count": 0,
  "signal_paper_count": 0,
  "official_event_count": 0,
  "public_discussion_count": 0,
  "auditable_coverage": 0.32,
  "sample_inference": {
    "audited_sample_size": 0,
    "observed_signal_rate": 0,
    "reliability": "not_available",
    "extrapolation_boundary": "该区间只描述已审计样本中算法信号率的不确定性；全文可得性和上传材料可能有偏，不能外推为全库造假比例或事实结论。"
  },
  "priority": "medium",
  "summary": "已索引 25 篇论文，其中 8 篇存在可审计全文或材料。"
}
```

Build several entity corpora in one request:

```bash
curl -X POST http://localhost:8000/api/entities/corpus/batch \
  -H "content-type: application/json" \
  -d '{
    "items": [
      {"entity_type":"author","query":"Alice Zhang","limit":25},
      {"entity_type":"institution","query":"Example University","limit":25}
    ],
    "continue_on_error": true
  }'
```

Import an entity manifest file:

```bash
curl -X POST http://localhost:8000/api/entities/corpus/import \
  -F "file=@entities.csv;type=text/csv" \
  -F "default_limit=25" \
  -F "continue_on_error=true"
```

CSV/TSV headers can include `entity_type`, `query`, `name`, `openalex_id`, `display_name`, `limit`, `year_from` and `year_to`. JSON manifests can be a list or `{ "items": [...] }`.

Queue auditable papers for review:

```bash
curl -X POST http://localhost:8000/api/entities/review-queue \
  -H "content-type: application/json" \
  -d '{"entity_type":"author","entity_id":"<local-author-id>","priority":7}'
```

## Artifact And Numeric Audit Loop

Upload a local source data file for a paper:

```bash
curl -X POST http://localhost:8000/api/artifacts/upload \
  -F "paper_id=<local-paper-id>" \
  -F "artifact_type=source_data" \
  -F "license_status=manual_upload" \
  -F "file=@source-data.csv;type=text/csv"
```

Discover known landing/PDF URLs and fetch a selected URL into local artifact storage:

```bash
curl -X POST http://localhost:8000/api/artifacts/discover \
  -H "content-type: application/json" \
  -d '{"paper_id":"<local-paper-id>"}'

curl -X POST http://localhost:8000/api/artifacts/fetch \
  -H "content-type: application/json" \
  -d '{"artifact_id":"<artifact-id>","license_status":"open_or_linked"}'
```

For deeper material discovery, let the service inspect the known landing page, PMC page or PubMed page and register matching PDF, source data, supplementary and figure links:

```bash
curl -X POST http://localhost:8000/api/artifacts/discover \
  -H "content-type: application/json" \
  -d '{"paper_id":"<local-paper-id>","inspect_landing_pages":true,"max_landing_pages":3,"max_discovered_links":30}'
```

The deep discovery path includes publisher-aware extraction for common Nature/Springer static supplementary files, ScienceDirect/Elsevier `mmc` downloads, Wiley `downloadSupplement` links, Cell attachments, PLOS supplementary files, MDPI supplementary attachments, Frontiers data sheets, Taylor & Francis supplements and BMJ supplementary files. It still records source URLs only; fetching into local storage remains a separate explicit `/api/artifacts/fetch` step.

Remote fetch requires an explicit fetchable `license_status`, rejects HTML login/error pages for auditable files, respects `ARTIFACT_FETCH_MAX_BYTES`, and can add a per-host politeness delay with `ARTIFACT_FETCH_MIN_INTERVAL_SECONDS`.

You can also fetch a new URL directly:

```bash
curl -X POST http://localhost:8000/api/artifacts/fetch \
  -H "content-type: application/json" \
  -d '{"paper_id":"<local-paper-id>","artifact_type":"source_data","source_url":"https://example.org/source-data.csv"}'
```

Run numeric audit on the uploaded artifact:

```bash
curl -X POST http://localhost:8000/api/audits/numeric \
  -H "content-type: application/json" \
  -d '{"artifact_id":"<artifact-id>","priority":8}'
```

List and decide review tasks:

```bash
curl "http://localhost:8000/api/review/tasks"

curl -X POST http://localhost:8000/api/review/tasks/<task-id>/decision \
  -H "content-type: application/json" \
  -d '{"decision":"confirmed_signal","reviewer_note":"人工复核确认该数值信号需要保留。"}'
```

Numeric audit currently supports CSV, TSV and first-sheet XLSX/XLSM files. It detects repeated numeric sequences and last-digit distribution anomalies. Results are stored as `algorithmic_signal` records and cannot be treated as official misconduct findings without external confirmation.

Image audit currently supports locally uploaded image artifacts such as PNG/JPEG/WebP/TIFF. It compares a target image against other image artifacts on the same paper, including flipped/rotated variants and local crop/patch reuse:

```bash
curl -X POST http://localhost:8000/api/audits/image \
  -H "content-type: application/json" \
  -d '{"artifact_id":"<figure-artifact-id>","enable_patch_similarity":true,"priority":8}'
```

Run metadata audit for an entity:

```bash
curl -X POST http://localhost:8000/api/audits/metadata \
  -H "content-type: application/json" \
  -d '{"entity_type":"author","entity_id":"<local-author-id>","min_cluster_size":5,"priority":6}'
```

Create a local lab/group entity after building the relevant author or institution corpora:

```bash
curl -X POST http://localhost:8000/api/entities/groups \
  -H "content-type: application/json" \
  -d '{
    "display_name": "Example Lab",
    "members": [
      {"entity_type":"author","entity_id":"<local-author-id>","label":"PI"},
      {"entity_type":"institution","entity_id":"<local-institution-id>","label":"School"}
    ]
  }'

curl "http://localhost:8000/api/entities/group/<local-group-id>/profile"
```

The group profile deduplicates papers across members. It is useful for lab-level coverage and review priority, but remains an audit scope, not a factual misconduct label.

Inspect an entity's internal breakdown from raw affiliation metadata:

```bash
curl "http://localhost:8000/api/entities/institution/<local-institution-id>/breakdown?limit=25&min_papers=1"
```

For an institution, this groups raw affiliations into heuristic units such as school, department, institute, laboratory, hospital and center, and also lists top local authors. It is a navigation and review-priority tool, not a definitive department roster.

Add `"inspect_landing_pages": true` to the entity cycle request when you want the worker/API to inspect publisher/PMC/PubMed pages during discovery. Keep it off for very large batches unless you are prepared for external HTTP latency.

Run the synchronous entity audit cycle:

```bash
curl -X POST http://localhost:8000/api/audits/entity-cycle \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"entity_type":"author","entity_id":"<local-author-id>","min_cluster_size":5,"priority":6}'
```

Queue the same workflow for the background worker:

```bash
curl -X POST http://localhost:8000/api/jobs/entity-corpus \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"entity_type":"author","query":"Alice Zhang","limit":25,"year_from":2020,"year_to":2026}'

curl -X POST http://localhost:8000/api/jobs/entity-cycle \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"entity_type":"author","entity_id":"<local-author-id>","min_cluster_size":5,"priority":6}'

curl "http://localhost:8000/api/jobs?status=queued"
curl "http://localhost:8000/api/jobs/<job-id>"
```

`/api/jobs/entity-corpus` is the faster Workbench path for large or slow upstream searches: select a candidate card, queue “后台建库”, then watch `/api/jobs` or the Workbench log instead of blocking the page.

Queue several entity audit cycles:

```bash
curl -X POST http://localhost:8000/api/jobs/entity-cycle/batch \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"items":[{"entity_type":"author","entity_id":"<author-id>"},{"entity_type":"institution","entity_id":"<institution-id>"}]}'
```

Create a recurring entity audit schedule:

```bash
curl -X POST http://localhost:8000/api/jobs/schedules/entity-cycle \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{
    "name": "weekly Alice audit",
    "interval_seconds": 604800,
    "run_immediately": false,
    "max_attempts": 2,
    "job": {
      "entity_type": "author",
      "entity_id": "<local-author-id>",
      "inspect_landing_pages": true,
      "min_cluster_size": 5,
      "priority": 6
    }
  }'

curl "http://localhost:8000/api/jobs/schedules?status=active"
```

The compose worker checks due schedules before polling queued jobs. For local testing, `POST /api/jobs/schedules/run-due` enqueues due schedules immediately.

For a local single-shot run without the compose worker:

```bash
gengscope-worker --once
```

For long-running local workers, stale recovery can requeue or fail jobs that were left in `running` after a worker crash:

```bash
gengscope-worker --poll-interval 5 --recover-stale-after 3600
```

Browse signals for an entity:

```bash
curl "http://localhost:8000/api/entities/author/<local-author-id>/signals?status=all"
```

Export an entity report:

```bash
curl "http://localhost:8000/api/reports/entity?entity_type=author&entity_id=<local-author-id>"

curl "http://localhost:8000/api/reports/entity?entity_type=author&entity_id=<local-author-id>&format=markdown"
```

Archive the current entity report as reproducible JSON and Markdown snapshots:

```bash
curl -X POST http://localhost:8000/api/reports/entity/archive \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"entity_type":"author","entity_id":"<local-author-id>","formats":["json","markdown"]}'

curl "http://localhost:8000/api/reports/archive?entity_type=author&entity_id=<local-author-id>"

curl "http://localhost:8000/api/reports/archive/<snapshot-id>?format=markdown"

curl -X POST http://localhost:8000/api/reports/archive/prune \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"entity_type":"author","entity_id":"<local-author-id>","keep_latest":20,"older_than_days":180,"dry_run":true}'
```

Inspect operation history:

```bash
curl "http://localhost:8000/api/audit-log?entity_type=author&entity_id=<local-author-id>"
```

The audit log records system actions and reviewer decisions only. It cannot be used as evidence that a paper, author, lab or institution committed misconduct.

Run a public real-case E2E smoke against a running API:

```bash
cd /Users/mac/Documents/GitHub/gengscope
scripts/run_real_case_e2e.py --base-url http://127.0.0.1:8010
```

The script imports a publicly indexed retracted article, records the publisher retraction notice as an official event, discovers linked materials, then reports the linked authors, institution profile and affiliation breakdown. It is intentionally source-attributed and does not make an independent misconduct finding.

Metadata audit detects entity-level patterns such as publication-year clusters, journal clusters, title-template similarity, public event density and high signal density among audited samples. It deliberately excludes its own metadata signals when computing signal-density findings so repeated runs do not amplify prior metadata results.

The agent endpoint returns JSON shaped like:

```json
{
  "paper": {
    "doi": "10.1038/s41586-024-08248-5",
    "title": "...",
    "journal_name": "...",
    "publication_year": 2024
  },
  "risk_card": {
    "official_status": "none",
    "institution_status": "investigation",
    "public_discussion_count": 0,
    "algorithmic_signal_count": 0,
    "highest_signal_level": "investigation",
    "summary": "存在机构调查记录，尚未发现期刊撤稿、更正或关注表达记录。"
  },
  "events": [],
  "evidence": [],
  "conclusion_boundary": "以上为已索引的公开状态、公开讨论和算法信号，不能据此直接认定论文造假。"
}
```
