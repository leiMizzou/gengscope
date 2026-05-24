create table if not exists entity_groups (
  id text primary key,
  display_name text not null,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists entity_group_members (
  id text primary key,
  group_id text not null references entity_groups(id) on delete cascade,
  member_entity_type text not null,
  member_entity_id text not null,
  label text,
  created_at timestamptz not null default now()
);

create index if not exists idx_entity_group_members_group on entity_group_members (group_id);
create index if not exists idx_entity_group_members_member on entity_group_members (member_entity_type, member_entity_id);
