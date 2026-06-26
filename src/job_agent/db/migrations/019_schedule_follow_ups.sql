-- Migration 019: Stamp follow_up_at on applications applied >= 7 days ago.
-- Closes review finding #2: TrackerAgent.check_follow_ups() was written and
-- unit-tested but never invoked in production, so follow_up_at was never set
-- and the dashboard "Follow-ups due" KPI + kanban bell were permanently inert.
--
-- pg_cron runs SQL, not Python, so the (tested) Python rule is expressed here
-- as SQL. This is deliberately system-wide (no user_id filter): one nightly
-- sweep stamps every user's due rows. It runs as the cron role and bypasses
-- RLS, which is correct for a maintenance job. The Python check_follow_ups()
-- stays as the canonical, unit-tested specification of the same rule.
--
-- Functionally equivalent to _do_check_follow_ups (tracker_agent.py) — same
-- rows selected, same value written — differing only in cadence (this runs
-- nightly; the Python sweep runs on demand). NOT a verbatim copy:
--   status='applied' AND follow_up_at IS NULL AND applied_at IS NOT NULL
--   AND applied_at <= now() - interval '7 days'
--   => follow_up_at := applied_at + interval '7 days'

create or replace function set_due_follow_ups()
returns void
language sql
as $$
    update applications
    set follow_up_at = applied_at + interval '7 days'
    where status = 'applied'
      and follow_up_at is null
      and applied_at is not null
      and applied_at <= now() - interval '7 days';
$$;

-- 02:00 UTC daily (before the 03:00 purge). Idempotent by name.
select cron.schedule(
    'set-due-follow-ups',
    '0 2 * * *',
    $$select set_due_follow_ups();$$
);
