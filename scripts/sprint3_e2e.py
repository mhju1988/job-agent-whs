"""Sprint 3 live e2e — idempotent re-runnable version.

Flow:
  1. Clear any prior match_scores (fresh scoring run).
  2. Re-parse the dummy CV, embed it, replace the single profile row.
  3. For every job row missing an embedding, embed its (title + company + description)
     and patch the row in place. Do NOT re-fetch from Arbeitsagentur — operate on
     whatever is already in the `jobs` table.
  4. Run MatcherAgent → RPC + per-row LLM gap analysis → batch insert match_scores.
  5. Print the ranked results table.

Pre-conditions:
  - Migrations 001-005 applied.
  - Some jobs exist in the `jobs` table (e.g. from a prior Scout run).
  - GWDG /chat and /embeddings endpoints reachable.
"""

from __future__ import annotations

import sys
from pathlib import Path

from job_agent.agents.base_agent import BaseAgent
from job_agent.agents.matcher_agent import MatcherAgent
from job_agent.db.client import SupabaseClient
from job_agent.tools.cv_parser import CVParser
from job_agent.tools.embedder import Embedder

PDF_PATH = Path("artifacts/dummy_cv.pdf")
TOP_N = 5
SENTINEL_UUID = "00000000-0000-0000-0000-000000000000"


def _trunc(s: str | None, n: int = 38) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> int:
    db = SupabaseClient()
    raw = db.raw
    embedder = Embedder()

    # 1. Clear prior match_scores so we score fresh.
    print("[1/5] Clearing prior match_scores...")
    raw.table("match_scores").delete().neq("id", SENTINEL_UUID).execute()

    # 2. Reuse existing profile if one is in Supabase; only parse the PDF
    #    as a fallback. Avoids requiring the dummy CV when the dashboard's
    #    "Update CV" upload has already populated the profile.
    print("[2/5] Loading profile...")
    existing = raw.table("profile").select("id").limit(1).execute().data or []
    if existing:
        profile_id = existing[0]["id"]
        print("      ✓ Profile already in Supabase — skipping parse")
        print(f"      -> profile_id={profile_id}")
    else:
        if not PDF_PATH.exists():
            print(
                f"ERROR: no profile row in Supabase and {PDF_PATH} missing.\n"
                "      Either upload a CV via the Streamlit sidebar, or run\n"
                "      scripts/_make_dummy_cv.py to generate the fallback PDF.",
                file=sys.stderr,
            )
            return 2
        print(f"      no profile found — parsing {PDF_PATH}")
        parser = CVParser(llm_agent=BaseAgent())
        profile = parser.parse(PDF_PATH)
        prof_vec = embedder.embed_text(profile.to_embedding_text())
        print(f"      -> {len(profile.skills)} skills, profile vector dim={len(prof_vec)}")
        inserted = raw.table("profile").insert(
            profile.to_supabase_row() | {"embedding": prof_vec}
        ).execute()
        profile_id = inserted.data[0]["id"]
        print(f"      -> profile_id={profile_id}")

    # 3. Embed any jobs missing an embedding.
    print("[3/5] Embedding any jobs without a vector...")
    jobs = raw.table("jobs").select(
        "id, title, company, description, embedding"
    ).execute().data or []
    missing = [j for j in jobs if j.get("embedding") is None]
    print(f"      -> {len(jobs)} jobs total, {len(missing)} need embeddings")
    for j in missing:
        text = " ".join(
            filter(None, [j.get("title"), j.get("company"), j.get("description") or ""])
        )
        vec = embedder.embed_text(text)
        raw.table("jobs").update({"embedding": vec}).eq("id", j["id"]).execute()
    print(f"      -> patched {len(missing)} job embeddings")

    # 4. Run the Matcher.
    print(f"[4/5] Running MatcherAgent (top_n={TOP_N})...")
    matcher = MatcherAgent(db=db, llm_agent=BaseAgent())
    result = matcher.run(profile_id=profile_id, top_n=TOP_N)
    print(f"      -> considered={result.candidates_considered} "
          f"scored={result.scored} persisted={result.persisted} "
          f"errors={len(result.errors)}")
    for err in result.errors:
        print(f"        ! {err}")

    # 5. Read back the ranked results and print.
    print("[5/5] Ranked results:\n")
    rows = (
        raw.table("match_scores")
        .select("score, gaps, rationale, jobs(title, company)")
        .order("score", desc=True)
        .limit(TOP_N)
        .execute()
    )

    print("Rank | Score | Title                                  | Company                                | Top gap")  # noqa: E501
    print("-----|-------|----------------------------------------|----------------------------------------|--------")  # noqa: E501
    for i, r in enumerate(rows.data or [], start=1):
        title = _trunc((r.get("jobs") or {}).get("title"), 38)
        company = _trunc((r.get("jobs") or {}).get("company"), 38)
        gaps = r.get("gaps") or []
        top_gap = _trunc(gaps[0] if gaps else "", 30)
        score = int(round(r.get("score") or 0))
        print(f"  {i}  |  {score:>3}  | {title:<38} | {company:<38} | {top_gap}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
