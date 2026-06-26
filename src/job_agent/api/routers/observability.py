"""Observability endpoints: agent-run history and per-run LLM events."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from job_agent.api.deps import get_user_db
from job_agent.db.client import SupabaseClient
from job_agent.tools.observability_store import ObservabilityStore

router = APIRouter()


@router.get("/observability/runs")
def runs(db: SupabaseClient = Depends(get_user_db)) -> list[dict[str, Any]]:
    return ObservabilityStore(db=db).fetch_runs(limit=200)


@router.get("/observability/runs/{run_id}/events")
def run_events(
    run_id: str, db: SupabaseClient = Depends(get_user_db)
) -> list[dict[str, Any]]:
    return ObservabilityStore(db=db).fetch_events_for_run(run_id)
