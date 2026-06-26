-- Migration 011: multi-tenancy. Adds user_id to the three user-owned tables
-- (profile, match_scores, applications). jobs stays a shared global pool.
-- Swaps applications' UNIQUE(job_id) for UNIQUE(user_id, job_id) so two users
-- can apply to the same job without colliding on Writer's upsert.
begin;

-- profile: exactly one per user. user_id is left nullable so this migration
-- applies cleanly over an existing (single-user dev) row; a row with a NULL
-- user_id is inert under RLS (it can never match auth.uid()) and the UNIQUE
-- constraint permits multiple NULLs. Production rows always carry a user_id.
alter table profile
    add column if not exists user_id uuid references auth.users(id) on delete cascade;
alter table profile drop constraint if exists profile_user_id_unique;
alter table profile add constraint profile_user_id_unique unique (user_id);

-- match_scores
alter table match_scores
    add column if not exists user_id uuid references auth.users(id) on delete cascade;
create index if not exists match_scores_user_id_idx on match_scores (user_id);

-- applications: per-user uniqueness on job_id.
alter table applications
    add column if not exists user_id uuid references auth.users(id) on delete cascade;
create index if not exists applications_user_id_idx on applications (user_id);
alter table applications drop constraint if exists applications_job_id_unique;
alter table applications drop constraint if exists applications_user_job_unique;
alter table applications add constraint applications_user_job_unique unique (user_id, job_id);

commit;
