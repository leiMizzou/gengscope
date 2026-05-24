create table if not exists job_runs (
  id varchar(36) primary key,
  job_type varchar not null,
  status varchar not null default 'queued',
  actor varchar,
  payload_json json not null,
  result_json json,
  error_message text,
  attempts integer not null default 0,
  max_attempts integer not null default 1,
  queued_at timestamp with time zone not null,
  started_at timestamp with time zone,
  finished_at timestamp with time zone,
  updated_at timestamp with time zone not null
);

create index if not exists idx_job_runs_status on job_runs (status);
create index if not exists idx_job_runs_type_status on job_runs (job_type, status);
create index if not exists idx_job_runs_queued_at on job_runs (queued_at);
