-- ---------------------------------------------------------------------------
-- 008_add_matched_skills_to_match_scores
--
-- Adds a `matched_skills text[]` column to the `match_scores` table so the
-- LLM gap-analysis output (already produced by MatcherAgent) can be persisted
-- and displayed in the Matches tab of the Streamlit dashboard.
--
-- Existing rows are intentionally left with NULL — the UI shows a fallback
-- caption ("No analysis available — re-run Matcher to score this job.") for
-- those rows. Re-running MatcherAgent on a job will produce a fresh row with
-- the column populated.
-- ---------------------------------------------------------------------------

begin;

alter table match_scores
    add column if not exists matched_skills text[];

commit;
