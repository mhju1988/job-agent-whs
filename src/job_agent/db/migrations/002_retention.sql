-- Migration 002: Data retention
-- Implements the 90-day retention policy required by docs/legal.md §2.4.
--
-- Behaviour:
--   - Deletes from `jobs` where scraped_at is older than 90 days.
--   - `match_scores.job_id` cascades, so related rows are removed automatically.
--   - `applications.job_id` is `on delete set null` (migration 001), so
--     applications survive — preserving the user's audit trail per legal §2.4.
--     Snapshot fields (job_title, job_company, job_url, job_source) keep the
--     record meaningful after the parent jobs row is gone.
--
-- Scheduled nightly via pg_cron in migration 018 (cron job
-- 'purge-expired-data'). This migration only defines the function.

create or replace function purge_expired_data()
returns void
language sql
as $$
    delete from jobs
    where scraped_at < now() - interval '90 days';
$$;
