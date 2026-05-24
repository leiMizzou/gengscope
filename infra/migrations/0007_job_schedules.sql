create table if not exists job_schedules (
  id varchar(36) primary key,
  name varchar not null,
  job_type varchar not null,
  status varchar not null default 'active',
  actor varchar,
  payload_json json not null,
  interval_seconds integer not null,
  max_attempts integer not null default 1,
  next_run_at timestamp with time zone not null,
  last_run_at timestamp with time zone,
  last_job_id varchar(36),
  created_at timestamp with time zone not null,
  updated_at timestamp with time zone not null
);

create index if not exists idx_job_schedules_status_next_run on job_schedules (status, next_run_at);
create index if not exists idx_job_schedules_type_status on job_schedules (job_type, status);
