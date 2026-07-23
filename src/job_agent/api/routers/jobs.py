"""Jobs endpoints: list the shared pool (minus hidden) + per-user hide/unhide."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends

from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.schemas import HideJobsRequest
from job_agent.db.client import SupabaseClient
from job_agent.services.hidden_jobs import fetch_hidden_job_ids

router = APIRouter()


@router.get("/jobs")
def list_jobs(db: SupabaseClient = Depends(get_user_db)) -> list[dict[str, Any]]:
    hidden = fetch_hidden_job_ids(db)
    rows = cast(
        "list[dict[str, Any]]",
        db.raw.table("jobs")
        .select("id, source, title, company, location, url, scraped_at")
        .order("scraped_at", desc=True)
        .limit(100)
        .execute()
        .data
        or [],
    )
    return [r for r in rows if str(r["id"]) not in hidden]


@router.get("/jobs/hidden")
def list_hidden_jobs(db: SupabaseClient = Depends(get_user_db)) -> list[dict[str, Any]]:
    """Return the caller's hidden jobs (job fields + ``hidden_at``), newest first.

    RLS scopes ``hidden_jobs`` to the caller; the embedded ``jobs`` join is
    flattened so each row matches the ``/jobs`` shape plus ``hidden_at``.
    """
    rows = cast(
        "list[dict[str, Any]]",
        db.raw.table("hidden_jobs")
        .select("hidden_at, jobs(id, source, title, company, location, url, scraped_at)")
        .order("hidden_at", desc=True)
        .execute()
        .data
        or [],
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        job = cast("dict[str, Any] | None", r.get("jobs"))
        if job:
            out.append({**job, "hidden_at": r.get("hidden_at")})
    return out


@router.post("/jobs/hide")
def hide_jobs(
    body: HideJobsRequest,
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> dict[str, int]:
    if not body.job_ids:
        return {"hidden": 0}
    rows = [{"user_id": user.user_id, "job_id": jid} for jid in body.job_ids]
    db.raw.table("hidden_jobs").upsert(
        rows, on_conflict="user_id,job_id", ignore_duplicates=True
    ).execute()
    return {"hidden": len(body.job_ids)}


@router.post("/jobs/unhide")
def unhide_jobs(
    body: HideJobsRequest,
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> dict[str, int]:
    if not body.job_ids:
        return {"unhidden": 0}
    db.raw.table("hidden_jobs").delete().eq("user_id", user.user_id).in_(
        "job_id", body.job_ids
    ).execute()
    return {"unhidden": len(body.job_ids)}
