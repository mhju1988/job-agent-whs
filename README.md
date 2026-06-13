# Automated Job Application Agent

Solo university project (W-HS "Agentic AI", Project #7). Fetches jobs, matches them against your CV, generates a tailored cover letter + CV variant, and tracks each application through a Streamlit dashboard.

Built as four CrewAI-style agents (Scout · Matcher · Writer · Tracker) over Supabase (Postgres + pgvector) with the GWDG OpenAI-compatible LLM endpoint.

---

## Setup

### 1. Prerequisites
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- A Supabase project (free tier) — EU region recommended (see `docs/legal.md` §2.1)
- A GWDG API key (`https://docs.hpc.gwdg.de/services/ai-services/saia/`)

### 2. Install
```powershell
uv sync
uv run pre-commit install
```

### 3. Configure
```powershell
copy .env.example .env
```

Fill in `.env`:
```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<service_role_or_anon_key>
GWDG_API_BASE=https://chat-ai.academiccloud.de/v1
GWDG_API_KEY=<your_key>
GWDG_MODEL=meta-llama-3.1-8b-instruct
GWDG_EMBED_MODEL=multilingual-e5-large-instruct
LOG_LEVEL=INFO
ARTIFACTS_DIR=artifacts
```

> **Note:** The GWDG model catalogue drifts without notice. Verify current model names with `GET /v1/models` before any live run.

### 4. Apply Supabase migrations
Open the Supabase SQL Editor and run each file in `src/job_agent/db/migrations/` in numeric order (001 → 009). The `supabase-py` client cannot run DDL, so this is manual.

### 5. Verify
```powershell
uv run pytest -q          # all mocked, no live calls
uv run ruff check src/ tests/
uv run mypy src/
```

---

## How to run

**Streamlit dashboard:**
```powershell
uv run streamlit run src/job_agent/ui/app.py
```
Three tabs: Jobs · Matches · Applications. Sidebar has a "Delete my data" GDPR action.

**End-to-end surface — Streamlit dashboard:**

The Streamlit dashboard is the end-to-end interface for Writer + Tracker. Upload your CV in the sidebar, then work through the tabs: run Scout to fetch jobs, run Matcher to score them, click "Prepare Application" on a match to invoke Writer, and track status through the Applications board.

**CLI pipeline demo:**
```powershell
uv run python scripts/demo_match.py
```
Runs the four-phase pipeline: Scout → Embed → Match → Print. Used as the live closer in the Sprint 2 presentation.

**Scripts in `scripts/`:**
- `scripts/demo_scout.py` — Scout in isolation (dry-run by default; `--details`, `--persist`)
- `scripts/demo_matcher.py` — Matcher in isolation (cosine preview; `--score`, `--show-profile`)
- `scripts/demo_match.py` — four-phase pipeline (Scout → Embed → Match → Print)
- `scripts/seed_demo_fixture.py` — records GWDG (prompt, response) pairs for the deterministic regression test

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (you)                               │
│   uploads CV · sets search preferences · clicks Apply           │
└───────────────────────┬─────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                  STREAMLIT DASHBOARD (UI)                       │
│   Jobs · Matches · Applications · Status · Delete my data       │
└───────────────────────┬─────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│               CREWAI-style ORCHESTRATOR                         │
│   Each agent is a focused class with DI (db, llm, tools)        │
└──────┬───────────────┬───────────────┬──────────────┬──────────┘
       ▼               ▼               ▼              ▼
  [SCOUT]         [MATCHER]        [WRITER]      [TRACKER]
  finds jobs      scores fit     writes .docx    tracks status
       │               │               │              │
       └───────────────┴───────┬───────┴──────────────┘
                               ▼
                  ┌────────────────────────┐
                  │   Supabase (Postgres   │
                  │   + pgvector HNSW)     │
                  │   + GWDG LLM endpoint  │
                  └────────────────────────┘
```

**Application status state machine** (enforced by `TrackerAgent`):
```
new → ready_to_send → applied → interview → offer
                          ↓         ↓         ↓
                       rejected  rejected  rejected
```

---

## Sprint summary

| Sprint | Deliverable | Key files |
|---|---|---|
| **1** | Research, architecture, legal/sources, DB schema, Scout Agent + Arbeitsagentur client | `docs/`, `src/job_agent/db/migrations/001_init.sql`, `agents/base_agent.py`, `agents/scout_agent.py`, `tools/arbeitsagentur_client.py` |
| **2** | Matcher Agent (CV parser, embeddings, pgvector RPC, LLM gap analysis) | `agents/matcher_agent.py`, `tools/cv_parser.py`, `tools/embedder.py`, migrations 003–006 |
| **3** | Writer Agent (cover letter Jinja + LLM, CV variant strict-subset, docx export) | `agents/writer_agent.py`, `tools/cover_letter_template.py`, `tools/cv_variant.py`, `tools/docx_exporter.py`, migrations 007–008 |
| **4** | Tracker Agent (state machine + GDPR delete) + Streamlit UI | `agents/tracker_agent.py`, `ui/app.py`, migration 009 |

---

## Reproducible demo fixture

The Matcher pipeline is frozen in `tests/fixtures/demo/`. Anyone cloning this repo can run:

```bash
uv run pytest tests/agents/test_matcher_agent.py -v
```

to verify the Matcher produces the exact Top-N from the Sprint 2 presentation slides — no GWDG or Supabase access required, the fixture replays recorded LLM responses.

---

## Stack

Python 3.11 · CrewAI-style agents · pydantic v2 (strict, `extra="forbid"`) · langchain-openai (against GWDG) · python-docx · pypdf · jinja2 · Supabase (Postgres + pgvector, HNSW cosine) · Streamlit 1.40+. Tooling: `uv`, `ruff`, `mypy`, `pytest`, `pre-commit`.

---

## Known limitations

- **GWDG quota** — free academic endpoint, occasional rate-limit or outage. Embeddings + chat both depend on it. Check status at https://docs.hpc.gwdg.de/services/ai-services/saia/.
- **JSearch optional** — only Arbeitsagentur is wired up as the primary source; JSearch/RapidAPI requires a `RAPIDAPI_KEY` in `.env` (200 req/month free tier; see `docs/sources.md`).
- **No auto-submit by design** — applications are never submitted programmatically. The user opens the job URL, applies manually, then clicks "Mark Applied" in the dashboard. This is a deliberate GDPR + ToS choice documented in `docs/legal.md` §2.4.
- **StepStone, LinkedIn, Indeed excluded** — robots.txt / ToS forbid scraping; we use the API-friendly Arbeitsagentur instead.
- **Single-user, local-only** — no multi-tenant model, no hosting, no mobile. The Streamlit dashboard runs on `localhost`.
- **90-day retention on jobs + match_scores** (per `purge_expired_data()` RPC); applications kept lifetime-of-project with snapshot fields so they survive the purge.

---

See `PLAN.md` for the original sprint plan, `PROGRESS.md` for per-sprint outcomes, `docs/concept.md` for the design rationale, and `docs/legal.md` for the GDPR / ToS posture.
