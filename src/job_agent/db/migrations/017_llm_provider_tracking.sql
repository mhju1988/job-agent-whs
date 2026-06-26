-- Track which LLM provider scored each job match
ALTER TABLE match_scores
    ADD COLUMN IF NOT EXISTS model_provider text DEFAULT 'gwdg';

-- Track which LLM provider answered each observability event
ALTER TABLE llm_events
    ADD COLUMN IF NOT EXISTS provider text DEFAULT 'gwdg';
