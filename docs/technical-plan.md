# Technical Plan

## 1. Recommended Stack

建议使用一个轻量 monorepo。

```text
Workbench: same-port FastAPI HTML workbench first, separate frontend later only if needed
Backend API: FastAPI + Python
Worker: Python CLI worker with DB-backed job queue first, Celery/Dramatiq later only if needed
Database: PostgreSQL
Search: PostgreSQL full-text first, Meilisearch later if needed
Object Storage: local filesystem in dev, S3/R2/MinIO in production
Queue: PostgreSQL job tables first, Redis later only if queue volume requires it
Migrations: SQL migration scripts
Data Validation: Pydantic
Agent/CI API: local HTTP API + OpenAPI contract; no MCP server in the core product
```

理由：

- OpenAlex、Crossref、ROR、PubMed、PDF/table parsing 和图像分析更适合 Python 生态。
- Web workbench、脚本、CI、notebook 和 agent 都通过同一个本地 HTTP API 调用，避免把集成层做成核心依赖。
- 第一版用 PostgreSQL 足够，避免过早引入 Elasticsearch。

## 2. Monorepo Structure

```text
gengscope/
  apps/
    web/
      app/
      components/
      lib/
      package.json
  services/
    api/
      gengscope_api/
        api/
        db/
        models/
        services/
        schemas/
      tests/
      pyproject.toml
    worker/
      gengscope_worker/
        ingest/
        normalize/
        analyze/
        jobs/
      tests/
      pyproject.toml
  packages/
    shared-schema/
      openapi/
      jsonschema/
      typescript/
  data/
    seeds/
    samples/
  infra/
    docker/
      docker-compose.yml
    migrations/
  skills/
    codex/
      SKILL.md
      examples/
  scripts/
    ingest/
    admin/
```

## 3. Data Ingestion

### 3.1 Paper Metadata

Primary source:

- OpenAlex Works API / snapshot

Filters:

```text
publication_year: 2020-2026
type: journal-article
authorships.institutions.country_code: CN
concept/topic: life sciences, medicine, biology, materials, nanotechnology
```

Fallback/enrichment:

- Crossref Works API
- PubMed / Europe PMC for biomedical records
- DOI resolver

### 3.2 Institution Normalization

Sources:

- ROR
- OpenAlex institutions
- Raw affiliation text from metadata

Rules:

- Store raw affiliation exactly as source provides it.
- Map to ROR when confidence is high.
- Do not force uncertain raw affiliations into an institution.
- Keep aliases, Chinese names and English names.

### 3.3 Retraction and Correction Events

Sources:

- Crossref Retraction Watch data
- Crossmark metadata
- Publisher pages
- Manual official notices

Event types:

```text
retraction
correction
expression_of_concern
editor_note
institution_notice
media_report
public_discussion
algorithmic_signal
```

### 3.4 PubPeer Signals

Use PubPeer as a link and signal source, not as copied content.

Store:

- DOI
- PubPeer URL
- first_seen_at
- last_seen_at
- comment_count if available
- rough category if manually classified

Avoid storing:

- Large comment bodies.
- User identities beyond public page metadata.
- Screenshots of comments unless legally reviewed.

### 3.5 Artifacts

Artifacts are files attached to papers:

- PDF
- supplementary files
- source data files
- correction notice PDF
- screenshots for evidence

Storage rules:

- Store URL, checksum, content type and captured timestamp.
- Respect publisher terms.
- Prefer storing open source data and metadata.
- For copyrighted content, store reference metadata and local analysis extracts only when permitted.

## 4. Processing Pipeline

```text
discover papers
  -> normalize DOI/title/journal/date
  -> normalize authors and institutions
  -> enrich Crossref/PubMed/OpenAlex/ROR
  -> import public integrity events
  -> fetch source artifacts when allowed
  -> run algorithmic analyzers
  -> create review tasks
  -> publish search index
```

Each step should be idempotent. Every imported record keeps `source_name`, `source_url`, `source_record_id`, `raw_payload_hash`, `captured_at`.

## 5. Algorithm Modules

### 5.1 Numeric Signals

Input:

- CSV/XLSX source data.
- Extracted supplementary tables.
- Manually uploaded table snippets.

Checks:

- Last digit distribution.
- Decimal-place pattern distribution.
- Duplicate sequences across groups.
- Fixed difference / fixed ratio between columns.
- Suspiciously high correlation across unrelated measurements.
- Repeated biological replicate values.
- Monotonic patterns unlikely for raw biological data.

Output:

```json
{
  "signal_type": "numeric_last_digit_anomaly",
  "severity": "low | medium | high",
  "paper_id": "...",
  "artifact_id": "...",
  "figure_label": "Fig. 4c",
  "table_name": "Source Data Fig. 4",
  "columns": ["group_a"],
  "summary": "末位数字分布偏离均匀分布，需要人工复核。",
  "metrics": {
    "chi_square_p": 0.0001
  }
}
```

### 5.2 Image Signals

Input:

- Extracted figure images.
- Manually split panels.
- Supplementary images.

Checks:

- Perceptual hash duplicate.
- Crop duplicate.
- Rotation/flip duplicate.
- Local patch similarity.
- Contrast-adjusted duplicate.
- Potential relabeling across panels.

Output must include bounding boxes and comparison image paths.

### 5.3 Metadata Signals

Checks:

- Unusual publication clusters.
- Reused title templates.
- Repeated suspicious affiliation patterns.
- Retraction/correction network around the same authors or institutions.

Metadata signals are low-confidence by default.

## 6. API Design

### Public API

```text
GET /api/papers?query=&year_from=&year_to=&institution_id=&event_type=
GET /api/papers/{doi}
GET /api/papers/{doi}/risk-card
GET /api/authors?query=
GET /api/authors/{author_id}
GET /api/institutions?query=
GET /api/institutions/{institution_id}
GET /api/institutions/{institution_id}/metrics
GET /api/events?paper_id=&status_level=&source_type=
```

### Internal API

```text
POST /api/admin/import/openalex
POST /api/admin/import/crossref
POST /api/admin/events
POST /api/admin/review-tasks/{id}/decision
POST /api/admin/artifacts
```

### Agent API

```text
GET /api/agent/doi/{doi}
GET /api/agent/institution/{institution_id}/summary
POST /api/agent/batch-risk-cards
POST /api/agent/audit-request
```

Agent endpoints must return compact, evidence-linked JSON.

## 7. Frontend Plan

### Pages

```text
/
/papers
/papers/[doi]
/authors/[id]
/institutions/[id]
/events/[id]
/review
/api-console
```

### Components

```text
SearchBox
PaperResultList
RiskBadge
RiskCard
EvidencePointerList
EventTimeline
AuthorInstitutionTable
InstitutionMetricsPanel
AlgorithmSignalTable
SourceArtifactViewer
ReviewDecisionPanel
```

### Design Tone

This is an operational research tool, not a marketing site.

- Dense, searchable, table-first UI.
- Neutral colors.
- Strong source links.
- No dramatic visual language.
- No shame ranking.
- Every claim links to a source or evidence pointer.

## 8. Development Phases

### Phase 0

- Finalize docs.
- Initialize repo tooling.
- Create database schema.
- Add seed cases manually.

### Phase 1

- Import OpenAlex and Crossref metadata by entity first: author, institution and local manifest. DOI import remains a compatibility path, not the main workflow.
- Build entity corpus search, paper search and paper detail views.
- Add manual event entry.
- Add risk card endpoint.

### Phase 2

- Add institution pages and normalized metrics.
- Add Retraction Watch import.
- Add PubPeer link tracking.
- Add CSV/TSV/JSON entity manifest import and batch entity corpus build.

### Phase 3

- Add source data artifact ingestion.
- Add numeric anomaly analyzer.
- Add review workbench.

### Phase 4

- Add image similarity analyzer.
- Add local HTTP/CI integration examples.
- Add scheduled entity audit updates.

## 9. Testing Strategy

Backend:

- Unit tests for DOI normalization, event status logic, institution matching.
- Integration tests for OpenAlex/Crossref clients using recorded fixtures.
- Database migration tests.
- Risk card snapshot tests.

Worker:

- Idempotent job tests.
- Parser tests for CSV/XLSX/source data.
- Analyzer tests with synthetic anomaly fixtures.

Frontend:

- Component tests for risk badges and event timeline.
- Playwright flow: search DOI -> paper detail -> evidence link.

Data:

- Seed fixture with known corrected/retracted/non-event papers.
- Golden JSON outputs for agent API.
