"""Tests for MatcherAgent explicit job_ids path."""
from __future__ import annotations

from unittest.mock import MagicMock

from job_agent.agents.base_agent import AskResult
from job_agent.agents.matcher_agent import MatcherAgent

_PROFILE = {
    "summary": "Python developer",
    "skills": ["Python", "FastAPI"],
    "experience": [],
    "education": [],
    "languages": ["English"],
}

_JOB = {
    "id": "job-abc",
    "title": "Python Dev",
    "company": "Acme",
    "description": "Build APIs.",
    "requirements": ["Python", "Docker"],
}

_LLM_RESPONSE = (
    '{"score": 80, "matched_skills": ["Python"], '
    '"gaps": ["Docker"], "rationale": "Good match."}'
)


def _make_db(
    *,
    profile_data: list[dict],
    jobs_data: list[dict],
    scored_data: list[dict] | None = None,
) -> tuple[MagicMock, dict[str, MagicMock]]:
    """Return (db_mock, table_mocks) with per-table dispatch via side_effect."""
    db = MagicMock()
    table_mocks: dict[str, MagicMock] = {}

    def _table(name: str) -> MagicMock:
        if name not in table_mocks:
            table_mocks[name] = MagicMock()
        return table_mocks[name]

    db.raw.table.side_effect = _table

    # profile
    pm = _table("profile")
    (
        pm.select.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
        .data
    ) = profile_data

    # jobs (explicit-ID fetch)
    jm = _table("jobs")
    (
        jm.select.return_value
        .in_.return_value
        .execute.return_value
        .data
    ) = jobs_data

    # match_scores — filter query (select → eq → in_ → execute)
    sm = _table("match_scores")
    (
        sm.select.return_value
        .eq.return_value
        .in_.return_value
        .execute.return_value
        .data
    ) = scored_data or []
    sm.upsert.return_value.execute.return_value = MagicMock()

    return db, table_mocks


def test_explicit_job_ids_skips_rpc_and_uses_jobs_table():
    """When job_ids provided: RPC must NOT be called; 'jobs' table MUST be used."""
    db, table_mocks = _make_db(
        profile_data=[_PROFILE],
        jobs_data=[_JOB],
    )
    llm = MagicMock()
    llm.ask_with_provider.return_value = AskResult(content=_LLM_RESPONSE, provider="gwdg")

    agent = MatcherAgent(db=db, llm_agent=llm)
    result = agent.run("profile-1", user_id="user-1", job_ids=["job-abc"])

    assert result.candidates_considered == 1
    assert result.scored == 1
    assert result.persisted == 1
    assert result.errors == []

    assert "jobs" in table_mocks, "Expected 'jobs' table to be queried"
    assert "job_listings" not in table_mocks, "'job_listings' must never be queried"

    db.raw.rpc.assert_not_called()


def test_explicit_job_ids_filters_already_scored():
    """Already-scored jobs are skipped when exclude_scored=True (default)."""
    db, _ = _make_db(
        profile_data=[_PROFILE],
        jobs_data=[],
        scored_data=[{"job_id": "job-abc"}],
    )
    llm = MagicMock()

    agent = MatcherAgent(db=db, llm_agent=llm)
    result = agent.run("profile-1", user_id="user-1", job_ids=["job-abc"])

    assert result.candidates_considered == 0
    assert result.scored == 0
    llm.ask_with_provider.assert_not_called()


def test_empty_job_ids_falls_back_to_rpc():
    """When job_ids is None, the existing pgvector RPC path is used."""
    db, _ = _make_db(
        profile_data=[_PROFILE],
        jobs_data=[],
    )
    db.raw.rpc.return_value.execute.return_value.data = [
        {
            "job_id": "job-xyz",
            "title": "Dev",
            "company": "Foo",
            "description": "Work.",
            "requirements": [],
            "similarity": 0.9,
        }
    ]

    llm = MagicMock()
    llm.ask_with_provider.return_value = AskResult(content=_LLM_RESPONSE, provider="gwdg")

    agent = MatcherAgent(db=db, llm_agent=llm)
    agent.run("profile-1", user_id="user-1", job_ids=None)

    db.raw.rpc.assert_called_once()
