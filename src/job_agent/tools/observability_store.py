"""Supabase I/O for the observability layer."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, cast

from job_agent.db.client import SupabaseClient
from job_agent.tools.run_context import RunContext

log = logging.getLogger(__name__)

# Reference: Llama-3.3-70B on Groq (closest public proxy for GWDG cost)
_PROMPT_EUR_PER_TOKEN = 0.0006 / 1000
_COMPLETION_EUR_PER_TOKEN = 0.0009 / 1000


class ObservabilityStore:
    """Writes and reads agent_runs and llm_events tables."""

    def __init__(self, db: SupabaseClient | None = None) -> None:
        self._db = db if db is not None else SupabaseClient()

    def insert_run(self, ctx: RunContext, user_id: str | None = None) -> None:
        row: dict[str, Any] = {
            "run_id": ctx.run_id,
            "agent_name": ctx.agent_name,
            "started_at": ctx.started_at.isoformat(),
            "status": "running",
        }
        if user_id is not None:
            row["user_id"] = user_id
        try:
            self._db.raw.table("agent_runs").insert(row).execute()
        except Exception as exc:  # noqa: BLE001
            log.warning("observability insert_run failed (migration pending?): %s", exc)

    def finish_run(
        self,
        run_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        try:
            self._db.raw.table("agent_runs").update(
                {
                    "status": status,
                    "finished_at": now.isoformat(),
                    "error_message": error_message,
                }
            ).eq("run_id", run_id).execute()
        except Exception as exc:  # noqa: BLE001
            log.warning("observability finish_run failed: %s", exc)

    def insert_llm_event(
        self,
        *,
        run_id: str,
        prompt_snippet: str,
        response_snippet: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        duration_ms: int,
        provider: str = "gwdg",
    ) -> None:
        if prompt_tokens is not None and completion_tokens is not None:
            cost = (
                prompt_tokens * _PROMPT_EUR_PER_TOKEN
                + completion_tokens * _COMPLETION_EUR_PER_TOKEN
            )
        else:
            cost = None

        try:
            self._db.raw.table("llm_events").insert(
                {
                    "run_id": run_id,
                    "prompt_snippet": prompt_snippet,
                    "response_snippet": response_snippet,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "estimated_cost_eur": cost,
                    "duration_ms": duration_ms,
                    "provider": provider,
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            log.warning("observability insert_llm_event failed: %s", exc)

    def fetch_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        resp = (
            self._db.raw.table("agent_runs")
            .select("*")
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
        return cast("list[dict[str, Any]]", resp.data or [])

    def fetch_events_for_run(self, run_id: str) -> list[dict[str, Any]]:
        resp = (
            self._db.raw.table("llm_events")
            .select("*")
            .eq("run_id", run_id)
            .order("created_at")
            .execute()
        )
        return cast("list[dict[str, Any]]", resp.data or [])
