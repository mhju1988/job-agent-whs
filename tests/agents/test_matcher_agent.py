"""Tests for MatcherAgent (new profile_id-based API)."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from job_agent.agents.base_agent import AskResult
from job_agent.agents.matcher_agent import MatcherAgent, MatcherResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROFILE_ID = "00000000-0000-0000-0000-000000000001"
USER_ID = "00000000-0000-0000-0000-0000000000aa"


def _make_rpc_row(i: int) -> dict[str, object]:
    return {
        "job_id": f"job-{i:03d}",
        "title": f"Title {i}",
        "company": f"Company {i}",
        "description": f"Description for job {i}.",
        "requirements": ["Python", "SQL"],
        "similarity": round(0.95 - i * 0.05, 2),
    }


def _valid_llm_json(score: int = 80) -> str:
    return json.dumps(
        {
            "score": score,
            "matched_skills": ["Python"],
            "gaps": ["Docker"],
            "rationale": "Good match overall.",
        }
    )


_PROFILE_ROW: dict[str, object] = {
    "summary": "Mid-level Python dev.",
    "skills": ["Python", "SQL"],
    "experience": [{"title": "Dev", "company": "Acme"}],
    "education": [{"degree": "B.Sc.", "institution": "FH"}],
    "languages": ["English"],
}


def _make_db_mock(rows: list[dict[str, object]]) -> MagicMock:
    db = MagicMock()
    db.raw.rpc.return_value.execute.return_value = MagicMock(data=rows)

    # profile fetch chain: db.raw.table("profile").select(...).eq(...).limit(1).execute()
    profile_chain = MagicMock()
    profile_chain.execute.return_value = MagicMock(data=[_PROFILE_ROW])

    # match_scores upsert chain: db.raw.table("match_scores").upsert(...).execute()
    upsert_chain = MagicMock()
    upsert_chain.return_value.execute.return_value = MagicMock(data=[{}])

    def _table(name: str) -> MagicMock:
        t = MagicMock()
        if name == "profile":
            t.select.return_value.eq.return_value.limit.return_value = profile_chain
        else:
            t.upsert = upsert_chain
        return t

    db.raw.table.side_effect = _table
    return db


def _make_llm_mock(responses: list[str] | None = None, default: str | None = None) -> MagicMock:
    llm = MagicMock()
    if responses is not None:
        llm.ask_with_provider.side_effect = [
            AskResult(content=r, provider="gwdg") for r in responses
        ]
    else:
        llm.ask_with_provider.return_value = AskResult(
            content=default or _valid_llm_json(), provider="gwdg"
        )
    return llm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_end_to_end_scores_every_rpc_row() -> None:
    """Mock RPC returns 10 rows (mock ignores top_n); all get scored + persisted in one batch."""
    rows = [_make_rpc_row(i) for i in range(10)]
    db = _make_db_mock(rows)
    llm = _make_llm_mock()

    agent = MatcherAgent(db=db, llm_agent=llm)
    result = agent.run(PROFILE_ID, user_id=USER_ID, top_n=5)

    assert isinstance(result, MatcherResult)
    assert result.candidates_considered == 10
    assert result.scored == 10
    assert result.persisted == 10
    assert result.errors == []

    # upsert called once with 10 dicts each containing required keys
    table_calls = [c.args[0] for c in db.raw.table.call_args_list]
    assert "match_scores" in table_calls
    assert table_calls.count("match_scores") == 1
    upsert_chain = db.raw.table.side_effect("match_scores").upsert
    upsert_call_args = upsert_chain.call_args
    upserted_rows = upsert_call_args[0][0]
    assert len(upserted_rows) == 10
    for row in upserted_rows:
        assert "job_id" in row
        assert "score" in row
        assert "gaps" in row
        assert "rationale" in row
        assert row["model_provider"] == "gwdg"


def test_partial_llm_failures_collected() -> None:
    """3 of 10 LLM responses are invalid JSON; scored==7, persisted==7, len(errors)==3."""
    rows = [_make_rpc_row(i) for i in range(10)]
    db = _make_db_mock(rows)

    responses: list[str] = []
    bad_indices = {2, 5, 8}
    for i in range(10):
        if i in bad_indices:
            responses.append("not json at all")
        else:
            responses.append(_valid_llm_json())

    llm = _make_llm_mock(responses=responses)

    agent = MatcherAgent(db=db, llm_agent=llm)
    result = agent.run(PROFILE_ID, user_id=USER_ID, top_n=10)

    assert result.candidates_considered == 10
    assert result.scored == 7
    assert result.persisted == 7
    assert len(result.errors) == 3


def test_invalid_match_schema_collected() -> None:
    """LLM returns valid JSON but score=150 (out of range); pydantic rejects it."""
    rows = [_make_rpc_row(0)]
    db = _make_db_mock(rows)
    bad_json = json.dumps(
        {"score": 150, "matched_skills": [], "gaps": [], "rationale": "x"}
    )
    llm = _make_llm_mock(responses=[bad_json])

    agent = MatcherAgent(db=db, llm_agent=llm)
    result = agent.run(PROFILE_ID, user_id=USER_ID, top_n=1)

    assert result.candidates_considered == 1
    assert result.scored == 0
    assert result.persisted == 0
    assert len(result.errors) == 1
    table_calls = [c.args[0] for c in db.raw.table.call_args_list]
    assert "match_scores" not in table_calls


def test_empty_rpc_response_no_insert() -> None:
    """RPC returns 0 rows; insert never called; all counts zero."""
    db = _make_db_mock([])
    llm = _make_llm_mock()

    agent = MatcherAgent(db=db, llm_agent=llm)
    result = agent.run(PROFILE_ID, user_id=USER_ID)

    assert result.candidates_considered == 0
    assert result.scored == 0
    assert result.persisted == 0
    assert result.errors == []
    table_calls = [c.args[0] for c in db.raw.table.call_args_list]
    assert "match_scores" not in table_calls


def test_json_fence_stripped() -> None:
    """LLM wraps response in ```json ... ```; matcher still parses it."""
    rows = [_make_rpc_row(0)]
    db = _make_db_mock(rows)
    fenced = "```json\n" + _valid_llm_json(72) + "\n```"
    llm = _make_llm_mock(responses=[fenced])

    agent = MatcherAgent(db=db, llm_agent=llm)
    result = agent.run(PROFILE_ID, user_id=USER_ID, top_n=1)

    assert result.scored == 1
    assert result.persisted == 1
    assert result.errors == []


def test_literal_control_char_in_rationale_still_scores() -> None:
    # German gap-analysis can yield a LITERAL newline inside the "rationale"
    # string instead of an escaped "\\n". Default json.loads (strict=True)
    # would reject it and silently drop the job as a parse error.
    rows = [_make_rpc_row(0)]
    db = _make_db_mock(rows)
    raw = (
        '{"score": 75, "matched_skills": ["Python"], "gaps": ["Docker"], '
        '"rationale": "Starker Treffer.\n'
        'Python und SQL passen gut."}'
    )
    assert "\n" in raw  # guard: reproduction needs a real control char
    llm = _make_llm_mock(responses=[raw])

    agent = MatcherAgent(db=db, llm_agent=llm)
    result = agent.run(PROFILE_ID, user_id=USER_ID, top_n=1)

    assert result.scored == 1
    assert result.persisted == 1
    assert result.errors == []


def test_errors_capped_at_10() -> None:
    """11 bad LLM responses; errors list is capped at 10."""
    rows = [_make_rpc_row(i) for i in range(11)]
    db = _make_db_mock(rows)
    responses = ["not json"] * 11
    llm = _make_llm_mock(responses=responses)

    agent = MatcherAgent(db=db, llm_agent=llm)
    result = agent.run(PROFILE_ID, user_id=USER_ID, top_n=11)

    assert result.candidates_considered == 11
    assert result.scored == 0
    assert result.persisted == 0
    assert len(result.errors) == 10


def test_run_records_agent_run_on_success() -> None:
    """MatcherAgent.run() calls insert_run and finish_run('success') when obs injected."""
    from unittest.mock import MagicMock

    from job_agent.tools.observability_store import ObservabilityStore

    mock_llm = MagicMock()
    mock_llm.ask.return_value = '{"score": 70, "matched_skills": [], "gaps": [], "rationale": "ok"}'
    mock_obs = MagicMock(spec=ObservabilityStore)

    # Return empty data so MatcherResult has 0 candidates (no LLM calls needed)
    db = _make_db_mock([])

    agent = MatcherAgent(db=db, llm_agent=mock_llm, obs=mock_obs)
    agent.run("profile-123", user_id=USER_ID)

    mock_obs.insert_run.assert_called_once()
    mock_obs.finish_run.assert_called_once()
    finish_args = mock_obs.finish_run.call_args
    assert finish_args[0][1] == "success"


def test_run_records_error_status_on_exception() -> None:
    """MatcherAgent.run() calls finish_run('error', ...) when an exception is raised."""
    import pytest

    from job_agent.tools.observability_store import ObservabilityStore

    db = MagicMock()
    db.raw.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.side_effect = (  # noqa: E501
        RuntimeError("db exploded")
    )
    mock_obs = MagicMock(spec=ObservabilityStore)

    agent = MatcherAgent(db=db, llm_agent=MagicMock(), obs=mock_obs)
    with pytest.raises(RuntimeError):
        agent.run("profile-123", user_id=USER_ID)

    finish_args = mock_obs.finish_run.call_args
    assert finish_args[0][1] == "error"
    assert "db exploded" in finish_args[0][2]


def test_run_passes_user_id_to_rpc_and_stamps_inserts() -> None:
    """user_id is forwarded to the RPC as p_user_id and stamped on every
    inserted match_scores row."""
    rows = [_make_rpc_row(0)]
    db = _make_db_mock(rows)
    llm = _make_llm_mock()

    agent = MatcherAgent(db=db, llm_agent=llm)
    agent.run(PROFILE_ID, user_id=USER_ID, top_n=1)

    # RPC called with p_user_id
    rpc_call = db.raw.rpc.call_args
    assert rpc_call.args[0] == "match_jobs_for_profile"
    assert rpc_call.args[1]["p_user_id"] == USER_ID

    # Every upserted row carries user_id
    upsert_rows = db.raw.table.side_effect("match_scores").upsert.call_args.args[0]
    assert upsert_rows, "expected at least one scored row"
    assert all(r["user_id"] == USER_ID for r in upsert_rows)


def test_matcher_emits_progress_per_job() -> None:
    """on_progress fires per scored job; the terminal event has current == total."""
    rows = [_make_rpc_row(i) for i in range(3)]
    db = _make_db_mock(rows)
    llm = _make_llm_mock()
    events: list[dict[str, object]] = []

    agent = MatcherAgent(db=db, llm_agent=llm)
    agent.run(PROFILE_ID, user_id=USER_ID, top_n=3, on_progress=events.append)

    assert any(e.get("stage") == "scoring" for e in events)
    assert events[-1]["stage"] == "done"
    assert events[-1]["current"] == events[-1]["total"]


def test_matcher_should_stop_cancels_queued_tail() -> None:
    """max_concurrency=1: jobs 3+ stay queued when the first completes and
    should_stop fires -> reliably cancelled. The immediate-next job races the
    worker pickup, so assert the robust property (not all scored), not ==1."""
    rows = [_make_rpc_row(i) for i in range(5)]
    db = _make_db_mock(rows)
    llm = _make_llm_mock()
    should_stop = lambda: llm.ask_with_provider.call_count >= 1  # noqa: E731

    agent = MatcherAgent(db=db, llm_agent=llm, max_concurrency=1)
    result = agent.run(PROFILE_ID, user_id=USER_ID, top_n=5, should_stop=should_stop)

    assert result.scored < 5  # cancellation prevented full scoring
    assert result.scored >= 1  # the first completed
    assert result.persisted == result.scored
    assert llm.ask_with_provider.call_count < 5  # tail never reached the LLM


def test_matcher_scores_all_under_concurrency() -> None:
    rows = [_make_rpc_row(i) for i in range(8)]
    db = _make_db_mock(rows)
    llm = _make_llm_mock()

    agent = MatcherAgent(db=db, llm_agent=llm, max_concurrency=4)
    result = agent.run(PROFILE_ID, user_id=USER_ID, top_n=8)

    assert result.scored == 8
    assert result.persisted == 8
    upserted = db.raw.table.side_effect("match_scores").upsert.call_args.args[0]
    assert len(upserted) == 8


def test_matcher_stamps_provider_per_call_under_concurrency() -> None:
    """Each row carries the provider from its OWN call (guards the race fix)."""
    rows = [_make_rpc_row(i) for i in range(6)]
    db = _make_db_mock(rows)
    llm = MagicMock()
    providers = [f"prov-{i}" for i in range(6)]
    llm.ask_with_provider.side_effect = [
        AskResult(content=_valid_llm_json(), provider=p) for p in providers
    ]

    agent = MatcherAgent(db=db, llm_agent=llm, max_concurrency=4)
    agent.run(PROFILE_ID, user_id=USER_ID, top_n=6)

    upserted = db.raw.table.side_effect("match_scores").upsert.call_args.args[0]
    assert sorted(r["model_provider"] for r in upserted) == sorted(providers)


def test_matcher_uses_configured_max_concurrency() -> None:
    rows = [_make_rpc_row(i) for i in range(3)]
    db = _make_db_mock(rows)
    llm = _make_llm_mock()

    with patch(
        "job_agent.agents.matcher_agent.ThreadPoolExecutor", wraps=ThreadPoolExecutor
    ) as mock_ex:
        agent = MatcherAgent(db=db, llm_agent=llm, max_concurrency=3)
        agent.run(PROFILE_ID, user_id=USER_ID, top_n=3)

    mock_ex.assert_called_once_with(max_workers=3)


def test_matcher_propagates_run_id_into_concurrent_obs_events() -> None:
    """copy_context() carries _current_run into workers -> events get the real
    run_id, never 'unknown'. Uses a real BaseAgent so ask_with_provider runs the
    real obs/contextvar path inside worker threads."""
    from job_agent.agents.base_agent import BaseAgent
    from job_agent.tools.observability_store import ObservabilityStore

    rows = [_make_rpc_row(i) for i in range(4)]
    db = _make_db_mock(rows)
    mock_chat = MagicMock()  # underlying chat model (not an LLMRouter)
    resp = MagicMock()
    resp.content = _valid_llm_json()
    resp.response_metadata = {}
    mock_chat.invoke.return_value = resp
    obs = MagicMock(spec=ObservabilityStore)
    real_agent = BaseAgent(llm=mock_chat, obs=obs)

    agent = MatcherAgent(db=db, llm_agent=real_agent, obs=obs, max_concurrency=4)
    result = agent.run(PROFILE_ID, user_id=USER_ID, top_n=4)

    assert result.scored == 4
    run_ids = {c.kwargs["run_id"] for c in obs.insert_llm_event.call_args_list}
    assert run_ids and "unknown" not in run_ids
