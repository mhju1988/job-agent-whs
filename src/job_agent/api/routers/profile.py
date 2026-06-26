"""Profile endpoints: read the user's profile, upload a CV (streamed progress)."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.progress import run_agent_sse
from job_agent.api.schemas import ProfileUpdateRequest
from job_agent.db.client import SupabaseClient
from job_agent.services.profile_service import save_profile_from_pdf, update_profile_fields
from job_agent.tools.observability_store import ObservabilityStore

router = APIRouter()


@router.get("/profile")
def get_profile(db: SupabaseClient = Depends(get_user_db)) -> dict[str, Any]:
    rows = db.raw.table("profile").select("*").limit(1).execute().data or []
    return cast("dict[str, Any]", rows[0]) if rows else {}


@router.patch("/profile")
def patch_profile(
    body: ProfileUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> dict[str, Any]:
    """Apply a partial {skills, summary} edit (re-embeds; no re-score)."""
    result = update_profile_fields(
        db, user.user_id, skills=body.skills, summary=body.summary
    )
    if not result.ok:
        if result.error == "no profile":
            raise HTTPException(
                status_code=404, detail="Upload a CV first to create a profile."
            )
        raise HTTPException(
            status_code=502, detail="Couldn't update embeddings — try again."
        )
    return result.profile or {}


@router.post("/cv")
async def upload_cv(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> EventSourceResponse:
    """Parse → embed → save → re-score, streaming live progress via SSE.

    The file is read here (request-scoped) and the heavy work runs in a worker
    thread inside run_agent_sse, emitting `progress` events (parsing/embedding/
    saving/rescoring + the Matcher's scoring) then a terminal `result`.
    """
    raw = await file.read()

    def work(on_progress: Any, should_stop: Any) -> dict[str, Any]:
        # should_stop is accepted for the run_agent_sse signature but not wired:
        # CV upload's internal parse→embed→save→re-score is out of #9's scope
        # (a follow-up could thread it into save_profile_from_pdf's rescore).
        result = save_profile_from_pdf(
            raw,
            db=db,
            user_id=user.user_id,
            on_progress=on_progress,
            obs=ObservabilityStore(db=db),
        )
        return result.model_dump()

    return run_agent_sse(work)
