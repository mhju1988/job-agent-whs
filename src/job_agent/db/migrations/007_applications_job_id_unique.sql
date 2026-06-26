-- Migration 007: ensure one application row per job (used by Writer's upsert).
-- Note: `applications.job_id` is intentionally nullable (FK is `on delete set
-- null` per migration 001 so applications survive the 90-day jobs purge per
-- docs/legal.md §2.4). Per SQL semantics, a UNIQUE constraint allows multiple
-- NULL values, so orphaned applications can coexist — this is by design.
begin;
alter table applications drop constraint if exists applications_job_id_unique;
alter table applications add constraint applications_job_id_unique unique (job_id);
commit;
