-- 015_match_scores_unique.sql
-- Adds a unique constraint on (user_id, job_id) so that the Matcher's
-- upsert(on_conflict="user_id,job_id") has a valid ON CONFLICT target.
-- Migration 011 created a plain (non-unique) index on user_id only; Postgres
-- requires a unique constraint or unique index for ON CONFLICT resolution.

begin;

alter table match_scores
    drop constraint if exists match_scores_user_job_unique;
alter table match_scores
    add constraint match_scores_user_job_unique unique (user_id, job_id);

commit;
