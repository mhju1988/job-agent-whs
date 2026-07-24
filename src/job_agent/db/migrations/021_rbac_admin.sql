-- Migration 021: RBAC support. `admin_audit_log` records every admin action
-- (who, what, target, when); `jobs_admin_delete` lets admins remove bad/
-- duplicate listings from the shared pool. Role itself lives in each user's
-- auth `app_metadata.role` (set only via the service-role key) — no role
-- column/table is needed here, since Postgres RLS reads it straight off
-- `auth.jwt()`.
begin;

create table if not exists admin_audit_log (
    id uuid primary key default gen_random_uuid(),
    admin_user_id uuid not null references auth.users(id),
    action text not null,
    target_user_id uuid references auth.users(id),
    target_resource text,
    detail jsonb,
    created_at timestamptz not null default now()
);

alter table admin_audit_log enable row level security;

-- No insert/update/delete policy for anon/authenticated: every write goes
-- through the backend's service-role client, which bypasses RLS entirely.
-- This SELECT policy is defense-in-depth in case the table is ever queried
-- directly with a user's JWT.
drop policy if exists admin_audit_log_admin_read on admin_audit_log;
create policy admin_audit_log_admin_read on admin_audit_log
    for select using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'admin');

-- jobs: today RLS (migration 012) defines select/insert/update for any
-- authenticated user but no delete policy at all, so no one but the
-- service role can delete a row. This adds delete, gated to admins —
-- a new grant, not a restriction on what regular users could already do.
drop policy if exists jobs_admin_delete on jobs;
create policy jobs_admin_delete on jobs
    for delete using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'admin');

commit;
