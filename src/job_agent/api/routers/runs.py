"""Agent-run SSE endpoints: scout, matcher, scout-matcher, writer.

Each endpoint runs the agent in a worker thread and streams live progress
events followed by a terminal result event (see api.progress.run_agent_sse).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastapi import APIRouter, Body, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from job_agent.agents.base_agent import BaseAgent
from job_agent.agents.matcher_agent import MatcherAgent, MatcherResult
from job_agent.agents.scout_agent import ScoutAgent
from job_agent.agents.writer_agent import WriterAgent
from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.progress import run_agent_sse
from job_agent.api.schemas import (
    MatcherRunRequest,
    RescoreRunRequest,
    ScoutRunRequest,
    WriterRunRequest,
)
from job_agent.config import get_settings
from job_agent.db.client import SupabaseClient
from job_agent.services.profile_service import load_candidate_brief
from job_agent.tools.cover_letter_template import CoverLetterRenderer
from job_agent.tools.observability_store import ObservabilityStore
from job_agent.tools.run_context import emit_progress as _emit
from job_agent.tools.search_suggester import SearchSuggester

router = APIRouter()


def _profile_id(db: SupabaseClient) -> str:
    rows = db.raw.table("profile").select("id").limit(1).execute().data or []
    if not rows:
        raise HTTPException(status_code=400, detail="No profile. Upload a CV first.")
    return str(cast("dict[str, Any]", rows[0])["id"])


def _build_scout(db: SupabaseClient) -> ScoutAgent:
    """Mirror ui.app.get_scout_agent — Arbeitsagentur always, JSearch when keyed."""
    from job_agent.tools.arbeitsagentur_client import ArbeitsagenturClient
    from job_agent.tools.embedder import Embedder

    clients: dict[str, Any] = {
        "arbeitsagentur": ArbeitsagenturClient.with_default_opener(),
    }
    key = get_settings().rapidapi_key
    if key:
        from job_agent.tools.jsearch_client import JSearchClient

        clients["jsearch"] = JSearchClient.with_default_opener(api_key=key)
    # Embed each job so it shares the profile's embedding space — required for
    # the stage-1 cosine-match RPC. Constructed once per run; embedding is
    # best-effort inside ScoutAgent (failures are logged, not fatal).
    return ScoutAgent(
        clients=clients, db=db, obs=ObservabilityStore(db=db), embedder=Embedder()
    )


@router.post("/runs/scout")
def run_scout(
    body: ScoutRunRequest,
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> EventSourceResponse:
    def work(on_progress: Any, should_stop: Any) -> dict[str, Any]:
        scout = _build_scout(db)
        result = scout.run(
            keyword=body.keyword,
            location=body.location,
            page_size=body.max_results,
            sources=body.sources,
            on_progress=on_progress,
            user_id=user.user_id,
            should_stop=should_stop,
        )
        return result.model_dump()

    return run_agent_sse(work)


@router.post("/runs/matcher")
def run_matcher(
    body: MatcherRunRequest = Body(default_factory=MatcherRunRequest),  # noqa: B008
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> EventSourceResponse:
    pid = _profile_id(db)

    def work(on_progress: Any, should_stop: Any) -> dict[str, Any]:
        agent = MatcherAgent(db=db, obs=ObservabilityStore(db=db))
        return agent.run(
            pid,
            user_id=user.user_id,
            job_ids=body.job_ids or None,
            exclude_scored=not bool(body.job_ids),
            on_progress=on_progress,
            should_stop=should_stop,
        ).model_dump()

    return run_agent_sse(work)


def _scout_then_matcher(
    scout: ScoutAgent,
    matcher: MatcherAgent,
    *,
    profile_id: str,
    user_id: str,
    keyword: str | None,
    location: str | None,
    page_size: int,
    sources: list[str] | None,
    on_progress: Any,
    should_stop: Callable[[], bool],
) -> dict[str, Any]:
    """Run Scout, then Matcher — but skip Matcher entirely if the run was
    cancelled during Scout (so we don't waste the matcher's pre-loop RPC)."""
    scout_result = scout.run(
        keyword=keyword,
        location=location,
        page_size=page_size,
        sources=sources,
        on_progress=on_progress,
        user_id=user_id,
        should_stop=should_stop,
    )
    if should_stop():
        return {
            "scout": scout_result.model_dump(),
            "matcher": MatcherResult(
                candidates_considered=0, scored=0, persisted=0, errors=[]
            ).model_dump(),
        }
    match_result = matcher.run(
        profile_id,
        user_id=user_id,
        on_progress=on_progress,
        should_stop=should_stop,
    )
    return {"scout": scout_result.model_dump(), "matcher": match_result.model_dump()}


@router.post("/runs/scout-matcher")
def run_scout_matcher(
    body: ScoutRunRequest,
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> EventSourceResponse:
    # Resolve the profile up front so a missing profile returns a real 400
    # (not a silent SSE error event) and we don't waste a Scout run.
    pid = _profile_id(db)

    def work(on_progress: Any, should_stop: Any) -> dict[str, Any]:
        # AI-determined search: with no keyword, ask the LLM to pick the most
        # relevant role from the candidate's profile before scouting.
        keyword = body.keyword
        location = body.location
        if not keyword:
            brief = load_candidate_brief(db)
            if brief:
                msg = "Selecting keyword from your profile…"
                _emit(on_progress, stage="suggesting", message=msg)
                # No obs: quick helper LLM call, not a tracked agent run.
                picks = SearchSuggester().suggest(brief, max_suggestions=1)
                if picks:
                    keyword = picks[0].keyword
                    location = location or picks[0].location
                    _emit(on_progress, stage="suggesting", keyword=keyword)

        if not keyword:
            raise ValueError(
                "Could not determine a search keyword — enter a term manually "
                "or upload a CV so the AI can pick the best role for you."
            )

        return _scout_then_matcher(
            _build_scout(db),
            MatcherAgent(db=db, obs=ObservabilityStore(db=db)),
            profile_id=pid,
            user_id=user.user_id,
            keyword=keyword,
            location=location,
            page_size=body.max_results,
            sources=body.sources,
            on_progress=on_progress,
            should_stop=should_stop,
        )

    return run_agent_sse(work)


@router.post("/runs/writer")
def run_writer(
    body: WriterRunRequest,
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> EventSourceResponse:
    pid = _profile_id(db)

    def work(on_progress: Any, should_stop: Any) -> dict[str, Any]:
        obs = ObservabilityStore(db=db)
        renderer = CoverLetterRenderer(llm_agent=BaseAgent(obs=obs), language=body.language)
        writer = WriterAgent(db=db, renderer=renderer, obs=obs)
        result = writer.run(
            profile_id=pid,
            job_id=body.job_id,
            match_score_id=body.match_score_id,
            candidate_name=body.candidate_name,
            matched_skills=body.matched_skills,
            user_id=user.user_id,
            on_progress=on_progress,
        )
        return result.model_dump()

    return run_agent_sse(work)


@router.post("/runs/rescore")
def run_rescore(
    body: RescoreRunRequest,
    user: CurrentUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_user_db),
) -> EventSourceResponse:
    """Re-score the user's top-``limit`` match_scores (by score) against the
    current profile, in place (exclude_scored=False -> upsert). Non-destructive.

    ``limit`` is required so a profile edit can't fire an unbounded re-score
    against the rate-limited LLM endpoint.
    """
    pid = _profile_id(db)
    rows = (
        db.raw.table("match_scores")
        .select("job_id")
        .eq("user_id", user.user_id)
        .order("score", desc=True)
        .limit(body.limit)
        .execute()
        .data
        or []
    )
    job_ids = [str(cast("dict[str, Any]", r)["job_id"]) for r in rows]

    def work(on_progress: Any, should_stop: Any) -> dict[str, Any]:
        if not job_ids:
            return MatcherResult(
                candidates_considered=0, scored=0, persisted=0, errors=[]
            ).model_dump()
        agent = MatcherAgent(db=db, obs=ObservabilityStore(db=db))
        return agent.run(
            pid,
            user_id=user.user_id,
            job_ids=job_ids,
            exclude_scored=False,
            on_progress=on_progress,
            should_stop=should_stop,
        ).model_dump()

    return run_agent_sse(work)
