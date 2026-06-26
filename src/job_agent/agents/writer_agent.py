"""Writer Agent: generates cover letter + CV variant docx and persists application row."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from job_agent.tools.observability_store import ObservabilityStore

from pydantic import BaseModel, ConfigDict

from job_agent.db.client import SupabaseClient
from job_agent.models.job import Job
from job_agent.models.match import MatchResult
from job_agent.models.profile import Education, Experience, Profile
from job_agent.tools.cover_letter_template import CoverLetterRenderer
from job_agent.tools.cv_variant import build_cv_variant
from job_agent.tools.docx_exporter import (
    export_cover_letter,
    export_cv_variant,
    make_slug,
)
from job_agent.tools.run_context import ProgressCb
from job_agent.tools.run_context import emit_progress as _emit


class WriterResult(BaseModel):
    """Returned by WriterAgent.run() after generating documents and upserting the application."""

    model_config = ConfigDict(extra="forbid")

    application_id: str
    cover_letter_path: str
    cv_variant_path: str
    status: Literal["ready_to_send"]


class WriterAgent:
    """Generates cover letter + CV variant .docx files and persists an applications row.

    All collaborators are DI seams:
    - ``db``           — SupabaseClient (or mock)
    - ``renderer``     — CoverLetterRenderer (or mock)
    - ``artifacts_dir``— directory for output files; defaults to Settings.artifacts_dir
    """

    def __init__(
        self,
        db: SupabaseClient | None = None,
        renderer: CoverLetterRenderer | None = None,
        artifacts_dir: Path | None = None,
        obs: ObservabilityStore | None = None,
    ) -> None:
        self._db: SupabaseClient = db if db is not None else SupabaseClient()
        self._obs = obs
        if renderer is not None:
            self._renderer = renderer
        else:
            from job_agent.agents.base_agent import BaseAgent

            self._renderer = CoverLetterRenderer(llm_agent=BaseAgent(obs=obs))
        if artifacts_dir is not None:
            self._artifacts_dir = artifacts_dir
        else:
            from job_agent.config import get_settings

            self._artifacts_dir = get_settings().artifacts_dir

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_profile(db: SupabaseClient, profile_id: str) -> Profile:
        resp = (
            db.raw.table("profile")
            .select("*")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            raise LookupError(f"No profile found with id={profile_id!r}")
        row: dict[str, Any] = cast("dict[str, Any]", resp.data[0])

        # Coerce nested JSONB back to typed sub-models
        experience = [
            Experience.model_validate(e) for e in (row.get("experience") or [])
        ]
        education = [
            Education.model_validate(e) for e in (row.get("education") or [])
        ]
        return Profile(
            summary=row.get("summary"),
            skills=row.get("skills") or [],
            highlighted_skills=row.get("highlighted_skills") or [],
            experience=experience,
            education=education,
            languages=row.get("languages") or [],
        )

    @staticmethod
    def _load_job(db: SupabaseClient, job_id: str) -> Job:
        resp = (
            db.raw.table("jobs")
            .select(
                "source, external_id, url, title, company, location,"
                " requirements, description, scraped_at"
            )
            .eq("id", job_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            raise LookupError(f"No job found with id={job_id!r}")
        return Job.model_validate(cast("dict[str, Any]", resp.data[0]))

    @staticmethod
    def _load_match(db: SupabaseClient, match_score_id: str, job_id: str) -> MatchResult:
        resp = (
            db.raw.table("match_scores")
            .select("score, matched_skills, gaps, rationale")
            .eq("id", match_score_id)
            .eq("job_id", job_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            raise LookupError(
                f"No match_score {match_score_id!r} for job {job_id!r} — "
                "match_score_id and job_id must belong to the same row"
            )
        row: dict[str, Any] = cast("dict[str, Any]", resp.data[0])
        return MatchResult(
            score=int(row["score"]),
            # `matched_skills` column added in migration 008; pre-migration
            # rows are NULL — callers may also pass a fresh list via run().
            matched_skills=list(row.get("matched_skills") or []),
            gaps=list(row.get("gaps") or []),
            rationale=str(row.get("rationale") or ""),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _do_run(
        self,
        *,
        profile_id: str,
        job_id: str,
        match_score_id: str,
        candidate_name: str,
        matched_skills: list[str],
        user_id: str,
        on_progress: ProgressCb | None = None,
    ) -> WriterResult:
        """Generate documents and upsert the application row.

        Parameters
        ----------
        profile_id:      UUID of the profile row.
        job_id:          UUID of the job row.
        match_score_id:  UUID of the match_scores row.
        candidate_name:  Display name for the cover letter.
        matched_skills:  Skills matched by the LLM (not persisted in DB; caller supplies).
        user_id:         Owner of the application row (multi-tenancy scope).
        """
        _emit(on_progress, stage="loading")
        profile = self._load_profile(self._db, profile_id)
        job = self._load_job(self._db, job_id)
        match = self._load_match(self._db, match_score_id, job_id)

        # Use DB-stored matched_skills; fall back to caller's value only for
        # pre-migration rows where the column is empty (migration 008).
        effective_skills = match.matched_skills if match.matched_skills else matched_skills
        match = MatchResult(
            score=match.score,
            matched_skills=effective_skills,
            gaps=match.gaps,
            rationale=match.rationale,
        )

        # Build CV variant with highlighted skills
        variant_profile = build_cv_variant(profile, match)

        # Generate cover letter text
        _emit(on_progress, stage="rendering")
        letter_text = self._renderer.render(
            candidate_name=candidate_name,
            profile=variant_profile,
            job=job,
            matched_skills=effective_skills,
            gaps_addressed=match.gaps,
        )

        # Build file paths — namespace by user to prevent cross-user filename collision
        company_slug = make_slug(job.company or "company", fallback="company")
        title_slug = make_slug(job.title or "job", fallback="job")
        user_prefix = user_id.replace("-", "")[:8]
        file_slug = f"{user_prefix}_{company_slug}_{title_slug}"

        self._artifacts_dir.mkdir(parents=True, exist_ok=True)
        cover_path = self._artifacts_dir / f"cover_letter_{file_slug}.docx"
        cv_path = self._artifacts_dir / f"cv_{file_slug}.docx"

        # Export documents
        _emit(on_progress, stage="exporting")
        cover_path = export_cover_letter(letter_text, cover_path)
        cv_path = export_cv_variant(variant_profile, cv_path)

        # Upsert into applications table. Conflict key is (user_id, job_id) so
        # two users can independently apply to the same job (migration 011).
        upsert_row: dict[str, Any] = {
            "user_id": user_id,
            "job_id": job_id,
            "job_title": job.title,
            "job_company": job.company,
            "job_url": job.url,
            "job_source": job.source,
            "cover_letter_path": str(cover_path),
            "cv_variant_path": str(cv_path),
            "status": "ready_to_send",
        }
        upsert_resp = (
            self._db.raw.table("applications")
            .upsert(upsert_row, on_conflict="user_id,job_id")
            .execute()
        )

        upsert_data = cast("dict[str, Any]", upsert_resp.data[0])
        application_id: str = str(upsert_data["id"])

        _emit(on_progress, stage="done", application_id=application_id)
        return WriterResult(
            application_id=application_id,
            cover_letter_path=str(cover_path),
            cv_variant_path=str(cv_path),
            status="ready_to_send",
        )

    def run(
        self,
        *,
        profile_id: str,
        job_id: str,
        match_score_id: str,
        candidate_name: str,
        matched_skills: list[str],
        user_id: str,
        on_progress: ProgressCb | None = None,
    ) -> WriterResult:
        """Run writer with observability instrumentation."""
        from job_agent.tools.run_context import start_run

        ctx = start_run("writer")
        if self._obs:
            self._obs.insert_run(ctx, user_id=user_id)
        try:
            result = self._do_run(
                profile_id=profile_id,
                job_id=job_id,
                match_score_id=match_score_id,
                candidate_name=candidate_name,
                matched_skills=matched_skills,
                user_id=user_id,
                on_progress=on_progress,
            )
            if self._obs:
                self._obs.finish_run(ctx.run_id, "success")
            return result
        except Exception as exc:
            if self._obs:
                self._obs.finish_run(ctx.run_id, "error", str(exc)[:500])
            raise
