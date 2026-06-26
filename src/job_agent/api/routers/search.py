"""AI search-suggestion endpoint: roles to search for, derived from the CV."""

from __future__ import annotations

import logging
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from job_agent.agents.matcher_agent import MatcherAgent
from job_agent.api.deps import get_user_db
from job_agent.db.client import SupabaseClient
from job_agent.tools.search_suggester import SearchSuggester, SearchSuggestion

log = logging.getLogger(__name__)

router = APIRouter()

_SUGGESTION_COLS = (
    "summary, skills, experience, education, languages, suggested_searches"
)


@router.get("/search/suggestions", response_model=list[SearchSuggestion])
def search_suggestions(
    db: SupabaseClient = Depends(get_user_db),
) -> list[SearchSuggestion]:
    """Return AI-proposed job-search queries for the authenticated user.

    Reads from the ``suggested_searches`` cache column written at CV-upload time.
    Falls back to a live LLM call for profiles that predate migration 016 or
    whose cache is otherwise empty.

    No observability run attached — this is a quick helper call, not a tracked
    agent run.
    """
    rows = (
        db.raw.table("profile")
        .select(_SUGGESTION_COLS)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(status_code=400, detail="No profile. Upload a CV first.")

    row = cast("dict[str, Any]", rows[0])

    # --- Cache hit ---
    cached: list[Any] = row.get("suggested_searches") or []
    if cached:
        try:
            return [SearchSuggestion.model_validate(s) for s in cached]
        except (ValidationError, TypeError) as exc:  # noqa: BLE001
            log.warning("corrupt suggested_searches cache, falling back to LLM: %s", exc)

    # --- Fallback: live LLM call ---
    brief = MatcherAgent.build_candidate_text(row)
    if not brief.strip():
        raise HTTPException(status_code=400, detail="No profile. Upload a CV first.")
    return SearchSuggester().suggest(brief)
