# API Contract

This document defines the first API surface for the entity-driven local API MVP.

## 1. Principles

- API responses must separate official events, public discussion and algorithmic signals.
- Every material claim must include a source URL or evidence pointer.
- DOI input is case-insensitive and normalized before lookup.
- Author and institution workflows start from candidate entities, not DOI-only imports.
- Candidate entity search is cached locally; clients can request a live refresh explicitly.
- Agent endpoints return compact JSON and avoid UI-only fields.

## 2. Common Types

When `GENGSCOPE_API_KEY` or `GENGSCOPE_API_KEYS` is configured, every `/api/*` endpoint requires one of:

```text
X-API-Key: <key>
X-GengScope-API-Key: <key>
Authorization: Bearer <key>
```

Clients can also send `X-GengScope-Actor` on write/review/report actions so audit logs identify the local reviewer or automation.

Optional key roles can be configured with `GENGSCOPE_API_KEY_ROLES`:

```text
GENGSCOPE_API_KEYS=read-key,reviewer-key,admin-key
GENGSCOPE_API_KEY_ROLES=read-key:read,reviewer-key:reviewer,admin-key:admin
```

`read` keys can call `GET /api/*`; `reviewer` keys can run normal corpus, artifact, audit, review, report and job workflows but cannot call `/api/admin/*` or prune report archives; `admin` keys have full `/api/*` access. Existing keys without explicit roles default to `admin`.

### RiskStatus

```json
{
  "official_status": "none | corrected | retracted | expression_of_concern",
  "institution_status": "none | investigation | conclusion",
  "publisher_status": "none | editor_note | correction | retraction | expression_of_concern",
  "public_discussion_count": 0,
  "media_report_count": 0,
  "algorithmic_signal_count": 0,
  "highest_signal_level": "none | algorithmic | public_discussion | investigation | official",
  "summary": "存在公开讨论，尚未发现官方结论。"
}
```

### EvidencePointer

```json
{
  "id": "uuid",
  "figure_label": "Fig. 4c",
  "table_label": "Source Data Fig. 4",
  "panel_label": "c",
  "column_name": "tumor_volume",
  "artifact_url": "https://...",
  "evidence_url": "https://...",
  "summary": "Source data 中该列末位数字分布异常。"
}
```

### IntegrityEvent

```json
{
  "id": "uuid",
  "event_type": "institution_notice",
  "status_level": "institution_investigation",
  "source_type": "institution",
  "source_name": "Example University",
  "source_url": "https://...",
  "event_date": "2026-05-12",
  "claim_summary": "机构公告称已成立调查组。",
  "verification_status": "source_verified",
  "evidence": []
}
```

## 3. Paper APIs

### GET /health

Process liveness check.

### GET /health/ready

Readiness check. Executes a lightweight database query, verifies required schema tables, and confirms the artifact storage directory is writable. Returns `503` when the API cannot reach its configured database, migrations have not been applied, or the artifact volume is not writable.

### GET /api/papers

Query parameters:

```text
query
doi
title
author
institution_id
journal
year_from
year_to
event_type
status_level
limit
offset
```

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "doi": "10.1038/example",
      "title": "Example title",
      "journal_name": "Nature",
      "publication_year": 2024,
      "china_institution_count": 2,
      "risk_status": {
        "official_status": "none",
        "institution_status": "none",
        "public_discussion_count": 1,
        "algorithmic_signal_count": 0,
        "highest_signal_level": "public_discussion",
        "summary": "存在公开讨论，尚未发现官方结论。"
      }
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### GET /api/papers/{doi}

Returns complete paper detail.

```json
{
  "paper": {
    "id": "uuid",
    "doi": "10.1038/example",
    "title": "Example title",
    "abstract": "...",
    "journal_name": "Nature",
    "publisher": "Springer Nature",
    "publication_year": 2024,
    "publication_date": "2024-11-13",
    "landing_page_url": "https://doi.org/10.1038/example"
  },
  "authorships": [],
  "institutions": [],
  "events": [],
  "algorithmic_signals": [],
  "artifacts": [],
  "risk_status": {}
}
```

Each authorship entry includes local `author_id`, local `institution_id`, raw author name, role flags, raw affiliation text and normalized institution display name when available. These IDs let a real-case DOI workflow jump from a paper to author, institution and breakdown endpoints.

### GET /api/papers/{doi}/risk-card

Returns the compact derived risk card.

## 4. Entity APIs

### GET /api/entities/search

Query parameters:

```text
entity_type=author | institution
query
limit
refresh=false | true
```

Search is limited to OpenAlex-backed authors and institutions. Lab or group entities are local composites created from already resolved authors/institutions. The default path checks `entity_search_cache` first for the same entity type, normalized query and limit. Cached responses may be marked `fresh`, `stale` or `stale_fallback`; send `refresh=true` to force a live OpenAlex refresh and update the local cache.

Response:

```json
{
  "cached": false,
  "source": "openalex",
  "cache_status": "refreshed",
  "fetched_at": "2026-05-23T00:00:00+00:00",
  "expires_at": "2026-05-30T00:00:00+00:00",
  "items": [
    {
      "entity_type": "author",
      "openalex_id": "https://openalex.org/A123",
      "display_name": "Example Author",
      "works_count": 42,
      "country_code": "CN",
      "hint": "Example University"
    }
  ]
}
```

### POST /api/entities/corpus

Builds or refreshes a local corpus for an author or institution.

Input:

```json
{
  "entity_type": "author",
  "query": "Example Author",
  "openalex_id": "https://openalex.org/A123",
  "limit": 25,
  "year_from": 2020,
  "year_to": 2026
}
```

Response includes the resolved entity, imported paper count and entity profile.

### POST /api/entities/corpus/batch

Builds or refreshes several local corpora from an entity list.

Input:

```json
{
  "items": [
    {
      "entity_type": "author",
      "query": "Example Author",
      "limit": 25
    },
    {
      "entity_type": "institution",
      "query": "Example University",
      "limit": 25
    }
  ],
  "continue_on_error": true
}
```

Response includes per-item success records, per-item errors and aggregate counts. Batch corpus results are still metadata/corpus construction records, not integrity conclusions.

### POST /api/entities/corpus/import

Multipart upload for a CSV, TSV or JSON entity manifest. CSV/TSV files use headers; JSON can be either a list or an object with an `items` list.

Supported fields:

```text
entity_type, query, name, openalex_id, display_name, limit, year_from, year_to
```

Form fields:

```text
file=@entities.csv
continue_on_error=true
default_limit=25
default_year_from=2020
default_year_to=2026
```

The endpoint builds the same batch corpus response as `/api/entities/corpus/batch` and records ordinary corpus audit-log entries.

### POST /api/entities/groups

Creates a local group/lab entity from existing author and institution IDs. Use this when a real laboratory should be represented as PI + lab members + institution rather than as a single DOI or a single school-level corpus.

```json
{
  "display_name": "Example Lab",
  "description": "Local audit group for PI and known lab members.",
  "members": [
    {"entity_type": "author", "entity_id": "local-author-id", "label": "PI"},
    {"entity_type": "institution", "entity_id": "local-institution-id", "label": "School"}
  ]
}
```

The response includes the group entity, aggregated profile and conclusion boundary. Group members can only be authors or institutions; downstream profile, signals, metadata audit, reports and jobs can use `entity_type=group`.

### POST /api/entities/groups/corpus

Builds author/institution corpora and then creates a local group/lab from the successfully resolved members.

```json
{
  "display_name": "Example Lab",
  "members": [
    {"entity_type": "author", "query": "Example PI", "limit": 50},
    {"entity_type": "author", "query": "Example Student", "limit": 25}
  ],
  "continue_on_error": true
}
```

This endpoint is intended for lab-level bootstrapping from a local member list. It returns per-member corpus results, member errors and the aggregated group profile.

### GET /api/entities/{entity_type}/{entity_id}/profile

Returns entity-level coverage and risk profile.

```json
{
  "paper_count": 10,
  "auditable_paper_count": 3,
  "audited_paper_count": 2,
  "signal_paper_count": 1,
  "official_event_count": 0,
  "public_discussion_count": 1,
  "auditable_coverage": 0.3,
  "audit_coverage": 0.2,
  "signal_rate_among_audited": 0.5,
  "sample_inference": {
    "paper_count": 10,
    "audited_sample_size": 2,
    "signal_sample_size": 1,
    "audit_coverage": 0.2,
    "observed_signal_rate": 0.5,
    "wilson_signal_rate_interval_95": {
      "lower": 0.0945,
      "upper": 0.9055
    },
    "reliability": "limited_coverage",
    "interpretation": "已审计样本覆盖率有限，信号率可用于提高复核优先级，但不能代表全库比例。",
    "extrapolation_boundary": "该区间只描述已审计样本中算法信号率的不确定性；全文可得性和上传材料可能有偏，不能外推为全库造假比例或事实结论。"
  },
  "priority": "high",
  "conclusion_boundary": "实体画像只表示已索引论文和已获取材料中的公开状态、可审计覆盖率与异常信号，不能直接认定作者、实验室或机构造假。"
}
```

### GET /api/entities/{entity_type}/{entity_id}/breakdown

Returns a heuristic internal breakdown from raw authorship affiliations. This is most useful for institution and group entities after corpus import.

Query parameters:

```text
limit=25
min_papers=1
```

Response:

```json
{
  "entity": {"entity_type": "institution", "id": "uuid", "display_name": "Example University"},
  "paper_count": 42,
  "affiliation_unit_count": 6,
  "author_count": 31,
  "affiliation_units": [
    {
      "unit_name": "School of Life Sciences",
      "unit_type": "school",
      "paper_count": 12,
      "author_count": 9,
      "auditable_paper_count": 5,
      "signal_paper_count": 1,
      "official_event_count": 0,
      "public_discussion_count": 0,
      "auditable_coverage": 0.4167,
      "top_authors": []
    }
  ],
  "top_authors": [],
  "method": {"source": "authorship.affiliation_raw", "classification": "keyword_heuristic"},
  "conclusion_boundary": "机构内部分组来自公开元数据中的原始 affiliation 启发式拆分，只用于导航、取样和复核优先级排序，不能作为院系归属或科研完整性事实结论。"
}
```

Affiliation breakdown is not a definitive department roster. It is a local navigation layer for deciding which author groups, schools or labs deserve expanded material collection and human review.

### POST /api/entities/review-queue

Creates review tasks for auditable papers in the entity corpus.

Input:

```json
{
  "entity_type": "author",
  "entity_id": "local-uuid",
  "priority": 7
}
```

## 5. Institution APIs

### GET /api/institutions

Search institution by name, ROR ID or OpenAlex ID.

### GET /api/institutions/{id}

Returns institution metadata, aliases, matched papers and event counts.

### GET /api/institutions/{id}/metrics

Response:

```json
{
  "institution_id": "uuid",
  "year_from": 2020,
  "year_to": 2026,
  "paper_count": 12450,
  "official_event_count": 12,
  "public_discussion_count": 31,
  "algorithmic_signal_count": 80,
  "official_events_per_1000_papers": 0.96,
  "notes": [
    "Algorithmic signals are unadjudicated and should not be used as misconduct counts."
  ]
}
```

## 6. Admin APIs

### POST /api/admin/import/doi

Input:

```json
{
  "doi": "10.1038/example",
  "sources": ["openalex", "crossref"]
}
```

Behavior:

- Normalize DOI.
- Fetch OpenAlex and Crossref records.
- Upsert paper, authorships and institutions.
- Save raw source records.

### POST /api/admin/events

Input:

```json
{
  "doi": "10.1038/example",
  "event_type": "institution_notice",
  "status_level": "institution_investigation",
  "source_type": "institution",
  "source_name": "Example University",
  "source_url": "https://...",
  "event_date": "2026-05-12",
  "claim_summary": "机构公告称已成立调查组。"
}
```

Validation:

- `source_url` is required.
- `claim_summary` must be attributed and neutral.
- Unofficial sources cannot set `official_retraction`, `official_correction` or `official_expression_of_concern`.

## 7. Artifact APIs

### POST /api/artifacts/register

Registers an existing URL or local storage URI as a paper artifact.

```json
{
  "paper_id": "paper-uuid",
  "artifact_type": "source_data",
  "source_url": "https://example.org/source-data.csv",
  "storage_uri": "/local/path/source-data.csv",
  "content_type": "text/csv",
  "filename": "source-data.csv",
  "license_status": "open_or_linked"
}
```

### POST /api/artifacts/upload

Multipart upload for local source data or manually collected artifacts.

```text
paper_id=<paper-uuid>
artifact_type=source_data
license_status=manual_upload
file=@source-data.csv
```

### POST /api/artifacts/discover

 Creates artifact records from already known metadata such as landing pages, PMC IDs and open access PDFs. With `inspect_landing_pages=true`, it fetches known landing/PMC/PubMed pages and registers matching PDF, source data, supplementary and figure links. The deep path also extracts common publisher-specific assets such as Nature/Springer static supplementary files, ScienceDirect/Elsevier `mmc` links, Wiley `downloadSupplement` links, Cell attachment URLs, PLOS supplementary files, MDPI supplementary attachments, Frontiers data sheets, Taylor & Francis supplements and BMJ supplementary files.

```json
{
  "paper_id": "paper-uuid",
  "inspect_landing_pages": true,
  "max_landing_pages": 3,
  "max_discovered_links": 30
}
```

### POST /api/artifacts/fetch

Fetches a registered artifact URL, or a new HTTP/HTTPS artifact URL, into local artifact storage. This is the bridge from metadata-only discovery to locally auditable material.

Fetch policy:

- `license_status` must explicitly assert a fetchable status such as `open_or_linked`, `manual_authorized`, `repository_open`, `cc_by`, `cc0`, `public_domain` or `fair_use_review`.
- Private, loopback, link-local, multicast and reserved network targets are rejected by default.
- HTML login/error pages are rejected for auditable file types.
- `ARTIFACT_FETCH_MAX_BYTES` limits remote payload size and `ARTIFACT_FETCH_MIN_INTERVAL_SECONDS` can add a per-host delay.

Fetch an existing registered artifact:

```json
{
  "artifact_id": "artifact-uuid",
  "license_status": "open_or_linked",
  "max_bytes": 52428800
}
```

Fetch a new URL for a paper:

```json
{
  "paper_id": "paper-uuid",
  "artifact_type": "source_data",
  "source_url": "https://example.org/source-data.csv",
  "license_status": "open_or_linked"
}
```

The service stores `storage_uri`, `checksum_sha256`, `content_type` and `filename`, then refreshes the paper material status. Only `http` and `https` URLs are accepted.

### GET /api/artifacts/papers/{paper_id}

Returns artifact records and current material status for the paper.

## 8. Audit APIs

### POST /api/audits/numeric

Runs deterministic numeric audit checks on a local CSV, TSV or first-sheet XLSX/XLSM artifact.

```json
{
  "artifact_id": "artifact-uuid",
  "min_duplicate_length": 3,
  "min_last_digit_sample": 10,
  "create_review_tasks": true,
  "priority": 8
}
```

Response:

```json
{
  "artifact_id": "artifact-uuid",
  "paper_id": "paper-uuid",
  "analyzed_rows": 10,
  "analyzed_numeric_columns": 4,
  "signal_count": 2,
  "created_review_tasks": 2,
  "signals": [],
  "conclusion_boundary": "数值审计只产生 algorithmic_signal，用于排序和人工复核，不能单独证明论文或作者造假。"
}
```

### POST /api/audits/image

Runs deterministic image similarity checks on local image artifacts. If `compare_artifact_ids` is omitted, the target is compared with other image artifacts on the same paper.

```json
{
  "artifact_id": "artifact-uuid",
  "compare_artifact_ids": ["peer-artifact-uuid"],
  "max_hamming_distance": 10,
  "enable_patch_similarity": true,
  "max_patch_hamming_distance": 6,
  "patch_grid_size": 4,
  "min_patch_stddev": 8.0,
  "create_review_tasks": true,
  "priority": 8
}
```

The image implementation detects highly similar panels across original, horizontal flip, vertical flip and 90/180/270 degree rotations. It also compares informative grid patches to catch simple crop/local reuse. It stores findings as `image_panel_similarity` or `image_patch_similarity` algorithmic signals.

### POST /api/audits/metadata

Runs entity-level metadata audit for publication-year clusters, journal clusters, title-template similarity, public/official event density and high non-metadata signal density among audited samples.

```json
{
  "entity_type": "author",
  "entity_id": "entity-uuid",
  "min_cluster_size": 5,
  "min_signal_rate_audited_count": 2,
  "signal_rate_threshold": 0.5,
  "public_event_rate_threshold": 0.2,
  "create_review_tasks": true,
  "priority": 6
}
```

Metadata findings are stored as `algorithmic_signal` records with analyzer `gengscope.metadata`. Title-template findings use `metadata_title_template_similarity`. Signal-density checks deliberately ignore prior metadata signals so repeated metadata audit runs do not amplify their own results.

### POST /api/audits/entity-cycle

Runs the local synchronous entity audit cycle: artifact discovery from already known metadata, review queue creation and metadata audit.

```json
{
  "entity_type": "author",
  "entity_id": "entity-uuid",
  "discover_artifacts": true,
  "inspect_landing_pages": false,
  "queue_review_tasks": true,
  "run_metadata_audit": true,
  "min_cluster_size": 5,
  "priority": 6
}
```

This endpoint is useful for short local runs. For repeatable deployed operation, use the job APIs and `gengscope-worker`.

## 9. Signal APIs

### GET /api/signals

Query parameters:

```text
entity_type=author | institution | group
entity_id
status=visible | all | needs_review | in_review | confirmed_signal | false_positive | not_actionable
signal_type
limit
offset
```

### GET /api/entities/{entity_type}/{entity_id}/signals

Returns the same signal list filtered to one author, institution or local group.

Response:

```json
{
  "items": [],
  "total": 4,
  "status_counts": {"needs_review": 4},
  "severity_counts": {"low": 4},
  "signal_type_counts": {"metadata_journal_cluster": 2},
  "conclusion_boundary": "信号列表只汇总公开事件与算法初筛结果，不能直接认定论文、作者、实验室或机构造假。"
}
```

## 10. Review APIs

### GET /api/review/tasks

Query parameters:

```text
status=open | closed | all
limit
offset
```

### POST /api/review/tasks/{task_id}/decision

```json
{
  "decision": "confirmed_signal | false_positive | not_actionable | needs_more_evidence",
  "reviewer_note": "人工复核记录。",
  "assigned_to": "reviewer@example.org"
}
```

## 11. Report APIs

### GET /api/reports/entity

Query parameters:

```text
entity_type=author | institution | group
entity_id
format=json | markdown
```

The JSON report bundles profile, signal counts, visible signals, open review tasks and a conclusion boundary. Markdown is intended for quick local review or agent-generated summaries.

### POST /api/reports/entity/archive

Request:

```json
{
  "entity_type": "author",
  "entity_id": "local-author-id",
  "formats": ["json", "markdown"]
}
```

Response:

```json
{
  "items": [
    {
      "id": "snapshot-uuid",
      "entity_type": "author",
      "entity_id": "local-author-id",
      "entity_display_name": "Alice Zhang",
      "report_format": "json",
      "content_sha256": "sha256",
      "actor": "local-ci",
      "created_at": "2026-05-23T00:00:00+00:00"
    }
  ],
  "total": 2,
  "conclusion_boundary": "报告归档是本地系统在某一时间点的可复核快照，用于追踪审计过程，不能作为论文、作者、实验室或机构的事实认定。"
}
```

### GET /api/reports/archive

Query parameters:

```text
entity_type=author | institution | group
entity_id
format=all | json | markdown
limit
offset
```

Lists archived report snapshots without returning full report content.

### GET /api/reports/archive/{snapshot_id}

Query parameters:

```text
format=json | markdown
```

`format=json` returns snapshot metadata plus `content_json`, `content_text` and `content`. `format=markdown` returns the archived Markdown text.

### POST /api/reports/archive/prune

Prunes archived report snapshots according to a local retention policy. By default this is a dry run.

```json
{
  "entity_type": "author",
  "entity_id": "local-author-id",
  "format": "all",
  "keep_latest": 20,
  "older_than_days": 180,
  "dry_run": true
}
```

The retention policy is evaluated per `(entity_type, entity_id, report_format)` group. When both `keep_latest` and `older_than_days` are present, the service keeps the newest `keep_latest` snapshots and only prunes older snapshots beyond that keep set. Set `dry_run=false` to delete matching snapshots. The action is recorded in the audit log.

Report archives are operational snapshots. They support reproducibility and local accountability, not misconduct conclusions.

## 12. Audit Log APIs

### GET /api/audit-log

Query parameters:

```text
action
actor
target_type
target_id
entity_type=author | institution | group
entity_id
paper_id
artifact_id
signal_id
task_id
limit
offset
```

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "action": "metadata_audit_run",
      "actor": "reviewer@example.org",
      "target_type": "entity",
      "target_id": "entity-uuid",
      "entity_type": "author",
      "entity_id": "entity-uuid",
      "summary": "Metadata audit created 4 signals.",
      "metadata": {
        "signal_count": 4,
        "created_review_tasks": 4
      },
      "created_at": "2026-05-23T00:00:00+00:00"
    }
  ],
  "total": 1,
  "conclusion_boundary": "操作日志只记录系统动作和人工复核轨迹，不能作为论文、作者、实验室或机构的事实认定。"
}
```

Audit logs are operational provenance. They should support reproducibility and local accountability, not misconduct conclusions.

## 13. Job APIs

### POST /api/jobs/entity-corpus

Queues an `entity_corpus_build` job for the background worker. This is the non-blocking version of `POST /api/entities/corpus` and is the preferred Workbench path when OpenAlex/Crossref latency would make the page feel slow.

```json
{
  "entity_type": "author",
  "query": "Example Author",
  "openalex_id": "https://openalex.org/A123",
  "limit": 50,
  "year_from": 2020,
  "year_to": 2026
}
```

Response:

```json
{
  "id": "job-uuid",
  "job_type": "entity_corpus_build",
  "status": "queued",
  "actor": "reviewer@example.org",
  "payload": {},
  "result": null,
  "error_message": null,
  "attempts": 0,
  "max_attempts": 1
}
```

When the worker completes the job, `result` contains the same corpus-build response returned by `POST /api/entities/corpus`. A successful corpus-build job only proves that metadata import ran; it is not an integrity finding.

### POST /api/jobs/entity-cycle

Queues an `entity_audit_cycle` job for the background worker.

```json
{
  "entity_type": "author",
  "entity_id": "entity-uuid",
  "discover_artifacts": true,
  "queue_review_tasks": true,
  "run_metadata_audit": true,
  "min_cluster_size": 5,
  "priority": 6
}
```

Response:

```json
{
  "id": "job-uuid",
  "job_type": "entity_audit_cycle",
  "status": "queued",
  "actor": "reviewer@example.org",
  "payload": {},
  "result": null,
  "error_message": null,
  "attempts": 0,
  "max_attempts": 1
}
```

### POST /api/jobs/entity-cycle/batch

Queues several `entity_audit_cycle` jobs for the background worker.

```json
{
  "items": [
    {
      "entity_type": "author",
      "entity_id": "author-uuid",
      "inspect_landing_pages": false,
      "min_cluster_size": 5
    },
    {
      "entity_type": "institution",
      "entity_id": "institution-uuid",
      "min_cluster_size": 5
    }
  ]
}
```

The response returns queued job records. A batch job record is workflow provenance only; it does not prove an integrity conclusion.

### POST /api/jobs/schedules/entity-cycle

Creates a persistent interval schedule. The background worker checks due schedules and enqueues ordinary `entity_audit_cycle` jobs.

```json
{
  "name": "weekly Alice audit",
  "interval_seconds": 604800,
  "start_at": "2026-05-23T00:00:00+00:00",
  "run_immediately": false,
  "max_attempts": 2,
  "job": {
    "entity_type": "author",
    "entity_id": "author-uuid",
    "inspect_landing_pages": true,
    "min_cluster_size": 5
  }
}
```

### GET /api/jobs/schedules

Query parameters:

```text
status=all | active | paused | cancelled
job_type
limit
offset
```

### POST /api/jobs/schedules/run-due

Enqueues all due active schedules immediately. This is mainly for local checks; the deployed worker runs the same check before polling queued jobs.

### POST /api/jobs/schedules/{schedule_id}/status

```json
{
  "status": "active | paused | cancelled"
}
```

Schedule records are workflow configuration. A due schedule only creates a queued job; it does not imply any integrity conclusion.

### GET /api/jobs

Query parameters:

```text
status=all | queued | running | succeeded | failed | cancelled
job_type
limit
offset
```

### GET /api/jobs/{job_id}

Returns one job run.

### POST /api/jobs/{job_id}/run

Runs a queued job immediately in the API process. This is intended for local operation and tests; deployed compose environments should use `gengscope-worker`.

### POST /api/jobs/{job_id}/retry

Moves a failed job back to `queued` and grants one more attempt.

Job records are workflow provenance. A succeeded job proves the local workflow ran, not that an integrity conclusion is true.
The compose worker claims queued jobs with PostgreSQL row locks and can recover stale `running` jobs when started with `--recover-stale-after`.

## 14. Agent APIs

### GET /api/agent/doi/{doi}

Returns a compact paper integrity summary.

### POST /api/agent/batch-risk-cards

Input:

```json
{
  "dois": ["10.1038/example-a", "10.1038/example-b"]
}
```

### POST /api/agent/audit-request

Creates a review or analysis request.

Input:

```json
{
  "doi": "10.1038/example",
  "requested_checks": ["numeric", "image"],
  "notes": "重点检查 Source Data Fig. 4。"
}
```

## 15. Error Shape

```json
{
  "error": {
    "code": "paper_not_found",
    "message": "No paper found for DOI.",
    "details": {
      "doi": "10.1038/example"
    }
  }
}
```
