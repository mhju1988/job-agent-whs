"""Sprint 2 live demo: fetch fresh jobs from Arbeitsagentur and score them.

Used as the live closer of the Sprint 2 presentation. Runs end-to-end against
real GWDG + Supabase + Arbeitsagentur. Output is sized for projector display.

Usage:
    uv run python scripts/demo_match.py --profile-id <uuid>
    uv run python scripts/demo_match.py --profile-id <uuid> --query "Data Engineer" --limit 3
"""

from __future__ import annotations

import argparse
import sys

from job_agent.agents.matcher_agent import MatcherAgent
from job_agent.agents.scout_agent import ScoutAgent
from job_agent.db.client import SupabaseClient
from job_agent.tools.arbeitsagentur_client import ArbeitsagenturClient
from job_agent.tools.embedder import Embedder


def _build_job_embedding_text(job: dict) -> str:
    """Compact textual representation of a job, used for embedding."""
    parts = [
        job.get("title") or "",
        job.get("company") or "",
        ", ".join(job.get("requirements") or []),
        job.get("description") or "",
    ]
    return "\n".join(p for p in parts if p).strip()


def _embed_unembedded_jobs(
    db: SupabaseClient,
    embedder: Embedder,
    limit: int,
) -> int:
    """Embed up to `limit` jobs that currently have NULL embedding. Returns count embedded."""
    resp = (
        db.raw.table("jobs")
        .select("id, title, company, requirements, description")
        .is_("embedding", "null")
        .limit(limit)
        .execute()
    )
    pending = resp.data or []
    if not pending:
        return 0

    for job in pending:
        text = _build_job_embedding_text(job)
        if not text:
            continue
        emb = embedder.embed_text(text)
        db.raw.table("jobs").update({"embedding": emb}).eq("id", job["id"]).execute()
    return len(pending)


def _print_header(text: str) -> None:
    print()
    print("=" * 70)
    print(text)
    print("=" * 70)


def _print_match(row: dict, n: int) -> None:
    job = row.get("jobs") or {}
    title = job.get("title") or "?"
    company = job.get("company") or "?"
    score = row.get("score") or 0.0
    matched = row.get("matched_skills") or []
    gaps = row.get("gaps") or []
    rationale = row.get("rationale") or ""

    print()
    print(f"  [{n}] {title}")
    print(f"      Company:    {company}")
    print(f"      Score:      {score:>5.0f} / 100")
    if matched:
        print(f"      Matched:    {', '.join(matched[:5])}")
    if gaps:
        print(f"      Gaps:       {', '.join(gaps[:3])}")
    if rationale:
        # Wrap rationale to ~60 chars/line at word boundary for projector legibility
        words = rationale.split()
        line = "      Rationale:  "
        prefix = " " * len(line.rstrip(" ").replace("Rationale:", "          "))
        first = True
        for w in words:
            if len(line) + len(w) > 78:
                print(line)
                line = prefix + w
            else:
                line += (("" if first else " ") + w)
            first = False
        print(line)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile-id", required=True,
                    help="UUID of the profile to score against")
    ap.add_argument("--query", default="Python Developer",
                    help="Arbeitsagentur search query (default: 'Python Developer')")
    ap.add_argument("--limit", type=int, default=1,
                    help="Number of fresh jobs to fetch and score (default 1)")
    args = ap.parse_args()

    _print_header(f"Sprint 2 live demo — query: {args.query!r}, limit: {args.limit}")

    db = SupabaseClient()
    embedder = Embedder()

    print("\n[1/4] Fetching fresh jobs from Arbeitsagentur...")
    scout = ScoutAgent(client=ArbeitsagenturClient.with_default_opener())
    scout_result = scout.run(keyword=args.query, page_size=max(args.limit, 5))
    print(f"      Fetched: {scout_result.fetched} | "
          f"Normalized: {scout_result.normalized} | "
          f"Upserted: {scout_result.upserted}")

    if scout_result.upserted == 0 and scout_result.fetched == 0:
        print("\n      No jobs returned. Try a different --query.", file=sys.stderr)
        return 1

    print("\n[2/4] Embedding fresh jobs via GWDG (multilingual-e5-large-instruct)...")
    embed_target = max(args.limit * 4, 5)
    embedded_count = _embed_unembedded_jobs(db, embedder, limit=embed_target)
    print(f"      Embedded: {embedded_count} job(s)")

    print("\n[3/4] Scoring with MatcherAgent (cosine + LLM gap analysis)...")
    matcher = MatcherAgent(db=db)
    result = matcher.run(args.profile_id, top_n=args.limit, exclude_scored=True)
    print(f"      Considered: {result.candidates_considered} | "
          f"Scored: {result.scored} | "
          f"Persisted: {result.persisted}")

    if result.errors:
        print(f"      WARNING: {len(result.errors)} error(s) during scoring:")
        for err in result.errors[:3]:
            print(f"        - {err}")

    if result.scored == 0:
        print(
            "\n      No new jobs to score (matcher excludes already-scored jobs).\n"
            "      Try a fresh --query or re-seed the demo profile.",
            file=sys.stderr,
        )
        return 1

    print("\n[4/4] Top matches:")
    rows = (
        db.raw.table("match_scores")
        .select("*, jobs(title, company)")
        .order("created_at", desc=True)
        .limit(args.limit)
        .execute()
    ).data or []

    for i, row in enumerate(rows, start=1):
        _print_match(row, i)

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
