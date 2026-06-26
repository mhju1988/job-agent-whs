-- 010_observability.sql
-- Tracks agent runs and per-call LLM events for the observability dashboard.

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name    text NOT NULL CHECK (agent_name IN ('scout', 'matcher', 'writer', 'tracker')),
    started_at    timestamptz NOT NULL,
    finished_at   timestamptz,
    duration_ms   int,
    status        text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'error')),
    error_message text
);

CREATE TABLE IF NOT EXISTS llm_events (
    event_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id             uuid NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    prompt_snippet     text,
    response_snippet   text,
    prompt_tokens      int,
    completion_tokens  int,
    estimated_cost_eur numeric(10,6),
    duration_ms        int,
    created_at         timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at ON agent_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_events_run_id ON llm_events(run_id);
