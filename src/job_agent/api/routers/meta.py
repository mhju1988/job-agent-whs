"""Meta endpoints: health check and the authenticated-user summary."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends

from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.schemas import HealthResponse, MeResponse
from job_agent.config import get_settings
from job_agent.db.client import SupabaseClient

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


def _scout_sources() -> list[str]:
    """Sources with credentials configured (mirrors ui.app._available_scout_sources)."""
    sources = ["arbeitsagentur"]
    if get_settings().rapidapi_key:
        sources.append("jsearch")
    return sources


@router.get("/me", response_model=MeResponse)
def me(
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> MeResponse:
    rows = db.raw.table("profile").select("full_name, skills").limit(1).execute().data or []
    has_profile = bool(rows)
    if rows:
        row = cast("dict[str, Any]", rows[0])
        label = f"{row.get('full_name') or 'Unnamed'} · {len(row.get('skills') or [])} skills"
    else:
        label = "No profile uploaded yet"
    return MeResponse(
        user_id=user.user_id,
        profile_label=label,
        has_profile=has_profile,
        scout_sources=_scout_sources(),
    )
