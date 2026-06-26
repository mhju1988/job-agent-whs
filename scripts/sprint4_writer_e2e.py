"""Sprint 4 Writer full e2e — same as the smoke, but goes through WriterAgent
so the `applications` row is upserted to Supabase with status='ready_to_send'.

Pre-conditions: migrations 001–007 applied (esp. 006 for the new status value
and 007 for the unique constraint on applications.job_id).
"""

from __future__ import annotations

import sys

from job_agent.agents.base_agent import BaseAgent
from job_agent.agents.writer_agent import WriterAgent
from job_agent.db.client import SupabaseClient
from job_agent.tools.cover_letter_template import CoverLetterRenderer

CANDIDATE_NAME = "Max Mustermann"


def main() -> int:
    db = SupabaseClient()
    raw = db.raw

    # 1. Profile id.
    prof = raw.table("profile").select("id, skills").limit(1).execute()
    if not prof.data:
        print("ERROR: no profile row. Run scripts/sprint3_e2e.py first.", file=sys.stderr)
        return 2
    profile_id = prof.data[0]["id"]
    profile_skills = prof.data[0]["skills"] or []

    # 2. Find the top-ranked ACONEXT job.
    jobs = (
        raw.table("jobs")
        .select("id, title, company")
        .ilike("company", "%ACONEXT%")
        .limit(1)
        .execute()
    )
    if not jobs.data:
        print("ERROR: no ACONEXT job. Run scripts/sprint3_e2e.py first.", file=sys.stderr)
        return 2
    job_id = jobs.data[0]["id"]
    job_title = jobs.data[0]["title"]
    job_company = jobs.data[0]["company"]

    # 3. Find its match_score row.
    match = (
        raw.table("match_scores")
        .select("id, score")
        .eq("job_id", job_id)
        .limit(1)
        .execute()
    )
    if not match.data:
        print(
            "ERROR: no match_score for ACONEXT. Run scripts/sprint3_e2e.py first.",
            file=sys.stderr,
        )
        return 2
    match_score_id = match.data[0]["id"]
    score = match.data[0]["score"]

    print(
        f"[1/2] Loaded profile={profile_id[:8]}… "
        f"job={job_company!r} ({job_title!r}, score={score})"
    )

    # 4. Run the WriterAgent — this is the deliverable: produce both .docx AND
    # upsert the applications row with status='ready_to_send'.
    agent = WriterAgent(
        db=db,
        renderer=CoverLetterRenderer(llm_agent=BaseAgent()),
    )
    matched = profile_skills[:4]
    result = agent.run(
        profile_id=profile_id,
        job_id=job_id,
        match_score_id=match_score_id,
        candidate_name=CANDIDATE_NAME,
        matched_skills=matched,
    )

    print("[2/2] WriterAgent.run complete:")
    print(f"      application_id={result.application_id}")
    print(f"      status={result.status}")
    print(f"      cover_letter={result.cover_letter_path}")
    print(f"      cv_variant  ={result.cv_variant_path}")

    # 5. Verify with a fresh query.
    check = (
        raw.table("applications")
        .select("id, status, job_title, job_company, cover_letter_path, cv_variant_path")
        .eq("id", result.application_id)
        .limit(1)
        .execute()
    )
    if not check.data:
        print("WARN: upsert claimed success but row not found on re-read.", file=sys.stderr)
        return 1
    row = check.data[0]
    print("\nApplications row verified:")
    print(f"  status      = {row['status']}")
    print(f"  job_title   = {row['job_title']}")
    print(f"  job_company = {row['job_company']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
