# GengScope API Reference

Use these calls against the local API base URL, usually `http://127.0.0.1:8010`.

## CLI

```bash
gengscope health --base-url http://127.0.0.1:8010
gengscope search "Alice Zhang" --entity-type author --limit 10
gengscope build-corpus "Tsinghua University" --entity-type institution --limit 50 --year-from 2020 --year-to 2026
gengscope import-doi "10.1038/example"
gengscope risk-card "10.1038/example"
gengscope agent-summary "10.1038/example"
gengscope batch-risk-cards "10.x/a" "10.x/b"
gengscope entity-profile author <entity_id>
gengscope audit-cycle institution <entity_id> --inspect-landing-pages
gengscope report institution <entity_id>
gengscope archive-report institution <entity_id>
```

Add `--base-url`, `--api-key`, and `--actor` when needed.

## Core HTTP Endpoints

```text
GET  /health/ready
GET  /api/papers?query=
GET  /api/papers?doi=
GET  /api/papers/{doi}
GET  /api/papers/{doi}/risk-card
GET  /api/agent/doi/{doi}
POST /api/agent/batch-risk-cards
POST /api/admin/import/doi
POST /api/admin/events
GET  /api/entities/search
POST /api/entities/corpus
POST /api/entities/corpus/import
POST /api/entities/groups
POST /api/entities/groups/corpus
GET  /api/entities/{entity_type}/{entity_id}/profile
GET  /api/entities/{entity_type}/{entity_id}/breakdown
POST /api/audits/numeric
POST /api/audits/image
POST /api/audits/metadata
POST /api/audits/entity-cycle
GET  /api/signals
GET  /api/review/tasks
POST /api/review/tasks/{task_id}/decision
GET  /api/reports/entity
POST /api/reports/entity/archive
GET  /api/reports/archive
GET  /api/audit-log
GET  /api/jobs
POST /api/jobs/entity-corpus
POST /api/jobs/entity-cycle
POST /api/jobs/schedules/entity-cycle
```

URL-encode DOI slashes in path endpoints, for example `10.1038%2Fexample`.

## Required Boundary

Every report should preserve this meaning:

```text
GengScope returns indexed public statuses, public discussions, material coverage, and algorithmic signals for human review. These records do not by themselves prove misconduct.
```
