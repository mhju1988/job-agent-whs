"""Sprint 4 Writer smoke — generate cover letter + CV variant for the
top-ranked job (ACONEXT) from the Sprint 3 e2e. File output only, no DB write.
"""

from __future__ import annotations

import sys
from pathlib import Path

from job_agent.agents.base_agent import BaseAgent
from job_agent.db.client import SupabaseClient
from job_agent.models.job import Job
from job_agent.models.match import MatchResult
from job_agent.models.profile import Education, Experience, Profile
from job_agent.tools.cover_letter_template import CoverLetterRenderer
from job_agent.tools.cv_variant import build_cv_variant
from job_agent.tools.docx_exporter import export_cover_letter, export_cv_variant, make_slug

ARTIFACTS = Path("artifacts")
CANDIDATE_NAME = "Max Mustermann"


def main() -> int:
    raw = SupabaseClient().raw

    # 1. Fetch the single profile row.
    prof_resp = raw.table("profile").select("*").limit(1).execute()
    if not prof_resp.data:
        print("ERROR: no profile in DB. Run scripts/sprint3_e2e.py first.", file=sys.stderr)
        return 2
    p = prof_resp.data[0]
    profile = Profile(
        summary=p.get("summary"),
        skills=p.get("skills") or [],
        highlighted_skills=p.get("highlighted_skills") or [],
        experience=[Experience.model_validate(e) for e in (p.get("experience") or [])],
        education=[Education.model_validate(e) for e in (p.get("education") or [])],
        languages=p.get("languages") or [],
    )

    # 2. Find the top-ranked job: ACONEXT.
    job_resp = (
        raw.table("jobs")
        .select(
            "id, source, external_id, url, title, company, location,"
            " requirements, description, scraped_at"
        )
        .ilike("company", "%ACONEXT%")
        .limit(1)
        .execute()
    )
    if not job_resp.data:
        print("ERROR: ACONEXT job not in DB. Run scripts/sprint3_e2e.py first.", file=sys.stderr)
        return 2
    job_row = dict(job_resp.data[0])
    job_db_id: str = job_row.pop("id")
    job = Job.model_validate(job_row)

    # 3. Look up its match_score row.
    match_resp = (
        raw.table("match_scores")
        .select("score, gaps, rationale")
        .eq("job_id", job_db_id)
        .limit(1)
        .execute()
    )
    if not match_resp.data:
        print(f"ERROR: no match_score for job {job.title!r}", file=sys.stderr)
        return 2
    m = match_resp.data[0]
    # matched_skills isn't persisted — proxy as top 4 profile skills (all matched at score 90).
    matched_skills = profile.skills[:4]
    match = MatchResult(
        score=int(m["score"]),
        matched_skills=matched_skills,
        gaps=list(m.get("gaps") or []),
        rationale=str(m.get("rationale") or ""),
    )

    print(f"[1/4] Loaded profile + job ({job.company}) + match (score={match.score})")

    # 4. Build CV variant (no LLM).
    variant = build_cv_variant(profile, match)
    print(f"[2/4] CV variant built — highlighted={variant.highlighted_skills}")

    # 5. Render cover letter via real GWDG LLM.
    print("[3/4] Rendering cover letter via GWDG LLM...")
    renderer = CoverLetterRenderer(llm_agent=BaseAgent())
    letter_text = renderer.render(
        candidate_name=CANDIDATE_NAME,
        profile=variant,
        job=job,
        matched_skills=matched_skills,
        gaps_addressed=match.gaps,
    )

    # 6. Export both .docx (no DB write).
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    company_slug = make_slug(job.company or "company", fallback="company")
    title_slug = make_slug(job.title or "job", fallback="job")
    slug = f"{company_slug}_{title_slug}"
    cover_path = export_cover_letter(letter_text, ARTIFACTS / f"cover_letter_{slug}.docx")
    cv_path = export_cv_variant(variant, ARTIFACTS / f"cv_{slug}.docx")

    print("[4/4] Artifacts written:")
    print(f"      {cover_path}")
    print(f"      {cv_path}")

    # First sentence of the body (best-effort split on first '.').
    body_marker = "Subject:"
    after_subject = letter_text.split(body_marker, 1)[-1]
    paragraphs = [p.strip() for p in after_subject.split("\n\n") if p.strip()]
    body_para = next((p for p in paragraphs[1:] if not p.startswith("Relevant")), "")
    first_sentence = body_para.split(".", 1)[0].strip() + "." if body_para else "(no body found)"
    print(f"\nFirst sentence of cover letter body:\n  {first_sentence}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
