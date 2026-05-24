alter table papers
  add column if not exists material_status text not null default 'metadata_only',
  add column if not exists is_oa_pdf_available boolean not null default false,
  add column if not exists is_source_data_available boolean not null default false,
  add column if not exists audit_status text not null default 'not_audited';

create index if not exists idx_papers_material_status on papers (material_status);
create index if not exists idx_papers_audit_status on papers (audit_status);
