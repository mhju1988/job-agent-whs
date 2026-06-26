"""Tests for the SSE agent-run endpoints."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from job_agent.agents.matcher_agent import MatcherResult
from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.main import create_app


def _client(db: MagicMock) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("u-1", "t")
    app.dependency_overrides[get_user_db] = lambda: db
    return TestClient(app)


def test_matcher_run_streams_progress_then_result() -> None:
    db = MagicMock()
    # _profile_id lookup
    db.raw.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"id": "p-1"}
    ]

    fake = MagicMock()

    def _run(profile_id: str, *, user_id: str, on_progress: Any = None, **kw: Any) -> MatcherResult:
        if on_progress:
            on_progress({"stage": "scoring", "current": 1, "total": 1})
        return MatcherResult(candidates_considered=1, scored=1, persisted=1, errors=[])

    fake.run.side_effect = _run

    with patch("job_agent.api.routers.runs.MatcherAgent", return_value=fake):
        client = _client(db)
        with client.stream("POST", "/api/runs/matcher") as r:
            body = "".join(chunk for chunk in r.iter_text())

    assert "event: progress" in body
    assert "event: result" in body
    assert '"scored": 1' in body


def test_matcher_passes_exclude_scored_false_when_job_ids_provided() -> None:
    """When explicit job_ids are sent, exclude_scored must be False so already-scored
    jobs are not silently skipped (which would produce a run with zero LLM events)."""
    db = MagicMock()
    db.raw.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"id": "p-1"}
    ]
    fake = MagicMock()
    fake.run.return_value = MatcherResult(candidates_considered=1, scored=1, persisted=1, errors=[])

    with patch("job_agent.api.routers.runs.MatcherAgent", return_value=fake):
        client = _client(db)
        with client.stream("POST", "/api/runs/matcher", json={"job_ids": ["j-1"]}) as r:
            r.read()

    call_kwargs = fake.run.call_args.kwargs
    assert call_kwargs["exclude_scored"] is False, (
        "exclude_scored must be False when job_ids are provided so rescoring works"
    )


def test_matcher_passes_exclude_scored_true_when_no_job_ids() -> None:
    """Without explicit job_ids, exclude_scored stays True to skip already-scored jobs."""
    db = MagicMock()
    db.raw.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"id": "p-1"}
    ]
    fake = MagicMock()
    fake.run.return_value = MatcherResult(candidates_considered=0, scored=0, persisted=0, errors=[])

    with patch("job_agent.api.routers.runs.MatcherAgent", return_value=fake):
        client = _client(db)
        with client.stream("POST", "/api/runs/matcher") as r:
            r.read()

    call_kwargs = fake.run.call_args.kwargs
    assert call_kwargs["exclude_scored"] is True


def test_run_requires_auth() -> None:
    # No dependency overrides → auth enforced.
    client = TestClient(create_app())
    assert client.post("/api/runs/matcher").status_code == 401


def test_rescore_resolves_top_k_by_score_and_disables_exclude() -> None:
    db = MagicMock()
    select = db.raw.table.return_value.select.return_value
    select.limit.return_value.execute.return_value.data = [{"id": "p-1"}]  # _profile_id
    # match_scores top-K: select(job_id).eq(user).order(score desc).limit(K).execute()
    ms = select.eq.return_value.order.return_value.limit.return_value
    ms.execute.return_value.data = [{"job_id": "j-1"}, {"job_id": "j-2"}]
    fake = MagicMock()
    fake.run.return_value = MatcherResult(
        candidates_considered=2, scored=2, persisted=2, errors=[]
    )

    with (
        patch("job_agent.api.routers.runs.MatcherAgent", return_value=fake),
        _client(db).stream("POST", "/api/runs/rescore", json={"limit": 5}) as r,
    ):
        r.read()

    select.eq.return_value.order.assert_called_once_with("score", desc=True)
    select.eq.return_value.order.return_value.limit.assert_called_once_with(5)
    kw = fake.run.call_args.kwargs
    assert kw["job_ids"] == ["j-1", "j-2"]
    assert kw["exclude_scored"] is False


def test_rescore_empty_match_set_skips_llm() -> None:
    db = MagicMock()
    select = db.raw.table.return_value.select.return_value
    select.limit.return_value.execute.return_value.data = [{"id": "p-1"}]
    ms = select.eq.return_value.order.return_value.limit.return_value
    ms.execute.return_value.data = []
    fake = MagicMock()

    with (
        patch("job_agent.api.routers.runs.MatcherAgent", return_value=fake),
        _client(db).stream("POST", "/api/runs/rescore", json={"limit": 5}) as r,
    ):
        body = "".join(chunk for chunk in r.iter_text())

    fake.run.assert_not_called()
    assert '"scored": 0' in body


def test_rescore_requires_limit() -> None:
    assert _client(MagicMock()).post("/api/runs/rescore", json={}).status_code == 422


def test_rescore_rejects_non_positive_limit() -> None:
    assert _client(MagicMock()).post("/api/runs/rescore", json={"limit": 0}).status_code == 422


def test_scout_then_matcher_skips_matcher_when_stopped_after_scout() -> None:
    """should_stop True after scout -> matcher.run not called, zeros matcher dict."""
    from job_agent.agents.scout_agent import ScoutResult
    from job_agent.api.routers.runs import _scout_then_matcher

    scout = MagicMock()
    scout.run.return_value = ScoutResult(
        fetched=2, normalized=2, upserted=2, errors=[], details_fetched=2
    )
    matcher = MagicMock()

    out = _scout_then_matcher(
        scout, matcher,
        profile_id="p-1", user_id="u-1",
        keyword="Python", location="Berlin", page_size=25, sources=None,
        on_progress=None, should_stop=lambda: True,
    )

    matcher.run.assert_not_called()
    assert out["matcher"] == MatcherResult(
        candidates_considered=0, scored=0, persisted=0, errors=[]
    ).model_dump()
    assert out["scout"]["upserted"] == 2


def test_scout_then_matcher_runs_matcher_when_not_stopped() -> None:
    from job_agent.agents.scout_agent import ScoutResult
    from job_agent.api.routers.runs import _scout_then_matcher

    scout = MagicMock()
    scout.run.return_value = ScoutResult(
        fetched=1, normalized=1, upserted=1, errors=[], details_fetched=1
    )
    matcher = MagicMock()
    matcher.run.return_value = MatcherResult(
        candidates_considered=1, scored=1, persisted=1, errors=[]
    )

    out = _scout_then_matcher(
        scout, matcher,
        profile_id="p-1", user_id="u-1",
        keyword="Python", location="Berlin", page_size=25, sources=None,
        on_progress=None, should_stop=lambda: False,
    )

    matcher.run.assert_called_once()
    assert matcher.run.call_args.kwargs["should_stop"] is not None
    assert out["matcher"]["scored"] == 1
    assert out["scout"]["upserted"] == 1
