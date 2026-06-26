"""GDPR data-deletion endpoint: wipe the authenticated user's data."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from job_agent.agents.tracker_agent import TrackerAgent
from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.schemas import DeleteSummaryResponse
from job_agent.db.client import SupabaseClient

router = APIRouter()


@router.post("/data/delete", response_model=DeleteSummaryResponse)
def delete_my_data(
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> DeleteSummaryResponse:
    summary = TrackerAgent(db=db).delete_my_data(user_id=user.user_id)
    return DeleteSummaryResponse(**summary.model_dump())
