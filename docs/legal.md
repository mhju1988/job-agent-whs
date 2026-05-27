# Legal & Compliance — Automated Job Application Agent (Sprint 1)

This document captures the legal and ethical constraints for the project. It is read alongside `docs/sources.md` (per-source ToS verdicts) and `CLAUDE.md` (project rules).

Scope: solo university project (W-HS, "Agentic AI"), non-commercial, single-user, Germany-focused, deployed locally only.

---

## 1. Manual-submit-only policy

- The agent **never** submits a job application automatically. It generates artifacts (cover letter `.docx`, tailored CV `.docx`) and surfaces a "ready to send" state in the Streamlit UI.
- The human user clicks "Apply" on the actual job-board page themselves.
- **Why:** automated submission would (a) violate most job-board ToS, (b) cross the GDPR boundary for processing personal data of recruiters/employers without explicit basis, and (c) risk filing low-quality applications at scale — the opposite of the project's intent.
- Enforced in code by: no HTTP POST to apply endpoints; no Playwright `click()` on apply buttons; Writer Agent's only output is local files plus a status row.

---

## 2. GDPR posture

### 2.1 Roles
- **Controller:** the user (project author), processing their own data and publicly-available job-listing data for personal academic use.
- **Processors used:** GWDG LLM endpoint (university-hosted, Germany), Supabase (data-residency configured to EU region during setup), JSearch/RapidAPI (acts as processor per their Feb-2025 DPA).
- **Data subjects whose data may be incidentally processed:** named contact persons in job listings (recruiter names, emails).

### 2.2 Lawful basis (Art. 6 GDPR)
- Processing of the user's own CV: **Art. 6(1)(a) consent** (the user is the data subject and the controller).
- Processing of public job-listing data: **Art. 6(1)(f) legitimate interest** for personal academic study; balanced against limited data minimisation and short retention.

### 2.3 Data minimisation rules (enforced in schema)
- Do **not** store recruiter email addresses or phone numbers from listings. If present in `job_description`, leave them in the raw text but do not extract to a structured PII field.
- Do **not** store any candidate (non-user) data — the agent is single-user.
- Embeddings are derived from the user's own CV and public job text only.

### 2.4 Retention
- `jobs` table: 90 days after `scraped_at`, then hard-deleted. Listings expire fast; long-term storage is not justifiable under "legitimate interest" balancing.
- `match_scores`: 90 days, tied to `job_id` (cascade).
- `applications`: kept for the project lifetime (the user's own record of where they applied), then deleted at project end.
- `profile` (user's own CV): kept until the user deletes it via the UI.
- Generated `.docx` artifacts: local-only, in `artifacts/` (gitignored). Deleted by the user when no longer needed.

### 2.5 Right to erasure / portability
- For a single-user system, the user can delete their `profile` row and all generated artifacts directly. The Tracker UI exposes a "Delete my data" action in Sprint 5.

### 2.6 No transfer to third countries
- GWDG: hosted in Germany (university cloud) — no transfer.
- Supabase: project will be created in an **EU region** (Frankfurt or Dublin); verify at signup.
- RapidAPI/JSearch: requests do leave the EU. Mitigation: send only the search query (keyword + location), never user CV content. Cache results locally so re-queries are unnecessary.

---

## 3. Per-source ToS compliance

| Source | ToS compliance line item | How we comply |
|---|---|---|
| **Arbeitsagentur Jobsuche API** | No formal ToS; BA opposes mass automated access. | Conservative rate limit (≤100 req/hr, well under the 1,000/hr cap); single-user usage; identifying User-Agent set to project name + contact email; no resale or republication of listings. |
| **Adzuna API** | 14-day academic trial; written consent for ongoing use; derivative works restricted. | Honour the trial window; email Adzuna for an academic licence before extended use (see `docs/sources.md` TODO); store the `redirect_url` and original IDs so attribution is preserved. |
| **JSearch (RapidAPI)** | Permissive for academic/personal use; RapidAPI DPA covers data processing; PII storage discouraged. | Cache only the listing fields needed for matching/display; do not persist recruiter PII fields; honour 200 req/month free-tier hard limit. |
| **StepStone.de** | robots.txt disallows `/jobs/`; ToS explicitly bans bots and automated scraping. | **Excluded.** No requests of any kind to StepStone from this project. |

---

## 4. Hard rules (enforced by code review)

1. **No auto-submit.** No code path may POST an application to a third-party site.
2. **No scraping of StepStone or any source not listed in `docs/sources.md`.** Adding a new source requires a new entry in `sources.md` plus a `legal.md` update.
3. **Robots.txt is checked before any Playwright run** in Sprint 2. A `User-Agent` identifying the project + a contact email is set.
4. **Rate limits are enforced client-side**, not just trusted from the server — every source client carries an explicit cap.
5. **No paid LLM APIs.** GWDG endpoint only.
6. **Secrets** live in `.env`, never committed (see `.gitignore`).
7. **No PII extraction** from listings into structured fields.
8. **All artifacts are local** (`artifacts/`, gitignored). Nothing is auto-uploaded anywhere.

---

## 5. Open follow-ups

- Verify Supabase project region is EU at signup (Sprint 1 deliverable).
- Email Adzuna for an academic licence before the 14-day trial expires (deferred 2026-05-13, see `sources.md`).
- Add a project contact email to the User-Agent string used by Scout (Sprint 2).
- Add a "Delete my data" action to the Streamlit UI (Sprint 5).

---

## 6. Disclaimer

This document is the author's own compliance reasoning for an academic project, not legal advice. The project is non-commercial, single-user, and not deployed publicly.
