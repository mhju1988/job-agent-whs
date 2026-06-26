"""User-scoped CV/profile persistence — Streamlit-free, reusable by API + tests.

Ports the persistence half of the old Streamlit ``handle_cv_upload``: parse PDF →
embed → replace *this user's* profile row → optionally trigger a rescore. UI
feedback (st.success/st.error) is NOT here; callers translate the typed result.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from job_agent.db.client import SupabaseClient
from job_agent.models.profile import Profile
from job_agent.tools.cv_parser import CVParseError, CVParser
from job_agent.tools.embedder import Embedder, EmbeddingServiceError
from job_agent.tools.observability_store import ObservabilityStore
from job_agent.tools.run_context import ProgressCb
from job_agent.tools.run_context import emit_progress as _emit
from job_agent.tools.search_suggester import SearchSuggester

log = logging.getLogger(__name__)


class ProfileSaveResult(BaseModel):
    """Outcome of :func:`save_profile_from_pdf`."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    error: str | None = None
    rescored: int | None = None


def save_profile_from_pdf(
    raw_bytes: bytes,
    *,
    db: SupabaseClient,
    user_id: str,
    parser: CVParser | None = None,
    embedder: Embedder | None = None,
    rescore: bool = True,
    on_progress: ProgressCb | None = None,
    obs: ObservabilityStore | None = None,
    suggest: bool = True,
) -> ProfileSaveResult:
    """Parse + embed + persist the user's profile. Returns a typed result.

    Replaces only *this user's* profile row (single profile per user, enforced by
    the migration-011 unique constraint). When ``rescore`` is True the caller's
    stale ``match_scores`` are cleared and the Matcher is re-run against the new
    profile embedding. ``on_progress`` (optional) receives per-stage dicts for the
    API's live SSE stream: parsing → embedding → saving → rescoring (+ the
    Matcher's own scoring events).
    """
    parser = parser or CVParser()
    embedder = embedder or Embedder()
    try:
        _emit(on_progress, stage="parsing")
        profile = parser.parse_bytes(raw_bytes)
        _emit(on_progress, stage="embedding")
        vector = embedder.embed_text(profile.to_embedding_text())
    except CVParseError as exc:
        return ProfileSaveResult(ok=False, error=f"CV parse failed: {exc}")
    except EmbeddingServiceError as exc:
        return ProfileSaveResult(ok=False, error=f"Embedding failed: {exc}")

    row = profile.to_supabase_row()
    row["embedding"] = vector
    row["user_id"] = user_id

    # Replace this user's single profile row (delete-then-insert; the PK is
    # server-generated so an upsert on id would always insert).
    _emit(on_progress, stage="saving")
    db.raw.table("profile").delete().eq("user_id", user_id).execute()
    db.raw.table("profile").insert(row).execute()

    # Generate and cache search suggestions (best-effort — must not fail the upload).
    if suggest:
        _emit(on_progress, stage="suggesting", message="Generating search suggestions…")
        from job_agent.agents.matcher_agent import MatcherAgent  # noqa: PLC0415

        try:
            brief = MatcherAgent.build_candidate_text(profile.to_supabase_row())
            suggestions = SearchSuggester().suggest(brief)
            if suggestions:
                suggestions_json = [
                    s.model_dump(exclude_none=True) for s in suggestions
                ]
                db.raw.table("profile").update(
                    {"suggested_searches": suggestions_json}
                ).eq("user_id", user_id).execute()
        except Exception:  # noqa: BLE001 — suggestions are best-effort
            log.warning("search-suggestion generation failed (non-fatal)", exc_info=True)

    rescored: int | None = None
    if rescore:
        from job_agent.agents.matcher_agent import MatcherAgent

        prof = (
            db.raw.table("profile")
            .select("id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        prof_rows = cast("list[dict[str, Any]]", prof.data or [])
        profile_id = str(prof_rows[0]["id"]) if prof_rows else None
        if profile_id:
            _emit(on_progress, stage="rescoring")
            db.raw.table("match_scores").delete().eq("user_id", user_id).execute()
            result = MatcherAgent(db=db, obs=obs).run(
                profile_id=profile_id, user_id=user_id, on_progress=on_progress
            )
            rescored = result.scored

    return ProfileSaveResult(ok=True, rescored=rescored)


_PROFILE_BRIEF_COLS = "summary, skills, experience, education, languages"


def load_candidate_brief(db: SupabaseClient) -> str | None:
    """Return a compact candidate brief from the user's profile, or None if missing.

    Single source of truth for the profile query used by the search-suggestion
    endpoint and the AI-determined scout keyword path. Callers that need to
    raise an HTTP 400 on a missing profile should check for None themselves.
    """
    from job_agent.agents.matcher_agent import MatcherAgent

    rows = (
        db.raw.table("profile")
        .select(_PROFILE_BRIEF_COLS)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    return MatcherAgent.build_candidate_text(cast("dict[str, Any]", rows[0]))


class ProfileUpdateResult(BaseModel):
    """Outcome of :func:`update_profile_fields`."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    error: str | None = None
    profile: dict[str, Any] | None = None


def update_profile_fields(
    db: SupabaseClient,
    user_id: str,
    *,
    skills: list[str] | None = None,
    summary: str | None = None,
    embedder: Embedder | None = None,
) -> ProfileUpdateResult:
    """Apply a partial {skills, summary} edit, re-embed, and persist.

    Embed-before-save: re-embeds the updated profile text and writes the row only
    if embedding succeeds (same failure semantics as save_profile_from_pdf). Returns
    ``ok=False`` with ``error="no profile"`` if the user has no profile row.
    """
    embedder = embedder or Embedder()

    rows = (
        db.raw.table("profile")
        .select("full_name, summary, skills, experience, education, languages")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return ProfileUpdateResult(ok=False, error="no profile")

    current = cast("dict[str, Any]", rows[0])
    profile = Profile(
        full_name=current.get("full_name"),
        summary=current.get("summary"),
        skills=current.get("skills") or [],
        experience=current.get("experience") or [],
        education=current.get("education") or [],
        languages=current.get("languages") or [],
    )
    if skills is not None:
        profile.skills = skills
    if summary is not None:
        profile.summary = summary

    try:
        vector = embedder.embed_text(profile.to_embedding_text())
    except EmbeddingServiceError as exc:
        return ProfileUpdateResult(ok=False, error=f"embedding failed: {exc}")

    payload: dict[str, Any] = {"embedding": vector}
    if skills is not None:
        payload["skills"] = profile.skills
    if summary is not None:
        payload["summary"] = profile.summary
    db.raw.table("profile").update(payload).eq("user_id", user_id).execute()

    return ProfileUpdateResult(ok=True, profile=profile.to_supabase_row())
