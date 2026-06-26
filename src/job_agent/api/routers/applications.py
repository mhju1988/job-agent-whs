"""Applications endpoints: list, status transition, document download (RLS-scoped)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from job_agent.agents.tracker_agent import InvalidTransitionError, TrackerAgent
from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.schemas import TransitionRequest
from job_agent.config import get_settings
from job_agent.db.client import SupabaseClient

router = APIRouter()


@router.get("/applications")
def list_applications(db: SupabaseClient = Depends(get_user_db)) -> list[dict[str, Any]]:
    rows = (
        db.raw.table("applications")
        .select(
            "id, job_id, job_title, job_company, status, cover_letter_path, "
            "cv_variant_path, follow_up_at, applied_at"
        )
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    return cast("list[dict[str, Any]]", rows)


@router.post("/applications/{application_id}/transition")
def transition(
    application_id: str,
    body: TransitionRequest,
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> dict[str, str]:
    tracker = TrackerAgent(db=db)
    try:
        tracker.transition(application_id, body.target, user_id=user.user_id)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": body.target}


@router.get("/applications/{application_id}/documents/{kind}")
def download_document(
    application_id: str,
    kind: str,
    db: SupabaseClient = Depends(get_user_db),
) -> FileResponse:
    col = {"cover": "cover_letter_path", "cv": "cv_variant_path"}.get(kind)
    if col is None:
        raise HTTPException(status_code=400, detail="kind must be 'cover' or 'cv'")
    rows = (
        db.raw.table("applications")
        .select(col)
        .eq("id", application_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    path = cast("dict[str, Any]", rows[0]).get(col) if rows else None
    if not path:
        raise HTTPException(status_code=404, detail="Document not found")
    # Resolve and validate the path stays within the configured artifacts directory.
    artifact_root = get_settings().artifacts_dir.resolve()
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(artifact_root):
        raise HTTPException(status_code=403, detail="Document path not allowed")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(str(resolved), filename=resolved.name)
