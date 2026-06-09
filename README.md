# Automated Job Application Agent

Solo university project (W-HS "Agentic AI"). Scrapes/fetches jobs, matches against a CV, generates tailored cover letter + CV variant, tracks progress in Supabase, and surfaces it in a Streamlit dashboard.


## Setup

```powershell
uv sync
copy .env.example .env   # then fill in GWDG + Supabase keys
uv run pytest
```

## Stack
Python 3.11  · Playwright · python-docx · pypdf · Supabase (Postgres + pgvector) · GWDG LLM · Streamlit

## What's working

### Sprint 1 — Scout Agent
Fetches job postings from the Arbeitsagentur Jobsuche API (and optionally JSearch via RapidAPI), normalises to a Pydantic `Job` model, de-dupes by `(source, external_id)`, and persists to Supabase. Client-side rate limiting (≤100 req/hr) and retention-aware schema (90-day purge for `jobs`/`match_scores`; `applications` survive via `on delete set null` + snapshot fields).

### Sprint 2 — Matcher Agent
Two-stage ranking: pgvector cosine narrows the candidate pool cheaply, then a GWDG LLM gap analysis (`apertus-70b-instruct-2509` or `meta-llama-3.1-8b-instruct`) scores each candidate against the CV with `matched_skills`, `gaps`, and a rationale. Embeddings via GWDG `multilingual-e5-large-instruct` (1024-dim); CV PDF parsing enforces a strict-subset rule (LLM cannot invent skills not present in the source PDF).

**Reproducible demo fixture.** The Matcher pipeline is frozen in `tests/fixtures/sprint2_demo/`. Anyone cloning this repo can run:

```bash
uv run pytest tests/agents/test_matcher_agent.py::test_matcher_against_sprint2_demo_fixture -v
```

to verify the Matcher produces the exact Top-N from the Sprint 2 presentation slides — no GWDG or Supabase access required, the fixture replays recorded LLM responses.

### Run the live end-to-end demo

With a populated profile and GWDG + Supabase credentials in `.env`:

```bash
# 1. (one-time) seed the demo fixture against your CV
uv run python scripts/seed_demo_fixture.py --cv path/to/your_cv.pdf

# 2. live closer — fetch fresh jobs, embed, score, print Top-N
uv run python scripts/demo_match.py --profile-id <uuid> --query "Java Developer" --limit 1
```
