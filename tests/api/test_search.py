"""Tests for the AI search-suggestions endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.main import create_app
from job_agent.tools.search_suggester import SearchSuggestion


def _client(db: MagicMock) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("u-1", "t")
    app.dependency_overrides[get_user_db] = lambda: db
    return TestClient(app)


def _db_with_profile(rows: list[dict] | None) -> MagicMock:
    db = MagicMock()
    chain = db.raw.table.return_value.select.return_value.limit.return_value
    chain.execute.return_value.data = rows
    return db


def test_suggestions_400_without_profile() -> None:
    db = _db_with_profile([])
    r = _client(db).get("/api/search/suggestions")
    assert r.status_code == 400


def test_suggestions_returns_cached_list_without_llm_call() -> None:
    """When suggested_searches is populated, the endpoint must NOT call SearchSuggester."""
    cached = [
        {"keyword": "Backend Python Developer", "location": "Berlin", "rationale": "r"},
        {"keyword": "Data Engineer", "location": None, "rationale": None},
    ]
    db = _db_with_profile([
        {
            "summary": "Py dev",
            "skills": ["Python"],
            "experience": [],
            "education": [],
            "languages": [],
            "suggested_searches": cached,
        }
    ])
    with patch("job_agent.api.routers.search.SearchSuggester") as mock_suggester, \
         patch("job_agent.api.routers.search.MatcherAgent") as mock_matcher:
        r = _client(db).get("/api/search/suggestions")
    mock_suggester.assert_not_called()
    mock_matcher.build_candidate_text.assert_not_called()
    assert r.status_code == 200
    assert [s["keyword"] for s in r.json()] == [
        "Backend Python Developer",
        "Data Engineer",
    ]


def test_suggestions_falls_back_to_llm_when_cache_empty() -> None:
    """When suggested_searches is empty/null, the endpoint falls back to live LLM."""
    db = _db_with_profile([
        {
            "summary": "Py dev",
            "skills": ["Python"],
            "experience": [],
            "education": [],
            "languages": [],
            "suggested_searches": [],
        }
    ])
    suggester = MagicMock()
    suggester.suggest.return_value = [
        SearchSuggestion(keyword="Backend Python Developer", location="Berlin"),
        SearchSuggestion(keyword="Data Engineer"),
    ]
    with patch("job_agent.api.routers.search.SearchSuggester", return_value=suggester):
        r = _client(db).get("/api/search/suggestions")
    suggester.suggest.assert_called_once()
    assert r.status_code == 200
    assert [s["keyword"] for s in r.json()] == ["Backend Python Developer", "Data Engineer"]
