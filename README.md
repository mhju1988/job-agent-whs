# Automated Job Application Agent

Solo university project (W-HS "Agentic AI", Project #7). Fetches jobs, matches them against your CV, generates a tailored cover letter + CV variant, and tracks each application — through a multi-user web app (Next.js frontend + FastAPI backend over the CrewAI-style agent core, with Supabase Auth + Row-Level Security).

Built as four CrewAI-style agents (Scout · Matcher · Writer · Tracker) over Supabase (Postgres + pgvector) with the GWDG OpenAI-compatible LLM endpoint.

**[▶ Project website](https://mhju1988.github.io/job-agent-whs/)** · **[Pitch deck (PDF)](docs/pitch_deck.pdf)** · **[Deployment guide](DEPLOY.md)**

> **▶ [Watch the product walkthrough (screencast)](https://github.com/mhju1988/job-agent-whs/releases/download/final/job-agent-walkthrough.mp4)** — the whole loop end to end: upload CV → Scout → Matcher → Writer → Tracker, with the human keeping the Apply click. _(Also on the [release page](https://github.com/mhju1988/job-agent-whs/releases/tag/final).)_

---

## Quick start with Docker

The fastest way to run the whole stack. You still need a Supabase project + a GWDG API key.

```bash
cp .env.example .env                 # fill in Supabase + GWDG keys
# add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY too (Compose reads them)
docker compose up -d --build         # builds the api + web images and starts both
```

Open **http://localhost:3000**. The `api` service runs on `:8000`, `web` on `:3000` — the same two-service layout used in deployment (see [DEPLOY.md](DEPLOY.md)). Apply the Supabase migrations once (below) before first use.

For day-to-day development, prefer running the two services directly (`uv run uvicorn …` / `npm run dev`) — see [How to run](#how-to-run).

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
GWDG_MODEL=llama-3.3-70b-instruct
GWDG_EMBED_MODEL=multilingual-e5-large-instruct
LOG_LEVEL=INFO
ARTIFACTS_DIR=artifacts
```

### 4. Apply Supabase migrations
Open the Supabase SQL Editor and run each file in `src/job_agent/db/migrations/` in numeric order (001 → 020). The `supabase-py` client cannot run DDL, so this is manual.

### 5. Verify
```powershell
uv run pytest -q          # 338 tests, all mocked, no live calls
uv run ruff check src/ tests/
uv run mypy src/
```

---

<a id="how-to-run"></a>
## How to run

The product is a **multi-user web app**: a FastAPI backend + a Next.js frontend, with Supabase Auth.

**1. Backend API** (run *without* `--reload` for long agent requests):
```powershell
uv run uvicorn job_agent.api.main:app        # http://localhost:8000 ; OpenAPI at /docs
```

**2. Frontend** (separate terminal):
```powershell
cd frontend
npm install                                   # first time
copy .env.local.example .env.local            # fill in NEXT_PUBLIC_* (Supabase URL + anon key + API base)
npm run dev                                   # http://localhost:3000
```
Sign in (create a user in the Supabase dashboard → Authentication), then: Dashboard · Jobs (run Scout) · Matches (prepare application) · Applications (kanban pipeline) · Profile (CV upload + GDPR delete) · Observability. Long agent runs stream live progress in the run drawer (SSE). The bold "command-center" design system is previewed at `/styleguide`.

> Auth note: the API verifies Supabase access tokens — **ES256** (the newer asymmetric signing keys) via JWKS automatically, or **HS256** via `SUPABASE_JWT_SECRET`. The per-request DB client is bound to the caller's JWT so Postgres RLS enforces per-user isolation.

**End-to-end CLI demo** (pipeline without the UI):
```powershell
uv run python scripts/sprint5_demo.py
```
Runs the full pipeline: Scout → Matcher → Writer → Tracker, prints a final summary block. Idempotent on rerun.

**Per-sprint smoke/e2e scripts** in `scripts/`:
- `sprint2_scout_smoke.py` — fetch 5 jobs (no DB write)
- `sprint3_e2e.py` — parse CV, embed, score
- `sprint4_writer_smoke.py` — render docs only (no DB write)
- `sprint4_writer_e2e.py` — full Writer + DB persist
- `sprint5_demo.py` — full pipeline + Tracker transition

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER (browser)                            │
│   uploads CV · searches jobs · reviews matches · clicks Apply    │
└───────────────────────┬──────────────────────────────────────────┘
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│           NEXT.JS FRONTEND (App Router · React 18 · TS)          │
│  Dashboard · Jobs · Matches · Applications · Profile · Observ.   │
│  Supabase Auth (JWT) · TanStack Query · SSE inline progress      │
└───────────────────────┬──────────────────────────────────────────┘
                        ▼ REST + SSE
┌──────────────────────────────────────────────────────────────────┐
│              FASTAPI BACKEND  (src/job_agent/api/)               │
│  JWT verification + per-request RLS client · /runs/* SSE routes  │
└──────┬───────────────┬───────────────┬──────────────┬───────────┘
       ▼               ▼               ▼              ▼
  [SCOUT]         [MATCHER]        [WRITER]      [TRACKER]
  finds jobs      scores fit     writes .docx    tracks status
       │               │               │              │
       └───────────────┴───────┬───────┴──────────────┘
                               ▼
                  ┌────────────────────────┐
                  │   Supabase (Postgres   │
                  │   + pgvector HNSW)     │
                  │   Auth + RLS           │
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
| **1** | Architecture · sources · legal · DB schema · BaseAgent | `docs/`, `migrations/001_init.sql`, `agents/base_agent.py` |
| **2** | Scout Agent + Arbeitsagentur client | `agents/scout_agent.py`, `tools/arbeitsagentur_client.py`, `models/job.py` |
| **3** | Matcher Agent + CV parser + embeddings | `agents/matcher_agent.py`, `tools/embedder.py`, `tools/cv_parser.py`, migrations 003–005 |
| **4** | Writer Agent + cover letter Jinja + CV variant + docx export | `agents/writer_agent.py`, `tools/cover_letter_template.py`, `tools/cv_variant.py`, `tools/docx_exporter.py`, migrations 006–007 |
| **5** | Tracker Agent + Streamlit UI (later removed) + demo | `agents/tracker_agent.py`, `scripts/sprint5_demo.py` |
| **Post** | Multi-tenancy · FastAPI backend · Next.js frontend · observability · SSE live progress | `src/job_agent/api/`, `frontend/`, migrations 008–016 |
| **Post** | Jobs page redesign · Matcher explicit job_ids · cached suggestions · LLM timeout | `frontend/src/app/(app)/jobs/page.tsx`, `agents/matcher_agent.py`, `config.py` |

Final state: **338 tests green**, ruff + mypy clean, frontend tsc clean.

---

## Stack

**Backend:** Python 3.11 · CrewAI-style agents · pydantic v2 (strict, `extra="forbid"`) · langchain-openai (against GWDG, 120 s timeout) · python-docx · pypdf · jinja2 · Supabase (Postgres + pgvector HNSW cosine, Auth + RLS) · FastAPI + uvicorn + sse-starlette · PyJWT. **Frontend:** Next.js 14.2 (App Router, TypeScript, React 18) · Tailwind v3 · shadcn/ui (Radix) · TanStack Query v5 · `@supabase/supabase-js` · `@microsoft/fetch-event-source` · motion/react. Tooling: `uv`, `ruff`, `mypy`, `pytest`; `eslint`, `tsc`, `vitest`.

---

## Known limitations

- **GWDG quota** — free academic endpoint, occasional rate-limit or outage. Embeddings + chat both depend on it. Check status at https://docs.hpc.gwdg.de/services/ai-services/saia/.
- **Job sources** — Arbeitsagentur is primary (no key). JSearch/RapidAPI is optional (set `RAPIDAPI_KEY`). Adzuna is evaluated in `docs/sources.md` but not wired.
- **No auto-submit by design** — applications are never submitted programmatically. The user opens the job URL, applies manually, then clicks "Mark Applied" in the dashboard. This is a deliberate GDPR + ToS choice documented in `docs/legal.md` §2.4.
- **StepStone, LinkedIn, Indeed excluded** — robots.txt / ToS forbid scraping; we use the API-friendly Arbeitsagentur instead.
- **Multi-user** — Supabase Auth + per-user `user_id` + Row-Level Security isolate each user's profile, matches, and applications; jobs are a shared global pool. Runs locally by default (API on `:8000`, web on `:3000`); not yet hardened for public hosting.
- **90-day retention on jobs + match_scores**, enforced nightly by `purge_expired_data()` scheduled via pg_cron (migration 018); applications kept lifetime-of-project with snapshot fields so they survive the purge.

---

## Deployment

The app deploys as **two services** (backend `api` + frontend `web`) from this one repo — locally via `docker compose up` (above) or to a host like Railway from the same `Dockerfile` / `frontend/Dockerfile`. Full step-by-step — env vars, cross-service URL wiring, Supabase redirect config, SSE/long-request notes, and artifact-persistence caveats — is in **[DEPLOY.md](DEPLOY.md)**.

---

See **[DEPLOY.md](DEPLOY.md)** for deployment, `docs/legal.md` for the GDPR / ToS posture, and `docs/sources.md` for the per-source job-board terms review.
