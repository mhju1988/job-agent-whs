-- Migration 012: Row-Level Security. Owner-only access to user-owned tables;
-- jobs is a shared pool readable + writable by any authenticated user (Scout
-- upserts public listings into it). The API binds the user's JWT so auth.uid()
-- resolves to the caller; the anon key alone has no table access.
begin;

alter table profile        enable row level security;
alter table match_scores   enable row level security;
alter table applications   enable row level security;
alter table jobs           enable row level security;

-- profile: owner only.
drop policy if exists profile_owner on profile;
create policy profile_owner on profile
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- match_scores: owner only.
drop policy if exists match_scores_owner on match_scores;
create policy match_scores_owner on match_scores
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- applications: owner only.
drop policy if exists applications_owner on applications;
create policy applications_owner on applications
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- jobs: shared global pool. Any authenticated user may read and upsert.
drop policy if exists jobs_authenticated_read on jobs;
create policy jobs_authenticated_read on jobs
    for select using (auth.role() = 'authenticated');
drop policy if exists jobs_authenticated_write on jobs;
create policy jobs_authenticated_write on jobs
    for insert with check (auth.role() = 'authenticated');
drop policy if exists jobs_authenticated_update on jobs;
create policy jobs_authenticated_update on jobs
    for update using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');

commit;
