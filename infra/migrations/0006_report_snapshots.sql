create table if not exists report_snapshots (
  id varchar(36) primary key,
  entity_type varchar not null,
  entity_id varchar(36) not null,
  entity_display_name varchar not null,
  report_format varchar not null,
  content_json json,
  content_text text,
  content_sha256 varchar not null,
  actor varchar,
  created_at timestamp with time zone not null
);

create index if not exists idx_report_snapshots_entity on report_snapshots (entity_type, entity_id);
create index if not exists idx_report_snapshots_created_at on report_snapshots (created_at);
create index if not exists idx_report_snapshots_hash on report_snapshots (content_sha256);
