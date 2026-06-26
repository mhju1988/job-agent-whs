-- 016_profile_suggested_searches.sql
-- Caches AI-generated search suggestions alongside the profile so the Jobs
-- page can read them in O(1) instead of calling the LLM on every page load.

begin;

alter table profile
    add column if not exists suggested_searches jsonb default '[]'::jsonb;

commit;
