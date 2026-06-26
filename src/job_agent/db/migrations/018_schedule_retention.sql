-- Migration 018: Schedule the 90-day retention purge.
-- Closes review finding #3: purge_expired_data() (migration 002) was written
-- but never invoked, so retention was not actually enforced. Migration 002's
-- comment deferred scheduling to "application code"; nothing ever called it.
-- We now schedule it in-database via pg_cron (revisiting 002's "avoid extension
-- dependencies" decision, which left the policy unenforced).
--
-- Supabase note: pg_cron may need enabling once via the dashboard
-- (Database -> Extensions -> pg_cron). The statement below is the SQL form.
-- pg_cron jobs run as the scheduling role (postgres) and bypass RLS, which is
-- correct for a system-wide maintenance sweep.

create extension if not exists pg_cron;

-- 03:00 UTC daily. Idempotent: re-running replaces the job of the same name.
select cron.schedule(
    'purge-expired-data',
    '0 3 * * *',
    $$select purge_expired_data();$$
);
