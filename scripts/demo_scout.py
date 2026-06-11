"""Scout Agent demo: fetch jobs from Arbeitsagentur and inspect the results.

Tests the Scout pipeline in isolation (no embeddings, no matcher). By default
runs DRY — fetches and normalises but does NOT write to the database, so it is
safe for rehearsals. Pass --persist to run the real ScoutAgent with upsert.

Usage:
    uv run python scripts/demo_scout.py --query "Python Developer"
    uv run python scripts/demo_scout.py --query "Data Engineer" --location "Essen" --page-size 10
    uv run python scripts/demo_scout.py --query "Backend Developer" --persist
"""

from __future__ import annotations

import argparse
import sys

from job_agent.agents.scout_agent import ScoutAgent
from job_agent.db.client import SupabaseClient
from job_agent.models.job import Job
from job_agent.tools.arbeitsagentur_client import ArbeitsagenturClient
from job_agent.tools.job_normalizer import normalize


def _print_header(text: str) -> None:
    print()
    print("=" * 70)
    print(text)
    print("=" * 70)


def _print_job(job: Job, n: int) -> None:
    desc = (job.description or "").strip()
    print()
    print(f"  [{n}] {job.title}")
    print(f"      Company:      {job.company or '?'}")
    print(f"      Location:     {job.location or '?'}")
    print(f"      External ID:  {job.external_id}")
    print(f"      URL:          {job.url}")
    if job.requirements:
        print(f"      Requirements: {', '.join(job.requirements[:6])}")
    print(f"      Description:  {len(desc)} chars"
          + (f" — {desc[:70]}..." if desc
             else " (list endpoint has no descriptions; use --details)"))


def _dry_run(query: str, location: str | None, page_size: int,
             details: bool) -> int:
    """Fetch + normalise without touching the database."""
    client = ArbeitsagenturClient.with_default_opener()

    print("\n[1/2] Fetching from Arbeitsagentur API (no DB writes)...")
    raw = client.search(keyword=query, location=location, page=1, page_size=page_size)
    raw_list = raw.get("stellenangebote") or []
    print(f"      API returned: {len(raw_list)} listing(s)")

    if not raw_list:
        print("\n      Nothing returned. Try a different --query.", file=sys.stderr)
        return 1

    step2 = "Normalising + fetching details" if details else "Normalising raw listings"
    print(f"\n[2/2] {step2} into typed Job models...")
    jobs: list[Job] = []
    failures = 0
    for raw_job in raw_list:
        try:
            job = normalize("arbeitsagentur", raw_job)
            if details:
                # The list endpoint carries no description — enrich from the
                # per-job detail endpoint, exactly like ScoutAgent's full run.
                try:
                    detail = client.fetch_detail(job.external_id)
                    job = normalize("arbeitsagentur", raw_job, detail=detail)
                except Exception as exc:  # noqa: BLE001 — keep un-enriched job
                    print(f"      detail fetch failed for {job.external_id}: "
                          f"{type(exc).__name__}: {exc}")
            jobs.append(job)
        except Exception as exc:  # noqa: BLE001 — demo surface, show and continue
            failures += 1
            print(f"      normalize failed: {type(exc).__name__}: {exc}")
    print(f"      Normalized: {len(jobs)} | Failed: {failures}")

    for i, job in enumerate(jobs, start=1):
        _print_job(job, i)

    print("\n  (dry run — nothing was written to the database; "
          "pass --persist to upsert)")
    return 0


def _persist_run(query: str, location: str | None, page_size: int) -> int:
    """Full ScoutAgent run: fetch, normalise, enrich with details, upsert."""
    db = SupabaseClient()

    before = db.raw.table("jobs").select("id", count="exact").execute().count or 0
    print(f"\n[1/3] Jobs in database before run: {before}")

    print("\n[2/3] Running ScoutAgent (fetch + normalise + detail-enrich + upsert)...")
    scout = ScoutAgent(client=ArbeitsagenturClient.with_default_opener(), db=db)
    result = scout.run(keyword=query, location=location, page_size=page_size)
    print(f"      Fetched: {result.fetched} | "
          f"Normalized: {result.normalized} | "
          f"Upserted: {result.upserted} | "
          f"Details fetched: {result.details_fetched}")
    if result.errors:
        print(f"      Errors ({len(result.errors)}):")
        for err in result.errors[:5]:
            print(f"        - {err}")

    after = db.raw.table("jobs").select("id", count="exact").execute().count or 0
    print(f"\n[3/3] Jobs in database after run:  {after}")
    print(f"      Genuinely new: {after - before} "
          f"(the other {result.upserted - (after - before)} were dedupe hits "
          f"on (source, external_id))")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--query", default="Python Developer",
                    help="Arbeitsagentur search query (default: 'Python Developer')")
    ap.add_argument("--location", default=None,
                    help="Optional location filter, e.g. 'Essen'")
    ap.add_argument("--page-size", type=int, default=5,
                    help="Number of listings to fetch (default 5)")
    ap.add_argument("--persist", action="store_true",
                    help="Run the real ScoutAgent and upsert to Supabase "
                         "(default: dry run, no DB writes)")
    ap.add_argument("--details", action="store_true",
                    help="Dry run only: also fetch full descriptions from the "
                         "detail endpoint (1 extra API call per job)")
    args = ap.parse_args()

    mode = "PERSIST" if args.persist else "DRY RUN"
    _print_header(
        f"Scout demo [{mode}] — query: {args.query!r}"
        + (f", location: {args.location!r}" if args.location else "")
    )

    if args.persist:
        return _persist_run(args.query, args.location, args.page_size)
    return _dry_run(args.query, args.location, args.page_size, details=args.details)


if __name__ == "__main__":
    raise SystemExit(main())
