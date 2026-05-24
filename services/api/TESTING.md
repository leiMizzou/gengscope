# Testing GengScope API

The API has three test levels:

1. Offline tests: deterministic, no network, in-memory SQLite.
2. Live metadata smoke test: hits real OpenAlex and Crossref APIs.
3. PostgreSQL integration test: runs the HTTP API loop against a disposable PostgreSQL database.

## 1. Offline Tests

Run these during normal development:

```bash
cd /Users/mac/Documents/GitHub/gengscope/services/api
python -m pytest
```

These tests cover:

- DOI normalization.
- Idempotent DOI import using fake OpenAlex/Crossref clients.
- Authorship, institution and source provenance persistence.
- Manual event validation.
- Risk card derivation and precedence.
- HTTP loop: import DOI -> create event -> paper detail -> risk card -> agent summary.
- Entity loop: search author/institution -> build single, batch or CSV/TSV/JSON-manifest local corpus -> profile coverage -> sample inference boundary -> queue review tasks.
- Artifact loop: discover PMC/landing-page and publisher-specific material links, upload source data or fetch a registered URL -> run numeric audit -> create signals/evidence -> decide review task.
- Image loop: upload figure images -> run image audit -> create whole-panel and crop/patch similarity signals and review tasks.
- Metadata loop: run entity metadata audit -> browse entity signals -> verify reruns are idempotent, including title-template similarity clusters.
- Golden regression loop: load `data/seeds/golden_algorithm_cases.json` and verify expected numeric, image and metadata signal outputs plus review-label boundary fields.
- Entity audit cycle loop: one API call runs artifact discovery, review queue creation, metadata audit and audit-log recording.
- Job queue loop: enqueue single, batch or recurring scheduled entity audit cycles, run them through the worker path, query status, retry a failed job and recover stale running jobs.
- Report loop: export entity JSON/Markdown report, archive JSON/Markdown snapshots, list/fetch/prune snapshots and verify content hashes.
- Audit log loop: verify corpus build, metadata audit, report export, report archive and report archive prune actions are recorded with actor and metadata.
- Optional API key loop: verify `/api/*` is open by default, protected when keys are set, and role-gated for read/reviewer/admin keys.
- Local CLI argument handling and API command payloads.

Expected result:

```text
passed
```

## 2. Live Metadata Smoke Test

Run this when you want to verify the real OpenAlex/Crossref path:

```bash
cd /Users/mac/Documents/GitHub/gengscope/services/api
GENGSCOPE_RUN_LIVE=1 python -m pytest -m live
```

Optional DOI override:

```bash
GENGSCOPE_RUN_LIVE=1 \
GENGSCOPE_LIVE_DOI=10.1038/s41586-024-08248-5 \
python -m pytest -m live
```

This test imports a real DOI into in-memory SQLite and asserts:

- normalized DOI is stored;
- title and landing page are present;
- authorships are imported;
- both OpenAlex and Crossref source records are saved;
- source payload hashes are present.

Do not make this part of every local run; it depends on network availability and upstream API behavior.

## 3. PostgreSQL Integration Test

Install PostgreSQL driver support:

```bash
cd /Users/mac/Documents/GitHub/gengscope/services/api
python -m pip install -e ".[postgres]" pytest
```

Start the local database from the repo root:

```bash
cd /Users/mac/Documents/GitHub/gengscope
docker compose -f infra/docker/docker-compose.yml up -d postgres
```

Run the PostgreSQL loop test:

```bash
cd /Users/mac/Documents/GitHub/gengscope/services/api
GENGSCOPE_POSTGRES_URL=postgresql+psycopg://gengscope:gengscope@localhost:54329/gengscope \
GENGSCOPE_ALLOW_DB_RESET=1 \
python -m pytest -m postgres
```

Important: `GENGSCOPE_ALLOW_DB_RESET=1` is required because the test drops and recreates the GengScope tables in the target database. Use only a disposable local database.

This test uses fake OpenAlex/Crossref clients, but real PostgreSQL storage, and verifies:

- SQLAlchemy table creation works on PostgreSQL;
- the HTTP import endpoint writes metadata and source records;
- the event endpoint writes validated integrity events;
- the agent endpoint derives the expected institution risk card.
- the entity corpus endpoint imports an author corpus into PostgreSQL;
- the review queue endpoint creates artifact audit tasks.

## 4. Docker Deploy E2E Smoke

Run the full deploy smoke from the repo root:

```bash
cd /Users/mac/Documents/GitHub/gengscope
scripts/verify_deploy.sh
```

The script builds API and worker images, starts Docker Compose, runs SQL migrations and checks the deployed HTTP API. It then seeds deterministic synthetic demo records inside the Docker database and verifies:

- entity profile returns a usable corpus and conclusion boundary;
- source-data upload persists a local artifact checksum;
- numeric audit creates algorithmic signals and review tasks;
- a reviewer decision closes a task without turning the signal into a misconduct conclusion;
- entity reports can be archived as JSON and Markdown snapshots;
- a background entity audit job can be enqueued and run;
- a recurring entity audit schedule can be created;
- audit logs are queryable for the deployed flow.

To re-run only the deployed E2E section against an already running compose stack:

```bash
scripts/verify_deploy_e2e.sh
```

If API keys are enabled, provide a reviewer or admin key through `GENGSCOPE_DEPLOY_VERIFY_API_KEY`, `GENGSCOPE_API_KEY`, or the first value in `GENGSCOPE_API_KEYS`.

## 5. Public Demo Smoke

Run the demo publication smoke from the repo root:

```bash
cd /Users/mac/Documents/GitHub/gengscope
scripts/verify_demo_publish.sh
```

The script starts the base compose stack with `infra/docker/docker-compose.demo.yml`, seeds deterministic synthetic demo records, verifies the agent DOI summary with the public read key, and confirms that the same read key is blocked from write/admin endpoints.

## Full Manual API Check

Start the service:

```bash
cd /Users/mac/Documents/GitHub/gengscope/services/api
gengscope serve --reload
```

Check health:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/ready
```

Import a DOI:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/import/doi \
  -H "content-type: application/json" \
  -d '{"doi":"10.1038/s41586-024-08248-5","sources":["openalex","crossref"]}'
```

Create an event:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/events \
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
```

Query the agent summary:

```bash
curl "http://127.0.0.1:8000/api/agent/doi/10.1038%2Fs41586-024-08248-5"
```

Build an entity corpus:

```bash
curl -X POST http://127.0.0.1:8000/api/entities/corpus \
  -H "content-type: application/json" \
  -d '{"entity_type":"author","query":"Alice Zhang","limit":25}'
```

Build a batch entity corpus:

```bash
curl -X POST http://127.0.0.1:8000/api/entities/corpus/batch \
  -H "content-type: application/json" \
  -d '{"items":[{"entity_type":"author","query":"Alice Zhang","limit":25},{"entity_type":"institution","query":"Example University","limit":25}]}'
```

Import an entity manifest:

```bash
curl -X POST http://127.0.0.1:8000/api/entities/corpus/import \
  -F "file=@entities.csv;type=text/csv" \
  -F "default_limit=25" \
  -F "continue_on_error=true"
```

The entity corpus response should include:

- `entity`
- `profile`
- `profile.sample_inference`
- `profile.conclusion_boundary`

The `conclusion_boundary` must preserve the product rule that indexed signals cannot be used to directly label a paper as fraudulent.

Upload a source data fixture:

```bash
curl -X POST http://127.0.0.1:8000/api/artifacts/upload \
  -F "paper_id=<local-paper-id>" \
  -F "artifact_type=source_data" \
  -F "license_status=manual_upload" \
  -F "file=@source-data.csv;type=text/csv"
```

Run numeric audit:

```bash
curl -X POST http://127.0.0.1:8000/api/audits/numeric \
  -H "content-type: application/json" \
  -d '{"artifact_id":"<artifact-id>","priority":8}'
```

Fetch a discovered or known artifact URL into local storage:

```bash
curl -X POST http://127.0.0.1:8000/api/artifacts/discover \
  -H "content-type: application/json" \
  -d '{"paper_id":"<local-paper-id>","inspect_landing_pages":true,"max_landing_pages":3,"max_discovered_links":30}'

curl -X POST http://127.0.0.1:8000/api/artifacts/fetch \
  -H "content-type: application/json" \
  -d '{"artifact_id":"<artifact-id>","license_status":"open_or_linked"}'
```

Run image audit on an uploaded figure image:

```bash
curl -X POST http://127.0.0.1:8000/api/audits/image \
  -H "content-type: application/json" \
  -d '{"artifact_id":"<figure-artifact-id>","enable_patch_similarity":true,"priority":8}'
```

Run metadata audit and browse entity signals:

```bash
curl -X POST http://127.0.0.1:8000/api/audits/metadata \
  -H "content-type: application/json" \
  -d '{"entity_type":"author","entity_id":"<local-author-id>","min_cluster_size":5,"priority":6}'

curl "http://127.0.0.1:8000/api/entities/author/<local-author-id>/signals?status=all"

curl "http://127.0.0.1:8000/api/reports/entity?entity_type=author&entity_id=<local-author-id>&format=markdown"

curl -X POST http://127.0.0.1:8000/api/reports/entity/archive \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"entity_type":"author","entity_id":"<local-author-id>","formats":["json","markdown"]}'

curl "http://127.0.0.1:8000/api/reports/archive?entity_type=author&entity_id=<local-author-id>"

curl "http://127.0.0.1:8000/api/reports/archive/<snapshot-id>?format=markdown"

curl -X POST http://127.0.0.1:8000/api/reports/archive/prune \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"entity_type":"author","entity_id":"<local-author-id>","keep_latest":20,"older_than_days":180,"dry_run":true}'
```

Run the synchronous entity audit cycle:

```bash
curl -X POST http://127.0.0.1:8000/api/audits/entity-cycle \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"entity_type":"author","entity_id":"<local-author-id>","min_cluster_size":5,"priority":6}'
```

Queue the same cycle for the background worker:

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/entity-cycle \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"entity_type":"author","entity_id":"<local-author-id>","min_cluster_size":5,"priority":6}'

curl "http://127.0.0.1:8000/api/jobs?status=queued"
```

Queue batch entity audit jobs:

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/entity-cycle/batch \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"items":[{"entity_type":"author","entity_id":"<local-author-id>"},{"entity_type":"institution","entity_id":"<local-institution-id>"}]}'
```

Create a recurring entity audit schedule:

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/schedules/entity-cycle \
  -H "content-type: application/json" \
  -H "X-GengScope-Actor: local-ci" \
  -d '{"name":"weekly audit","interval_seconds":604800,"job":{"entity_type":"author","entity_id":"<local-author-id>","inspect_landing_pages":true,"min_cluster_size":5}}'

curl "http://127.0.0.1:8000/api/jobs/schedules?status=active"
```

Review the generated task:

```bash
curl "http://127.0.0.1:8000/api/review/tasks"

curl -X POST http://127.0.0.1:8000/api/review/tasks/<task-id>/decision \
  -H "content-type: application/json" \
  -d '{"decision":"false_positive","reviewer_note":"人工复核判定为误报。"}'
```

Inspect the operation audit log:

```bash
curl "http://127.0.0.1:8000/api/audit-log?entity_type=author&entity_id=<local-author-id>"
```

Run the local verification wrapper from the repo root:

```bash
cd /Users/mac/Documents/GitHub/gengscope
scripts/verify_local.sh
```

Set `GENGSCOPE_VERIFY_DOCKER_BUILD=1` to include API and worker image builds. The CI workflow runs offline tests, the PostgreSQL loop and Docker Compose config validation.

Run the deploy smoke test when validating a local release candidate:

```bash
cd /Users/mac/Documents/GitHub/gengscope
scripts/verify_deploy.sh
```

For CI or parallel local stacks, override ports:

```bash
GENGSCOPE_API_PORT=18010 GENGSCOPE_POSTGRES_PORT=15432 scripts/verify_deploy.sh
```

Golden analyzer baselines live in:

```text
data/seeds/golden_algorithm_cases.json
```

These cases are deterministic regression fixtures with review-priority labels. They are not misconduct labels and should only be used to detect analyzer output drift in CI.

Verify migrations against the compose PostgreSQL service:

```bash
cd /Users/mac/Documents/GitHub/gengscope
scripts/db_migrate.sh
scripts/db_migrate.sh
```

The second run should skip every already applied migration.

Verify backup creation against the compose PostgreSQL service:

```bash
cd /Users/mac/Documents/GitHub/gengscope
scripts/db_backup.sh
```

Restore is intentionally guarded:

```bash
GENGSCOPE_ALLOW_RESTORE=1 scripts/db_restore.sh backups/gengscope_YYYYMMDD_HHMMSS.sql
```
