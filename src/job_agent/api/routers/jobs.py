"""Jobs endpoint: list the shared job pool (RLS allows authenticated reads)."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends

from job_agent.api.deps import get_user_db
from job_agent.db.client import SupabaseClient

router = APIRouter()


@router.get("/jobs")
def list_jobs(db: SupabaseClient = Depends(get_user_db)) -> list[dict[str, Any]]:
    rows = (
        db.raw.table("jobs")
        .select("id, source, title, company, location, url, scraped_at")
        .order("scraped_at", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )
    return cast("list[dict[str, Any]]", rows)
