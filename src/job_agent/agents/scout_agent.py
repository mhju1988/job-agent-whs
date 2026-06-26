"""Scout Agent — fetches jobs from Arbeitsagentur API and persists them.

Note: This class intentionally does NOT subclass CrewAI ``Agent`` or wire a
``Crew``. The formal CrewAI orchestration layer (task / crew definitions) is
deferred to a later sprint. The class shape satisfies the multi-agent design
and acts as a DI-friendly unit-testable component.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from job_agent.tools.embedder import Embedder
    from job_agent.tools.observability_store import ObservabilityStore

from job_agent.db.client import SupabaseClient
from job_agent.models.job import Job
from job_agent.tools.arbeitsagentur_client import ArbeitsagenturClient
from job_agent.tools.job_normalizer import normalize
from job_agent.tools.run_context import ProgressCb, StopCb
from job_agent.tools.run_context import emit_progress as _emit

_log = logging.getLogger(__name__)

# Sources that accept `page` / `page_size` kwargs; others get keyword+location only.
_PAGINATION_SOURCES: frozenset[str] = frozenset({"arbeitsagentur"})


class ScoutResult(BaseModel):
    """Summary of a single Scout run."""

    fetched: int
    normalized: int
    upserted: int
    errors: list[str]
    details_fetched: int = 0


class ScoutAgent:
    """Fetches, normalises, and persists job listings from Arbeitsagentur.

    All three collaborators are dependency-injection seams:
    - ``client``      — ArbeitsagenturClient (or any duck-typed mock)
    - ``db``          — SupabaseClient (or mock)
    - ``normalize_fn``— callable matching ``normalize(source, raw_job) -> Job``

    When any argument is ``None``, the production default is constructed, which
    triggers credential guards.  That is intentional for production use and
    irrelevant for tests (always pass mocks).
    """

    def __init__(
        self,
        client: ArbeitsagenturClient | None = None,
        db: SupabaseClient | None = None,
        normalize_fn: Callable[..., Job] | None = None,
        clients: dict[str, Any] | None = None,
        obs: ObservabilityStore | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        """Construct with one of two patterns:

        - ``client=...`` (legacy single-source): registers under ``"arbeitsagentur"``.
        - ``clients={"source": <client>, ...}`` (multi-source): dispatch table.

        Passing both raises ``ValueError`` — pick one. When both are ``None``
        a production Arbeitsagentur client is built (triggers credential guard).

        ``embedder`` is optional: when provided, every normalised job is
        embedded (``Job.to_embedding_text()``) and stamped onto its upsert row
        so it shares the profile's embedding space and the cosine-match RPC
        can find it. When ``None`` (e.g. tests), jobs are upserted without a
        vector — back-compat with prior behavior.
        """
        if client is not None and clients is not None:
            raise ValueError(
                "ScoutAgent: pass either `client=` OR `clients=`, not both."
            )

        if clients is not None:
            self._clients: dict[str, Any] = dict(clients)
        else:
            legacy_client = (
                client if client is not None else ArbeitsagenturClient.with_default_opener()
            )
            self._clients = {"arbeitsagentur": legacy_client}

        self._db: SupabaseClient = db if db is not None else SupabaseClient()
        self._normalize: Callable[..., Job] = (
            normalize_fn if normalize_fn is not None else normalize
        )
        self._obs: ObservabilityStore | None = obs
        self._embedder: Embedder | None = embedder

    @staticmethod
    def _extract_raw_list(source: str, raw: Any) -> list[dict[str, Any]]:
        """Per-source extractor: where each API hides its job list."""
        if isinstance(raw, list):
            return raw
        if not isinstance(raw, dict):
            return []
        if source == "arbeitsagentur":
            result: list[dict[str, Any]] = raw.get("stellenangebote") or []
            return result
        if source == "jsearch":
            result = raw.get("data") or []
            return result
        # Unknown source dict shape — try a `.data` fallback then give up.
        return raw.get("data") or []

    def run(
        self,
        keyword: str | None = None,
        location: str | None = None,
        page: int = 1,
        page_size: int = 25,
        sources: list[str] | None = None,
        on_progress: ProgressCb | None = None,
        user_id: str | None = None,
        should_stop: StopCb | None = None,
    ) -> ScoutResult:
        """Fetch jobs across all configured sources, normalise, upsert, return summary."""
        from job_agent.tools.run_context import start_run

        ctx = start_run("scout")
        if self._obs:
            self._obs.insert_run(ctx, user_id=user_id)
        try:
            result = self._do_run(
                keyword=keyword,
                location=location,
                page=page,
                page_size=page_size,
                sources=sources,
                on_progress=on_progress,
                should_stop=should_stop,
            )
            if self._obs:
                self._obs.finish_run(ctx.run_id, "success")
            return result
        except Exception as exc:
            if self._obs:
                self._obs.finish_run(ctx.run_id, "error", str(exc)[:500])
            raise

    def _do_run(
        self,
        keyword: str | None = None,
        location: str | None = None,
        page: int = 1,
        page_size: int = 25,
        sources: list[str] | None = None,
        on_progress: ProgressCb | None = None,
        should_stop: StopCb | None = None,
    ) -> ScoutResult:
        """Fetch jobs from all sources, normalise, upsert to DB, return summary.

        Iterates ``self._clients`` (filtered by ``sources`` if provided), calls
        each ``client.search(...)``, dispatches normalisation with the correct
        source key, and merges all results into a single upsert batch (DB
        dedupes on ``(source, external_id)``).

        Per-source details: if a client exposes ``fetch_detail(ref)`` (e.g.
        Arbeitsagentur), each job is enriched with the full description;
        failures are non-fatal.
        """
        active_sources = (
            [s for s in (sources or list(self._clients.keys())) if s in self._clients]
        )

        jobs: list[Job] = []
        errors: list[str] = []
        details_fetched = 0
        total_fetched = 0

        _emit(on_progress, stage="start", total=len(active_sources))
        for src_idx, source in enumerate(active_sources, start=1):
            if should_stop is not None and should_stop():
                break
            _emit(
                on_progress,
                stage="source",
                source=source,
                current=src_idx,
                total=len(active_sources),
            )
            client = self._clients[source]
            try:
                if source in _PAGINATION_SOURCES:
                    raw = client.search(
                        keyword=keyword,
                        location=location,
                        page=page,
                        page_size=page_size,
                    )
                else:
                    raw = client.search(keyword=keyword, location=location)
            except Exception as exc:  # noqa: BLE001 — one source's failure must not abort others
                # Include exc.status when present (e.g. JSearchAPIError, ArbeitsagenturAPIError)
                # so the UI can switch on it deterministically rather than substring-matching.
                status_tag = f" [{exc.status}]" if hasattr(exc, "status") else ""
                err = f"{source}: search failed{status_tag}: {type(exc).__name__}: {exc}"
                errors.append(err)
                _log.warning("scout %s", err)
                continue

            raw_list = self._extract_raw_list(source, raw)
            total_fetched += len(raw_list)
            supports_detail = hasattr(client, "fetch_detail")

            for raw_job in raw_list:
                if should_stop is not None and should_stop():
                    break
                # First pass: normalise from the list row.
                try:
                    job = self._normalize(source, raw_job)
                except Exception as exc:  # noqa: BLE001
                    err = f"{source}: normalize: {type(exc).__name__}: {exc}"
                    errors.append(err)
                    _log.warning("scout %s", err)
                    continue

                # Second pass (per-source): enrich with detail endpoint when
                # supported. A detail-fetch failure keeps the un-enriched job.
                if supports_detail:
                    try:
                        detail = client.fetch_detail(job.external_id)
                        job = self._normalize(source, raw_job, detail=detail)
                        details_fetched += 1
                    except Exception as exc:  # noqa: BLE001
                        err = (
                            f"{source}: detail fetch failed for {job.external_id}: "
                            f"{type(exc).__name__}: {exc}"
                        )
                        errors.append(err)
                        _log.warning("scout %s", err)

                jobs.append(job)

        rows = [job.to_supabase_row() for job in jobs]

        # Embed each job so it shares the profile's embedding space — a
        # prerequisite for the cosine-match RPC. Best-effort (non-fatal), like
        # the detail-fetch step above: a failed embedding is logged and the
        # job is still upserted without a vector. Skipped entirely when no
        # embedder is configured (tests / opt-in).
        if self._embedder is not None and rows:
            embedded = 0
            for job, row in zip(jobs, rows, strict=True):
                try:
                    row["embedding"] = self._embedder.embed_text(
                        job.to_embedding_text()
                    )
                    embedded += 1
                except Exception as exc:  # noqa: BLE001 — one job must not abort the run
                    err = (
                        f"{job.source}:{job.external_id}: embed failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    errors.append(err)
                    _log.warning("scout %s", err)
            _emit(on_progress, stage="embedded", embedded=embedded)

        if rows:
            self._db.raw.table("jobs").upsert(
                rows, on_conflict="source,external_id"
            ).execute()

        _emit(on_progress, stage="done", upserted=len(rows), fetched=total_fetched)

        return ScoutResult(
            fetched=total_fetched,
            normalized=len(jobs),
            upserted=len(rows),
            errors=errors[:10],
            details_fetched=details_fetched,
        )
