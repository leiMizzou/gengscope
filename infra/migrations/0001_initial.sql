create extension if not exists pg_trgm;
create extension if not exists unaccent;

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
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table authors (
  id text primary key,
  display_name text not null,
  openalex_id text,
  orcid text,
  name_variants jsonb,
  disambiguation_status text not null default 'unverified',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

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
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table authorships (
  id text primary key,
  paper_id text not null references papers(id) on delete cascade,
  author_id text references authors(id),
  author_name_raw text not null,
  author_position int,
  author_role text,
  is_corresponding boolean default false,
  institution_id text references institutions(id),
  affiliation_raw text,
  affiliation_match_confidence double precision,
  created_at timestamptz not null default now()
);

create table source_artifacts (
  id text primary key,
  paper_id text not null references papers(id) on delete cascade,
  artifact_type text not null,
  source_url text not null,
  storage_uri text,
  content_type text,
  filename text,
  checksum_sha256 text,
  license_status text not null default 'unknown',
  captured_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table integrity_events (
  id text primary key,
  paper_id text references papers(id) on delete cascade,
  event_type text not null,
  status_level text not null,
  source_type text not null,
  source_name text,
  source_url text not null,
  event_date date,
  captured_at timestamptz not null default now(),
  claim_summary text not null,
  verification_status text not null default 'unverified',
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table evidence_pointers (
  id text primary key,
  paper_id text references papers(id) on delete cascade,
  event_id text references integrity_events(id) on delete cascade,
  signal_id text,
  artifact_id text references source_artifacts(id) on delete set null,
  figure_label text,
  table_label text,
  panel_label text,
  column_name text,
  row_label text,
  page_number int,
  bbox_json jsonb,
  evidence_url text,
  evidence_summary text,
  created_at timestamptz not null default now()
);

create table algorithmic_signals (
  id text primary key,
  paper_id text not null references papers(id) on delete cascade,
  artifact_id text references source_artifacts(id) on delete set null,
  signal_type text not null,
  severity text not null,
  confidence double precision,
  analyzer_name text not null,
  analyzer_version text not null,
  summary text not null,
  metrics_json jsonb,
  status text not null default 'needs_review',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table evidence_pointers
  add constraint fk_evidence_signal
  foreign key (signal_id)
  references algorithmic_signals(id)
  on delete cascade;

create table review_tasks (
  id text primary key,
  paper_id text not null references papers(id) on delete cascade,
  signal_id text references algorithmic_signals(id) on delete cascade,
  event_id text references integrity_events(id) on delete cascade,
  task_type text not null,
  priority int not null default 0,
  status text not null default 'open',
  assigned_to text,
  reviewer_note text,
  decision text,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table source_records (
  id text primary key,
  source_name text not null,
  source_record_id text,
  source_url text,
  entity_type text not null,
  entity_id text,
  raw_payload jsonb,
  raw_payload_hash text not null,
  captured_at timestamptz not null default now()
);

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
