create index if not exists idx_source_artifacts_paper on source_artifacts (paper_id);
create index if not exists idx_source_artifacts_type on source_artifacts (artifact_type);
create index if not exists idx_review_tasks_status on review_tasks (status);
create index if not exists idx_review_tasks_signal on review_tasks (signal_id);
