-- Migration 005: top-N job similarity RPC for Matcher Agent.
-- Uses pgvector cosine distance (<=> operator). Lower distance = more similar.
-- `similarity` is `1 - distance` for an intuitive 0..1 score.
begin;

create or replace function match_jobs_for_profile(
    profile_id uuid,
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
        -- Clamp to [0,1]: cosine distance is in [0,2] for arbitrary vectors;
        -- our multilingual-e5 outputs are normalised so this is defence in depth.
        greatest(0.0, least(1.0, 1 - (j.embedding <=> (select embedding from prof)))) as similarity
    from jobs j
    where j.embedding is not null
      and (select embedding from prof) is not null
      and (
          not exclude_scored
          or not exists (select 1 from match_scores ms where ms.job_id = j.id)
      )
    order by j.embedding <=> (select embedding from prof)
    limit top_n;
$$;

commit;
