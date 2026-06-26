-- 014_observability_user.sql
-- Links agent_runs to the authenticated user so:
--   (a) delete_my_data can purge prompt snippets (GDPR Art. 17).
--   (b) RLS prevents cross-user reads on the observability dashboard.
--   (c) Anon+JWT writes work (authenticated role gets INSERT; old migration
--       010 created the tables without any grants, causing silent failures).

begin;

alter table agent_runs
    add column if not exists user_id uuid references auth.users(id) on delete cascade;

create index if not exists agent_runs_user_id_idx on agent_runs (user_id);

-- Grant DML to the authenticated role (anon+JWT path used by the API).
grant select, insert, update on agent_runs to authenticated;
grant select, insert on llm_events to authenticated;

-- RLS for agent_runs: each user sees and writes only their own rows.
alter table agent_runs enable row level security;
drop policy if exists agent_runs_owner on agent_runs;
create policy agent_runs_owner on agent_runs
    for all using (user_id = auth.uid())
    with check (user_id = auth.uid());

-- llm_events: access is gated via the parent run's ownership.
alter table llm_events enable row level security;
drop policy if exists llm_events_owner on llm_events;
create policy llm_events_owner on llm_events
    for all using (
        run_id in (
            select run_id from agent_runs where user_id = auth.uid()
        )
    );

commit;
