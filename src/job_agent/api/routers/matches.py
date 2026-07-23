"""Matches endpoints: the user's scored jobs, score-filtered (RLS-scoped).

The graph endpoint re-runs the stage-1 cosine RPC live (with
``exclude_scored=False``) and joins it with the persisted stage-2 LLM
``match_scores``, so a single payload carries both scoring stages for the
front-end's two-canvas fit graph.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Query

from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.db.client import SupabaseClient
from job_agent.services.hidden_jobs import fetch_hidden_job_ids
from job_agent.services.match_query import filter_matches

router = APIRouter()

# Graceful per-user ceiling, far above any realistic count (the shared jobs pool
# is ~100 with a 90-day purge). If ever hit, score-desc keeps the strongest.
MAX_MATCHES = 500


@router.get("/matches")
def list_matches(
    min_score: int = Query(0, ge=0, le=100),
    db: SupabaseClient = Depends(get_user_db),
) -> list[dict[str, Any]]:
    hidden = fetch_hidden_job_ids(db)
    rows = cast(
        "list[dict[str, Any]]",
        db.raw.table("match_scores")
        .select(
            "id, job_id, score, matched_skills, gaps, rationale, created_at, "
            "jobs(title, company, applications(id, status, cover_letter_path))"
        )
        .order("score", desc=True)
        .limit(MAX_MATCHES)
        .execute()
        .data
        or [],
    )
    visible = [r for r in rows if str(r["job_id"]) not in hidden]
    return filter_matches(visible, min_score)


# Fit-graph node cap — deliberately small for readability, independent of the
# /matches list cap (MAX_MATCHES).
_GRAPH_TOP_N = 50


@router.get("/matches/graph")
def get_match_graph(
    db: SupabaseClient = Depends(get_user_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return both scoring stages for the fit graph.

    The two stages are fetched independently so neither gates the other:

    * **Stage 2 (LLM ``score`` + gap analysis)** comes from the persisted
      ``match_scores`` rows joined to ``jobs`` — the reliable source, since
      every scored job has a row here regardless of how it was scored.
    * **Stage 1 (cosine ``similarity``)** comes from re-running the live
      ``match_jobs_for_profile`` RPC with ``exclude_scored=False``. The RPC
      needs both a profile embedding and jobs *with* embeddings; jobs scored
      via the manual "score these" path (or any job lacking an embedding) have
      no cosine value, so ``similarity`` is nullable and jobs without it are
      simply dropped from the Stage-1 canvas.

    ``profile.skills`` decorates the centre node in the UI.
    """
    # Centre node: the caller's single profile (RLS-scoped to them).
    profile_rows = (
        db.raw.table("profile").select("id, skills").limit(1).execute().data or []
    )
    if not profile_rows:
        return {"profile": None, "jobs": []}
    profile = cast("dict[str, Any]", profile_rows[0])
    profile_id = profile["id"]
    hidden = fetch_hidden_job_ids(db)

    # Stage 2 — the persisted LLM scores joined to job titles/companies. This is
    # the union of jobs we surface, so a missing Stage-1 value never hides a job.
    score_rows = cast(
        "list[dict[str, Any]]",
        db.raw.table("match_scores")
        .select(
            "job_id, score, matched_skills, gaps, rationale, "
            "jobs(title, company, requirements, description)"
        )
        .eq("user_id", user.user_id)
        .order("score", desc=True)
        .limit(_GRAPH_TOP_N)
        .execute().data
        or [],
    )

    # Stage 1 — live cosine similarities (best-effort; may be empty if jobs lack
    # embeddings). Build a job_id → similarity lookup to attach later.
    rpc_rows = cast(
        "list[dict[str, Any]]",
        db.raw.rpc(
            "match_jobs_for_profile",
            {
                "profile_id": profile_id,
                "p_user_id": user.user_id,
                "top_n": _GRAPH_TOP_N,
                "exclude_scored": False,
            },
        ).execute().data
        or [],
    )
    similarities = {
        str(r["job_id"]): float(r.get("similarity") or 0.0) for r in rpc_rows
    }

    jobs: list[dict[str, Any]] = []
    for r in score_rows:
        job_id = str(r["job_id"])
        if job_id in hidden:
            continue
        joined = cast("dict[str, Any] | None", r.get("jobs"))
        jobs.append(
            {
                "job_id": job_id,
                "title": (joined or {}).get("title") or "",
                "company": (joined or {}).get("company"),
                "requirements": (joined or {}).get("requirements") or [],
                "description": (joined or {}).get("description"),
                # None when the RPC had no cosine value for this job.
                "similarity": similarities.get(job_id),
                "score": float(r["score"]) if r.get("score") is not None else None,
                "matched_skills": r.get("matched_skills") or [],
                "gaps": r.get("gaps") or [],
                "rationale": r.get("rationale"),
            }
        )

    return {"profile": {"skills": profile.get("skills") or []}, "jobs": jobs}
