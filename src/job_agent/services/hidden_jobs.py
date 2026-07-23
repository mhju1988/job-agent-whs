"""Shared helper: the caller's hidden job ids (RLS-scoped)."""

from __future__ import annotations

from typing import Any, cast

from job_agent.db.client import SupabaseClient


def fetch_hidden_job_ids(db: SupabaseClient) -> set[str]:
    """Return the set of job ids the current user has hidden.

    RLS on ``hidden_jobs`` scopes the rows to the caller, so no explicit
    ``user_id`` filter is required.
    """
    rows = cast(
        "list[dict[str, Any]]",
        db.raw.table("hidden_jobs").select("job_id").execute().data or [],
    )
    return {str(r["job_id"]) for r in rows}
