-- Migration 020: per-user hidden jobs. A user "hides" a shared-pool job so it
-- disappears from their Jobs + Matches views without touching the shared row.
-- Owner-only RLS; both FKs cascade so the 90-day job purge and GDPR account
-- delete clean up hidden rows automatically.
begin;

create table if not exists hidden_jobs (
    user_id   uuid not null references auth.users(id) on delete cascade,
    job_id    uuid not null references jobs(id)       on delete cascade,
    hidden_at timestamptz not null default now(),
    primary key (user_id, job_id)
);

create index if not exists hidden_jobs_user_id_idx on hidden_jobs (user_id);

alter table hidden_jobs enable row level security;

drop policy if exists hidden_jobs_owner on hidden_jobs;
create policy hidden_jobs_owner on hidden_jobs
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

commit;
