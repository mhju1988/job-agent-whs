"""Matcher Agent demo: inspect both stages of the ranking pipeline in isolation.

Stage 1 (default, free): calls the `match_jobs_for_profile` pgvector RPC and
prints the cosine-similarity ranking — no LLM calls, no DB writes.

Stage 2 (--score): runs the full MatcherAgent (LLM gap analysis) on the top-N
candidates and prints the persisted match rows.

--show-profile prints the exact candidate brief the LLM receives.

Usage:
    uv run python scripts/demo_matcher.py --profile-id <uuid>
    uv run python scripts/demo_matcher.py --profile-id <uuid> --top-n 10 --include-scored
    uv run python scripts/demo_matcher.py --profile-id <uuid> --show-profile
    uv run python scripts/demo_matcher.py --profile-id <uuid> --score --top-n 3
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from job_agent.agents.matcher_agent import MatcherAgent
from job_agent.db.client import SupabaseClient


def _print_header(text: str) -> None:
    print()
    print("=" * 70)
    print(text)
    print("=" * 70)


def _wrap(text: str, indent: str = "                ", width: int = 78) -> None:
    """Print text wrapped at word boundaries for projector legibility."""
    line = indent
    for w in text.split():
        if len(line) + len(w) + 1 > width:
            print(line)
            line = indent + w
        else:
            line += ("" if line == indent else " ") + w
    if line.strip():
        print(line)


def _show_profile(db: SupabaseClient, profile_id: str) -> int:
    resp = (
        db.raw.table("profile")
        .select("summary, skills, experience, education, languages")
        .eq("id", profile_id)
        .limit(1)
        .execute()
    )
    row: dict[str, Any] | None = resp.data[0] if resp.data else None
    if row is None:
        print(f"\n  No profile found with id {profile_id}", file=sys.stderr)
        return 1
    print("\nCandidate brief (exactly what the LLM receives per job):")
    print("-" * 70)
    print(MatcherAgent._build_candidate_text(row))
    print("-" * 70)
    return 0


def _preview(db: SupabaseClient, profile_id: str, top_n: int,
             exclude_scored: bool) -> int:
    """Stage 1 only: cosine ranking via the pgvector RPC. Zero LLM calls."""
    label = "unscored only" if exclude_scored else "including already-scored"
    print(f"\n[stage 1] pgvector cosine ranking — top {top_n}, {label}...")

    rows = db.raw.rpc(
        "match_jobs_for_profile",
        {"profile_id": profile_id, "top_n": top_n, "exclude_scored": exclude_scored},
    ).execute().data or []

    if not rows:
        print(
            "\n  RPC returned 0 candidates. Either the profile id is wrong, the\n"
            "  profile has no embedding, or every job within the HNSW search\n"
            "  horizon (ef_search=40 nearest) is already scored.",
            file=sys.stderr,
        )
        return 1

    print(f"\n  {'#':>3}  {'cosine':>7}  {'title':<48}  company")
    print(f"  {'-' * 3}  {'-' * 7}  {'-' * 48}  {'-' * 20}")
    for i, r in enumerate(rows, start=1):
        title = (r.get("title") or "?")[:48]
        company = (r.get("company") or "?")[:28]
        print(f"  {i:>3}  {r['similarity']:>7.4f}  {title:<48}  {company}")

    print(
        "\n  (stage 1 is the cheap narrowing pass — no LLM involved;"
        " run with --score to apply the LLM gap analysis)"
    )
    return 0


def _score(db: SupabaseClient, profile_id: str, top_n: int) -> int:
    """Stage 1 + 2: full MatcherAgent run, then print the new match rows."""
    print(f"\n[stage 1+2] MatcherAgent.run — top {top_n}, LLM gap analysis...")
    matcher = MatcherAgent(db=db)
    result = matcher.run(profile_id, top_n=top_n, exclude_scored=True)
    print(f"      Considered: {result.candidates_considered} | "
          f"Scored: {result.scored} | "
          f"Persisted: {result.persisted}")
    if result.errors:
        print(f"      Errors ({len(result.errors)}):")
        for err in result.errors[:5]:
            print(f"        - {err}")
    if result.scored == 0:
        print(
            "\n  Nothing scored — all candidates within the search horizon are\n"
            "  already in match_scores. Fetch fresh jobs first (demo_scout.py\n"
            "  --persist, then embed) or use demo_match.py for the full loop.",
            file=sys.stderr,
        )
        return 1

    rows = (
        db.raw.table("match_scores")
        .select("score, matched_skills, gaps, rationale, jobs(title, company)")
        .order("created_at", desc=True)
        .limit(result.persisted)
        .execute()
    ).data or []

    for i, row in enumerate(rows, start=1):
        job = row.get("jobs") or {}
        print()
        print(f"  [{i}] {job.get('title') or '?'}")
        print(f"      Company:    {job.get('company') or '?'}")
        print(f"      Score:      {row.get('score') or 0:>5.0f} / 100")
        if row.get("matched_skills"):
            print(f"      Matched:    {', '.join(row['matched_skills'][:5])}")
        if row.get("gaps"):
            print(f"      Gaps:       {', '.join(row['gaps'][:3])}")
        if row.get("rationale"):
            print("      Rationale:")
            _wrap(row["rationale"])
    print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile-id", required=True,
                    help="UUID of the profile to rank against")
    ap.add_argument("--top-n", type=int, default=5,
                    help="Number of candidates (default 5)")
    ap.add_argument("--include-scored", action="store_true",
                    help="Preview mode: also show jobs that already have a score")
    ap.add_argument("--score", action="store_true",
                    help="Run the full LLM gap analysis and persist results "
                         "(default: cosine preview only, no LLM calls)")
    ap.add_argument("--show-profile", action="store_true",
                    help="Print the candidate brief the LLM receives, then exit")
    args = ap.parse_args()

    mode = "SCORE (LLM)" if args.score else "PREVIEW (cosine only)"
    _print_header(f"Matcher demo [{mode}] — profile {args.profile_id[:8]}...")

    db = SupabaseClient()

    if args.show_profile:
        return _show_profile(db, args.profile_id)
    if args.score:
        return _score(db, args.profile_id, args.top_n)
    return _preview(db, args.profile_id, args.top_n,
                    exclude_scored=not args.include_scored)


if __name__ == "__main__":
    raise SystemExit(main())
