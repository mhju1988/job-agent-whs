"""Sprint 5 end-to-end CLI demo.

Pipeline: Scout -> Matcher -> Writer -> Tracker

Pre-conditions:
  - Migrations 001-007 applied.
  - A profile row exists (run scripts/sprint3_e2e.py if missing).
  - GWDG /chat and /embeddings endpoints reachable.

Exit codes:
  0 — success
  1 — unexpected error
  2 — precondition failure (no profile, no jobs after Scout)
"""

from __future__ import annotations

import sys
from typing import Any

from job_agent.agents.base_agent import BaseAgent
from job_agent.agents.matcher_agent import MatcherAgent
from job_agent.agents.scout_agent import ScoutAgent
from job_agent.agents.tracker_agent import InvalidTransitionError, TrackerAgent
from job_agent.agents.writer_agent import WriterAgent
from job_agent.db.client import SupabaseClient
from job_agent.tools.arbeitsagentur_client import ArbeitsagenturClient
from job_agent.tools.cover_letter_template import CoverLetterRenderer

CANDIDATE_NAME = "Max Mustermann"
SCOUT_QUERY = "Java Developer"
SCOUT_LOCATION = "Oberhausen"
SCOUT_PAGE_SIZE = 5
MATCHER_TOP_N = 5
TOP_MATCHES = 3


def _trunc(s: str | None, n: int = 38) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------------------
# Step 1 — Scout
# ---------------------------------------------------------------------------


def step_scout(db: SupabaseClient) -> list[str]:
    """Fetch jobs via ScoutAgent; return list of upserted job_ids."""
    client = ArbeitsagenturClient.with_default_opener()
    agent = ScoutAgent(client=client, db=db)
    result = agent.run(
        keyword=SCOUT_QUERY,
        location=SCOUT_LOCATION,
        page_size=SCOUT_PAGE_SIZE,
    )
    print(
        f"[1/4] Scout: fetched={result.fetched}, "
        f"normalized={result.normalized}, upserted={result.upserted}"
    )
    if result.errors:
        print(f"      ! First error: {result.errors[0]}")

    # Retrieve the most-recently-scraped job_ids to hand to Matcher fallback.
    raw = db.raw
    rows = (
        raw.table("jobs")
        .select("id")
        .order("scraped_at", desc=True)
        .limit(SCOUT_PAGE_SIZE)
        .execute()
    )
    return [r["id"] for r in (rows.data or [])]


# ---------------------------------------------------------------------------
# Step 2 — Matcher
# ---------------------------------------------------------------------------


def step_matcher(
    db: SupabaseClient,
    profile_id: str,
    recent_job_ids: list[str],
) -> dict[str, Any]:
    """Run MatcherAgent; return the rank-1 match_score row."""
    raw = db.raw

    agent = MatcherAgent(db=db, llm_agent=BaseAgent())
    result = agent.run(profile_id=profile_id, top_n=MATCHER_TOP_N)

    if result.scored == 0:
        print(
            "[2/4] Matcher: scored=0 (jobs already matched), "
            "reusing top existing score"
        )
        if result.errors:
            print(f"      ⚠ Matcher errors: {result.errors[:3]}")
    else:
        print(f"[2/4] Matcher: scored={result.scored}, errors={len(result.errors)}")
        if result.errors:
            print(f"      ! First error: {result.errors[0]}")

    # Query top 3 match_scores — scoped to the current Scout's job_ids so the
    # demo surfaces the freshly-fetched run, not stale global top scores.
    top_rows = (
        raw.table("match_scores")
        .select("id, score, job_id, jobs(title, company)")
        .in_("job_id", recent_job_ids)
        .order("score", desc=True)
        .limit(TOP_MATCHES)
        .execute()
    )
    matches: list[dict[str, Any]] = top_rows.data or []

    if not matches:
        print("ERROR: No match_scores found after Scout+Matcher run.", file=sys.stderr)
        sys.exit(2)

    # Print table.
    print(f"\n  {'Rank':<4} | {'Score':>5} | {'Company':<30} | {'Title'}")
    print(f"  {'-'*4}-+-{'-'*5}-+-{'-'*30}-+-{'-'*30}")
    for i, row in enumerate(matches, start=1):
        job_info: dict[str, Any] = row.get("jobs") or {}
        company = _trunc(job_info.get("company"), 30)
        title = _trunc(job_info.get("title"), 30)
        score = int(round(row.get("score") or 0))
        print(f"  {i:<4} | {score:>5} | {company:<30} | {title}")
    print()

    return matches[0]


# ---------------------------------------------------------------------------
# Step 3 — Writer
# ---------------------------------------------------------------------------


def step_writer(
    db: SupabaseClient,
    rank1_match: dict[str, Any],
    profile_id: str,
    profile_skills: list[str],
) -> str:
    """Run WriterAgent for rank-1 match; return application_id.

    Idempotency guard: if an application already exists for this job in a
    post-`ready_to_send` state, skip Writer so we don't clobber `status` /
    `applied_at` via the on_conflict upsert.
    """
    match_score_id: str = rank1_match["id"]
    job_id: str = rank1_match["job_id"]

    existing_resp = (
        db.raw.table("applications")
        .select("id, status")
        .eq("job_id", job_id)
        .limit(1)
        .execute()
    )
    existing = (existing_resp.data or [None])[0]
    if existing and existing.get("status") in {"applied", "interview", "offer", "rejected"}:
        status = existing["status"]
        print(
            f"[3/4] Skipping Writer — application already in status '{status}', "
            "artifacts preserved."
        )
        return str(existing["id"])

    agent = WriterAgent(
        db=db,
        renderer=CoverLetterRenderer(llm_agent=BaseAgent()),
    )
    matched_skills = profile_skills[:4]
    result = agent.run(
        profile_id=profile_id,
        job_id=job_id,
        match_score_id=match_score_id,
        candidate_name=CANDIDATE_NAME,
        matched_skills=matched_skills,
    )

    print(f"[3/4] Writer: application_id={result.application_id}, status={result.status}")
    print(f"      cover_letter={result.cover_letter_path}")
    print(f"      cv_variant  ={result.cv_variant_path}")

    return str(result.application_id)


# ---------------------------------------------------------------------------
# Step 4 — Tracker
# ---------------------------------------------------------------------------


def step_tracker(db: SupabaseClient, application_id: str) -> None:
    """Transition application to 'applied'; print final state."""
    tracker = TrackerAgent(db=db)

    try:
        tracker.transition(application_id, "applied")
    except InvalidTransitionError as exc:
        # Already applied — do not crash.
        print(f"[4/4] Tracker: transition skipped — {exc}")
    else:
        print("[4/4] Tracker: transitioned to 'applied'")

    # Re-query final state.
    raw = db.raw
    row_resp = (
        raw.table("applications")
        .select(
            "id, status, applied_at, job_title, job_company, "
            "cover_letter_path, cv_variant_path"
        )
        .eq("id", application_id)
        .limit(1)
        .execute()
    )
    row: dict[str, Any] = (row_resp.data or [{}])[0]

    print(f"      id              = {row.get('id')}")
    print(f"      status          = {row.get('status')}")
    print(f"      applied_at      = {row.get('applied_at')}")
    print(f"      job_title       = {row.get('job_title')}")
    print(f"      job_company     = {row.get('job_company')}")
    print(f"      cover_letter    = {row.get('cover_letter_path')}")
    print(f"      cv_variant      = {row.get('cv_variant_path')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    try:
        db = SupabaseClient()
        raw = db.raw

        # Pre-condition: profile must exist.
        prof_resp = raw.table("profile").select("id, skills").limit(1).execute()
        if not prof_resp.data:
            print(
                "ERROR: No profile row found. "
                "Run scripts/sprint3_e2e.py first to create a profile.",
                file=sys.stderr,
            )
            return 2
        profile_id: str = prof_resp.data[0]["id"]
        profile_skills: list[str] = prof_resp.data[0].get("skills") or []

        # Step 1 — Scout.
        recent_job_ids = step_scout(db)
        if not recent_job_ids:
            print(
                "ERROR: Scout returned 0 jobs. Check Arbeitsagentur API connectivity.",
                file=sys.stderr,
            )
            return 2

        # Step 2 — Matcher.
        rank1_match = step_matcher(db, profile_id, recent_job_ids)

        # Step 3 — Writer.
        application_id = step_writer(db, rank1_match, profile_id, profile_skills)

        # Step 4 — Tracker.
        step_tracker(db, application_id)

        # Final summary — re-query the actual status (don't hardcode "applied",
        # since step_tracker may have skipped the transition on an already-final row).
        final_resp = (
            raw.table("applications")
            .select("status")
            .eq("id", application_id)
            .limit(1)
            .execute()
        )
        final_status = (final_resp.data or [{}])[0].get("status", "unknown")

        print()
        print("============================================")
        print("Sprint 5 demo complete.")
        print("Pipeline: Scout -> Matcher -> Writer -> Tracker")
        print(f"Final application status: {final_status}")
        print(f"Application id: {application_id}")
        print("============================================")

    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
