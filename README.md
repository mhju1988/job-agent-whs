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
