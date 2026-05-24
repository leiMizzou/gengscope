create table if not exists audit_logs (
  id varchar(36) primary key,
  action varchar not null,
  actor varchar,
  target_type varchar,
  target_id varchar(36),
  entity_type varchar,
  entity_id varchar(36),
  paper_id varchar(36),
  artifact_id varchar(36),
  signal_id varchar(36),
  task_id varchar(36),
  summary text,
  metadata_json json,
  created_at timestamp with time zone not null
);

create index if not exists idx_audit_logs_action on audit_logs (action);
create index if not exists idx_audit_logs_target on audit_logs (target_type, target_id);
create index if not exists idx_audit_logs_entity on audit_logs (entity_type, entity_id);
create index if not exists idx_audit_logs_created_at on audit_logs (created_at);
