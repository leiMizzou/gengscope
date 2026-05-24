# Implementation Plan

## 1. MVP Build Order

### Step 1: Backend Skeleton

Create `services/api` with:

```text
gengscope_api/
  main.py
  config.py
  db/session.py
  db/models.py
  schemas/
  api/routes/
  services/
  clients/
tests/
```

Core dependencies:

```text
fastapi
uvicorn
sqlalchemy
alembic
pydantic
pydantic-settings
httpx
psycopg
python-dotenv
pytest
ruff
```

### Step 2: Database

Create Alembic migrations for:

- papers
- authors
- institutions
- authorships
- source_artifacts
- integrity_events
- evidence_pointers
- algorithmic_signals
- review_tasks
- source_records

### Step 3: DOI Import

Implement:

```text
clients/openalex.py
clients/crossref.py
services/doi.py
services/import_paper.py
```

Rules:

- Normalize DOI to lower case.
- Remove `https://doi.org/`.
- Save raw API payloads.
- Upsert records idempotently.
- Preserve raw affiliation strings.

### Step 4: Manual Event Entry

Implement:

```text
schemas/events.py
services/events.py
api/routes/admin_events.py
```

Validation:

- Source URL required.
- Status level must match source type.
- Claim summary must be non-empty and under 800 characters.

### Step 5: Risk Card

Implement:

```text
services/risk_card.py
schemas/risk_card.py
api/routes/agent.py
```

Risk card is derived from events and signals. It is not a separate manually edited table.

### Step 6: Web Skeleton

Create `apps/web` with:

```text
app/
  page.tsx
  papers/page.tsx
  papers/[doi]/page.tsx
  institutions/[id]/page.tsx
components/
  SearchBox.tsx
  RiskBadge.tsx
  EventTimeline.tsx
  EvidencePointerList.tsx
lib/
  api.ts
```

### Step 7: Seed Data

Load `data/seeds/seed_cases.json` through an admin import script.

## 2. Service Boundaries

### API Service

Owns:

- HTTP API.
- Database writes.
- Risk card derivation.
- Admin validation.
- Public query surface.

Does not own:

- Long-running ingestion.
- PDF parsing.
- Image analysis.

### Worker Service

Owns:

- Batch imports.
- Source artifact fetching.
- Supplementary parsing.
- Numeric and image analysis.
- Review task creation.

### Web App

Owns:

- Search and detail pages.
- Evidence visualization.
- Admin forms.
- Review workbench.

## 3. Code Quality Rules

- All source imports are idempotent.
- All imported data keeps provenance.
- All public claims have source URLs.
- Algorithmic signals cannot become public official facts.
- Use typed schemas at API boundaries.
- Add tests for DOI normalization, risk card derivation and event validation before broad ingestion.

## 4. First Sprint Tasks

```text
P0-001 Initialize FastAPI project
P0-002 Add PostgreSQL docker-compose
P0-003 Add SQLAlchemy models and migration
P0-004 Implement DOI normalization
P0-005 Implement OpenAlex client
P0-006 Implement Crossref client
P0-007 Implement DOI import endpoint
P0-008 Implement manual event endpoint
P0-009 Implement risk-card endpoint
P0-010 Add seed import script
P0-011 Initialize Next.js app
P0-012 Build DOI search page
P0-013 Build paper detail page
```

## 5. Testing Checklist

Backend:

```text
test_normalize_doi
test_import_same_doi_twice_is_idempotent
test_manual_event_requires_source_url
test_unofficial_source_cannot_set_official_status
test_risk_card_prefers_retraction_over_public_discussion
test_risk_card_counts_algorithmic_signals_separately
```

Frontend:

```text
search by DOI
open paper detail
render event timeline
render no-event state
render official correction state
```

Worker:

```text
parse_csv_source_data
detect_duplicate_numeric_sequence
detect_last_digit_anomaly
create_review_task_for_signal
```

## 6. Deployment Shape

Local:

```text
PostgreSQL
Redis
FastAPI
Next.js
Worker
```

Production:

```text
API container
Worker container
PostgreSQL managed database
Redis managed queue
Object storage
Static/web hosting
```
