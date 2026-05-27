# Job Sources — Evaluation (Sprint 1)

## Summary table

| Source | Type | Legal verdict | Coverage (DE) | Auth | Rate limit | Recommendation |
|---|---|---|---|---|---|---|
| Adzuna API | Official API | Gray — academic trial OK, ongoing use needs written consent | Good (one of 12 supported countries, `de` code) | `app_id` + `app_key` via registration | 2,500/month; 250/day; 25/min | Fallback / supplementary |
| Arbeitsagentur (Jobboerse) | Unofficial-but-public API | Gray — no formal ToS published; BA hostile to mass access but no enforcement record | Excellent — Germany's largest job DB | Static public key `jobboerse-jobsuche` as `X-API-Key` header | ~1,000 req/hour (community-reported) | Primary |
| StepStone.de | Scraping target | Forbidden — robots.txt disallows `/jobs/` paths; ToS explicitly bans bots | Excellent | N/A | N/A | Excluded |
| JSearch (RapidAPI) | Aggregator API (Google for Jobs) | Gray — permissive for academic/personal use under RapidAPI ToS | Good (supports `country=de`) | `X-RapidAPI-Key` + `X-RapidAPI-Host` | 200/month, 1,000/hr (free Basic) | Second fallback |

---

## 1. Adzuna API

- **Legal verdict:** Gray. Academic use is explicitly permitted for a **14-day trial** to validate coverage. Ongoing research requires **written consent from Adzuna** and may require a licence agreement. Derivative works (aggregations, counts, ongoing research outputs) are prohibited without authorisation. Source: [Adzuna ToS](https://developer.adzuna.com/docs/terms_of_service)
- **Credentials:** Registration required at [developer.adzuna.com](https://developer.adzuna.com/). Provides `app_id` and `app_key`, both passed as query parameters.
- **Rate limit:** Free tier — 25 hits/min, 250 hits/day, 1,000 hits/week, 2,500 hits/month. Higher limits negotiable for commercial use. Source: [Adzuna ToS](https://developer.adzuna.com/docs/terms_of_service)
- **Germany coverage:** Confirmed — Germany (`de`) is one of 12 supported countries with EUR pricing. Source: [adzuna-job-search-mcp GitHub](https://github.com/folathecoder/adzuna-job-search-mcp)
- **Fields returned:** `title`, `id`, `description` (snippet), `salary_min`, `salary_max`, `salary_is_predicted`, `location` (area hierarchy + display_name), `company.display_name`, `contract_type`, `contract_time`, `category`, `created`, `redirect_url`, `latitude`, `longitude`. Source: [Adzuna API docs /search](https://developer.adzuna.com/docs/search)
- **Endpoint pattern:** `https://api.adzuna.com/v1/api/jobs/de/search/{page}?app_id=...&app_key=...`
- **Notes:** 2,500 req/month is tight for a job-agent doing repeated polling. Free tier is suitable for sprint demo and academic validation. Ongoing use past 14 days is legally ambiguous — requires email to Adzuna.

---

## 2. Arbeitsagentur API

- **Legal verdict:** Gray — no formal published ToS. The Bundesagentur für Arbeit (BA) is on record opposing mass automated access (netzpolitik.org, 2021) but has not pursued legal action against academic/individual users. The API endpoint is publicly accessible via a well-known static key, making it effectively open data in practice, though not officially licensed as such. The BA's own portal uses this API for its public job search, which supports public-access intent. Acceptable for this academic solo-user project under the legitimate-interest balancing and rate-limit/UA mitigations documented in [docs/legal.md §2.2 and §3](legal.md). Source: [bundesAPI/jobsuche-api](https://github.com/bundesAPI/jobsuche-api), [netzpolitik.org](https://netzpolitik.org/2021/open-data-arbeitsagentur-kaempft-gegen-offene-schnittstelle/)
- **Auth model:** HTTP header `X-API-Key: jobboerse-jobsuche` — a publicly known static key, no registration required. Confirmed 401 without header (live test). Source: [bundesAPI/jobsuche-api README](https://github.com/bundesAPI/jobsuche-api/blob/main/README.md)
- **Rate limit:** 1,000 requests/hour (community-reported; returns HTTP 429 on excess). No official documentation of this limit. Source: [publicapi.dev/arbeitsamt-api](https://publicapi.dev/arbeitsamt-api)
- **Coverage:** Germany's largest job database — the official federal job board (Jobboerse). Covers public-sector, trade, and white-collar listings. Filterable by keyword (`was`), location (`wo`), employment type, salary, and qualification. Source: [bundesAPI/jobsuche-api](https://github.com/bundesAPI/jobsuche-api)
- **Endpoint:** `https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs`
- **Notes:** Best DE coverage for a Germany-focused academic project. Key risk: BA could change the static key or add CAPTCHA (already happened once in 2021, bypassed within days). Implement graceful fallback to Adzuna if 401 occurs. Apply conservative rate limiting (e.g., max 100 req/hour in agent) to stay well under threshold.

---

## 3. StepStone.de

- **robots.txt verdict:** Strongly restrictive. Disallows `/jobs/vollzeit/`, `/jobs/teilzeit/`, `/jobs/home-office/`, `/jobs/*?*` (job pages with query params), `/5/ergebnisliste.html`, `/5/job-search-*.html`, `/search-results`, `/search-results/*`. Only user-agent `Jobsearch1.5` receives limited exemptions. Source: [stepstone.de/robots.txt](https://www.stepstone.de/robots.txt)
- **ToS verdict:** Explicitly forbidden. StepStone's Nutzungsbedingungen prohibit: (1) using scraping or comparable techniques to capture and repurpose content; (2) using automated bots, scripts, plugins, or extensions to extract content. Source: [stepstone.de Nutzungsbedingungen 2022](https://www.stepstone.de/ueber-stepstone/nutzungsbedingungen-2022-03/) (confirmed via search; direct page timed out)
- **Go / No-go:** **NO-GO.** Both robots.txt and ToS independently forbid automated access to job listings. Proceeding would violate ToS and conflict with robots.txt, creating legal and ethical risk even for a non-commercial academic project. No viable path forward without a partnership/API agreement with StepStone.

---

## 4. JSearch (RapidAPI)

- **Legal verdict:** Gray — permissive for academic/personal use. RapidAPI's ToS does not explicitly prohibit storing results for non-commercial projects; their GDPR DPA (Feb 2025) positions RapidAPI as data processor. Long-term bulk storage of employer PII would be inadvisable under GDPR. Source: [RapidAPI ToS](https://rapidapi.com/page/terms), [RapidAPI GDPR](https://docs.rapidapi.com/docs/gdpr-information)
- **Credentials:** RapidAPI key sent as `X-RapidAPI-Key` header; also requires `X-RapidAPI-Host: jsearch.p.rapidapi.com`. Obtain via RapidAPI dashboard (no credit card for Basic). Source: [JSearch API Details](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch/details)
- **Rate limit (free):** 200 requests/month, 1,000 req/hour. Hard limit enforced — exceeding returns HTTP 429 (no accidental overage charges). Paid tiers start at $25/month for 10,000 req/month. Source: [JSearch Pricing](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch/pricing)
- **Germany coverage:** Sources from Google for Jobs + open web. Supports `country=de` query parameter and free-text `location` (e.g., `location=Berlin`). Response fields include `job_city`, `job_state`, `job_country`. Coverage mirrors Google for Jobs Germany index — broad but not exhaustive for BA-only postings. Source: [JSearch API Docs - OpenWeb Ninja](https://www.openwebninja.com/api/jsearch/docs)
- **Schema (key fields, normalisability):** Response: `{ status, request_id, parameters, data[] }`. Each job has `job_id`, `job_title`, `employer_name`, `employer_logo`, `job_city`, `job_state`, `job_country`, `job_description`, `job_apply_link`, `job_posted_at_datetime_utc`, plus 30+ supplementary fields (salary, skills, experience level). Maps cleanly to a unified `Job` pydantic model alongside Arbeitsagentur (`titel`, `arbeitgeber`, `arbeitsort.ort`) and Adzuna (`title`, `company.display_name`, `location.display_name`) via a thin adapter layer.
- **Notes:** 200 req/month is tight but sufficient for nightly Scout runs with disciplined batching (~5–10 searches/day). Pagination via `page`/`num_pages` params. Pure REST — no Playwright needed.

---

## Recommendation

- **Primary:** Arbeitsagentur Jobsuche API — best DE coverage, no registration friction, 1,000 req/hr limit is sufficient for academic load, effectively open access in practice.
- **Fallback (1):** Adzuna API — register for free `app_id`/`app_key`, use during 14-day trial for sprint validation; contact Adzuna for an academic licence for ongoing use. Complements Arbeitsagentur with private-sector listings.
- **Fallback (2):** JSearch (RapidAPI) — Google-for-Jobs aggregator, `country=de` supported, 200 req/month free; useful when Arbeitsagentur is rate-limited and Adzuna's monthly cap is exhausted. Clean schema, normalises easily.
- **Excluded:** StepStone.de — robots.txt and ToS both forbid automated scraping. Risk outweighs any coverage benefit.

---

## Open questions for user

1. **Adzuna ongoing licence:** The free tier allows a 14-day academic trial. If the agent is used beyond Sprint 1, should we email Adzuna to request an academic licence? (Low effort, likely approved for a university project.)
   <!-- TODO: email Adzuna for academic licence before the 14-day trial expires (deferred 2026-05-13). -->

2. **Arbeitsagentur risk tolerance:** The BA has historically opposed open API access. Are you comfortable relying on the static public key for a university demo, given the risk it could be rotated? A fallback-first design (Arbeitsagentur primary, Adzuna fallback) mitigates this.
3. **Additional sources:** Decided 2026-05-13 — no Indeed/Xing/LinkedIn. MVP locks to Arbeitsagentur + Adzuna + JSearch.

---

## Sources consulted

- [Adzuna Terms of Service](https://developer.adzuna.com/docs/terms_of_service)
- [Adzuna Developer Overview](https://developer.adzuna.com/overview)
- [Adzuna MCP / Country List](https://github.com/folathecoder/adzuna-job-search-mcp)
- [bundesAPI/jobsuche-api README](https://github.com/bundesAPI/jobsuche-api/blob/main/README.md)
- [publicapi.dev — Arbeitsamt API](https://publicapi.dev/arbeitsamt-api)
- [netzpolitik.org — Arbeitsagentur vs open API](https://netzpolitik.org/2021/open-data-arbeitsagentur-kaempft-gegen-offene-schnittstelle/)
- [StepStone robots.txt](https://www.stepstone.de/robots.txt)
- [StepStone Nutzungsbedingungen 2022](https://www.stepstone.de/ueber-stepstone/nutzungsbedingungen-2022-03/)
- [JSearch on RapidAPI — pricing](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch/pricing)
- [JSearch on RapidAPI — details](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch/details)
- [JSearch API Docs — OpenWeb Ninja](https://www.openwebninja.com/api/jsearch/docs)
- [RapidAPI Terms of Service](https://rapidapi.com/page/terms)
- [RapidAPI GDPR Information](https://docs.rapidapi.com/docs/gdpr-information)
