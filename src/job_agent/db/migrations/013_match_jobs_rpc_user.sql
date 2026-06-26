-- Migration 013: make match_jobs_for_profile multi-tenant. The exclude_scored
-- predicate now means "not yet scored BY THIS USER" so a job scored by another
-- user is still a candidate. Adds p_user_id; otherwise identical to migration 005.
--
-- Note: profile_id is a plain argument, not validated against p_user_id. This is
-- safe under RLS: when called via the per-user (anon key + JWT) client, the
-- `profile` table is RLS-gated to the caller, so a foreign profile_id yields a
-- NULL embedding and the `(select embedding from prof) is not null` guard returns
-- zero rows. SECURITY INVOKER (the default) is intentional so RLS applies.
begin;

create or replace function match_jobs_for_profile(
    profile_id uuid,
    p_user_id uuid,
    top_n int default 10,
    exclude_scored boolean default true
)
returns table (
    job_id uuid,
    title text,
    company text,
    description text,
    requirements text[],
    similarity double precision
)
language sql
stable
as $$
    with prof as (
        select embedding from profile where id = profile_id
    )
    select
        j.id,
        j.title,
        j.company,
        j.description,
        j.requirements,
        greatest(0.0, least(1.0, 1 - (j.embedding <=> (select embedding from prof)))) as similarity
    from jobs j
    where j.embedding is not null
      and (select embedding from prof) is not null
      and (
          not exclude_scored
          or not exists (
              select 1 from match_scores ms
              where ms.job_id = j.id and ms.user_id = p_user_id
          )
      )
    order by j.embedding <=> (select embedding from prof)
    limit top_n;
$$;

commit;
