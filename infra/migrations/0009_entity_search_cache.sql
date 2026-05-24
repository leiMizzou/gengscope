create table if not exists entity_search_cache (
  id text primary key,
  entity_type text not null,
  query_text text not null,
  query_normalized text not null,
  requested_limit int not null,
  results_json jsonb not null,
  result_count int not null default 0,
  source_name text not null default 'openalex',
  fetched_at timestamptz not null default now(),
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_entity_search_cache_lookup
  on entity_search_cache (entity_type, query_normalized, requested_limit);

create index if not exists idx_entity_search_cache_expires_at
  on entity_search_cache (expires_at);
