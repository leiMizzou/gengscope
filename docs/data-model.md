# Data Model

## 1. Entity Overview

```text
Paper
  has many Authorships
  has many SourceArtifacts
  has many IntegrityEvents
  has many AlgorithmicSignals

Author
  has many Authorships

Institution
  has many Authorships

IntegrityEvent
  has many EvidencePointers

AlgorithmicSignal
  has many EvidencePointers

ReviewTask
  references AlgorithmicSignal or IntegrityEvent

AuditLog
  records local system actions and reviewer decisions

ReportSnapshot
  records point-in-time entity report exports

JobRun
  records queued and completed background worker jobs

JobSchedule
  records recurring background job schedules
```

## 2. Tables

### papers

```sql
create table papers (
  id text primary key,
  doi text unique,
  title text not null,
  abstract text,
  journal_name text,
  publisher text,
  publication_year int,
  publication_date date,
  type text,
  openalex_id text unique,
  crossref_member_id text,
  pmid text,
  pmcid text,
  landing_page_url text,
  open_access_url text,
  is_retracted boolean default false,
  material_status text not null default 'metadata_only',
  is_oa_pdf_available boolean default false,
  is_source_data_available boolean default false,
  audit_status text not null default 'not_audited',
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

`material_status` values:

```text
metadata_only
landing_page_found
pdf_found
source_data_found
full_auditable
manual_upload_available
```

`audit_status` values:

```text
not_audited
queued
in_review
reviewed
blocked_no_material
```

### authors

```sql
create table authors (
  id text primary key,
  display_name text not null,
  openalex_id text,
  orcid text,
  name_variants jsonb,
  disambiguation_status text not null default 'unverified',
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

### institutions

```sql
create table institutions (
  id text primary key,
  display_name text not null,
  english_name text,
  chinese_name text,
  ror_id text,
  openalex_id text,
  country_code text,
  city text,
  aliases jsonb,
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

### authorships

```sql
create table authorships (
  id text primary key,
  paper_id text not null references papers(id),
  author_id text references authors(id),
  author_name_raw text not null,
  author_position int,
  author_role text,
  is_corresponding boolean default false,
  institution_id text references institutions(id),
  affiliation_raw text,
  affiliation_match_confidence double precision,
  created_at timestamptz not null
);
```

`author_role` values:

```text
first
co_first
middle
co_corresponding
corresponding
last
unknown
```

### source_artifacts

```sql
create table source_artifacts (
  id text primary key,
  paper_id text not null references papers(id),
  artifact_type text not null,
  source_url text not null,
  storage_uri text,
  content_type text,
  filename text,
  checksum_sha256 text,
  license_status text not null default 'unknown',
  captured_at timestamptz not null,
  created_at timestamptz not null
);
```

`artifact_type` values:

```text
paper_pdf
source_data
supplementary
figure_image
correction_notice
publisher_notice
media_snapshot
manual_upload
```

### integrity_events

```sql
create table integrity_events (
  id text primary key,
  paper_id text references papers(id),
  event_type text not null,
  status_level text not null,
  source_type text not null,
  source_name text,
  source_url text not null,
  event_date date,
  captured_at timestamptz not null,
  claim_summary text not null,
  verification_status text not null default 'unverified',
  created_by text,
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

`verification_status` values:

```text
unverified
source_verified
official_confirmed
disputed
withdrawn
superseded
```

### evidence_pointers

```sql
create table evidence_pointers (
  id text primary key,
  paper_id text references papers(id),
  event_id text references integrity_events(id),
  signal_id text,
  artifact_id text references source_artifacts(id),
  figure_label text,
  table_label text,
  panel_label text,
  column_name text,
  row_label text,
  page_number int,
  bbox_json jsonb,
  evidence_url text,
  evidence_summary text,
  created_at timestamptz not null
);
```

### algorithmic_signals

```sql
create table algorithmic_signals (
  id text primary key,
  paper_id text not null references papers(id),
  artifact_id text references source_artifacts(id),
  signal_type text not null,
  severity text not null,
  confidence double precision,
  analyzer_name text not null,
  analyzer_version text not null,
  summary text not null,
  metrics_json jsonb,
  status text not null default 'needs_review',
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

`status` values:

```text
needs_review
in_review
confirmed_signal
false_positive
not_actionable
promoted_to_event
```

### review_tasks

```sql
create table review_tasks (
  id text primary key,
  paper_id text not null references papers(id),
  signal_id text references algorithmic_signals(id),
  event_id text references integrity_events(id),
  task_type text not null,
  priority int not null default 0,
  status text not null default 'open',
  assigned_to text,
  reviewer_note text,
  decision text,
  decided_at timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

### source_records

```sql
create table source_records (
  id text primary key,
  source_name text not null,
  source_record_id text,
  source_url text,
  entity_type text not null,
  entity_id text,
  raw_payload jsonb,
  raw_payload_hash text not null,
  captured_at timestamptz not null
);
```

Used for provenance and reproducibility.

### entity_groups

```sql
create table entity_groups (
  id text primary key,
  display_name text not null,
  description text,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table entity_group_members (
  id text primary key,
  group_id text not null references entity_groups(id) on delete cascade,
  member_entity_type text not null,
  member_entity_id text not null,
  label text,
  created_at timestamptz not null
);
```

Groups are local lab or collection scopes built from existing authors and institutions. They deduplicate papers across members for profile, signal, report and job workflows. A group is an audit scope, not an allegation or misconduct finding.

### audit_logs

```sql
create table audit_logs (
  id text primary key,
  action text not null,
  actor text,
  target_type text,
  target_id text,
  entity_type text,
  entity_id text,
  paper_id text,
  artifact_id text,
  signal_id text,
  task_id text,
  summary text,
  metadata_json jsonb,
  created_at timestamptz not null
);
```

Audit logs are operational records: corpus builds, artifact operations, audit runs, report exports, report archives and review decisions. They must not be interpreted as evidence that a paper, author, lab or institution committed misconduct.

### report_snapshots

```sql
create table report_snapshots (
  id text primary key,
  entity_type text not null,
  entity_id text not null,
  entity_display_name text not null,
  report_format text not null,
  content_json jsonb,
  content_text text,
  content_sha256 text not null,
  actor text,
  created_at timestamptz not null
);
```

Report snapshots store point-in-time JSON and/or Markdown entity reports so CI runs, local scripts and human review can prove which version of a report was reviewed. They can be pruned by local retention policy through the report archive API. They are provenance artifacts, not evidence that a paper, author, lab or institution committed misconduct.

### job_runs

```sql
create table job_runs (
  id text primary key,
  job_type text not null,
  status text not null default 'queued',
  actor text,
  payload_json jsonb not null,
  result_json jsonb,
  error_message text,
  attempts int not null default 0,
  max_attempts int not null default 1,
  queued_at timestamptz not null,
  started_at timestamptz,
  finished_at timestamptz,
  updated_at timestamptz not null
);
```

`status` values:

```text
queued
running
succeeded
failed
cancelled
```

Initial job type:

```text
entity_audit_cycle
```

Jobs are operational workflow records. Job success means the requested local workflow ran to completion; it is not an integrity conclusion.

### job_schedules

```sql
create table job_schedules (
  id text primary key,
  name text not null,
  job_type text not null,
  status text not null default 'active',
  actor text,
  payload_json jsonb not null,
  interval_seconds int not null,
  max_attempts int not null default 1,
  next_run_at timestamptz not null,
  last_run_at timestamptz,
  last_job_id text,
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

`status` values:

```text
active
paused
cancelled
```

Schedules are operational configuration. A due schedule only enqueues a background job; it is not an integrity conclusion.

## 3. Indexes

Recommended indexes:

```sql
create index idx_papers_doi_lower on papers (lower(doi));
create index idx_papers_year on papers (publication_year);
create index idx_papers_title_trgm on papers using gin (title gin_trgm_ops);
create index idx_authors_display_name_trgm on authors using gin (display_name gin_trgm_ops);
create index idx_institutions_display_name_trgm on institutions using gin (display_name gin_trgm_ops);
create index idx_authorships_paper on authorships (paper_id);
create index idx_authorships_author on authorships (author_id);
create index idx_authorships_institution on authorships (institution_id);
create index idx_events_paper on integrity_events (paper_id);
create index idx_events_status_level on integrity_events (status_level);
create index idx_signals_paper on algorithmic_signals (paper_id);
create index idx_signals_status on algorithmic_signals (status);
create index idx_audit_logs_action on audit_logs (action);
create index idx_audit_logs_target on audit_logs (target_type, target_id);
create index idx_audit_logs_entity on audit_logs (entity_type, entity_id);
create index idx_audit_logs_created_at on audit_logs (created_at);
create index idx_job_runs_status on job_runs (status);
create index idx_job_runs_type_status on job_runs (job_type, status);
create index idx_job_runs_queued_at on job_runs (queued_at);
create index idx_job_schedules_status_next_run on job_schedules (status, next_run_at);
create index idx_job_schedules_type_status on job_schedules (job_type, status);
```

Enable:

```sql
create extension if not exists pg_trgm;
create extension if not exists unaccent;
```

## 4. Risk Card Derivation

Risk card is derived, not manually stored.

Priority:

1. Retraction.
2. Expression of concern.
3. Official correction.
4. Institution conclusion.
5. Institution investigation.
6. Publisher/editor note.
7. Public discussion.
8. Media report.
9. Algorithmic signal.

Pseudo-code:

```text
events = load_events(paper_id)
signals = load_reviewed_signals(paper_id)

official_status = highest_official_event(events)
public_signal_count = count_public_events(events)
algorithmic_signal_count = count_active_signals(signals)

summary = generate_neutral_summary(official_status, events, signals)
```

## 5. Seed Data

Seed records should include:

- One paper with official correction.
- One paper with expression of concern.
- One paper with institutional investigation.
- One paper with public discussion only.
- One clean control paper with no event.

Seed data should be small and manually curated. Do not commit downloaded PDFs, full supplementary files or copyrighted images unless license permits.
