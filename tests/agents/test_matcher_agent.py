"""Tests for MatcherAgent (new profile_id-based API)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from job_agent.agents.matcher_agent import MatcherAgent, MatcherResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROFILE_ID = "00000000-0000-0000-0000-000000000001"


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

    # match_scores insert chain: db.raw.table("match_scores").insert(...).execute()
    insert_chain = MagicMock()
    insert_chain.return_value.execute.return_value = MagicMock(data=[{}])

    def _table(name: str) -> MagicMock:
        t = MagicMock()
        if name == "profile":
            t.select.return_value.eq.return_value.limit.return_value = profile_chain
        else:
            t.insert = insert_chain
        return t

    db.raw.table.side_effect = _table
    return db


def _make_llm_mock(responses: list[str] | None = None, default: str | None = None) -> MagicMock:
    llm = MagicMock()
    if responses is not None:
        llm.ask.side_effect = responses
    else:
        llm.ask.return_value = default or _valid_llm_json()
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
    result = agent.run(PROFILE_ID, top_n=5)

    assert isinstance(result, MatcherResult)
    assert result.candidates_considered == 10
    assert result.scored == 10
    assert result.persisted == 10
    assert result.errors == []

    # insert called once with 10 dicts each containing required keys
    table_calls = [c.args[0] for c in db.raw.table.call_args_list]
    assert "match_scores" in table_calls
    assert table_calls.count("match_scores") == 1
    insert_chain = db.raw.table.side_effect("match_scores").insert
    insert_call_args = insert_chain.call_args
    inserted_rows = insert_call_args[0][0]
    assert len(inserted_rows) == 10
    for row in inserted_rows:
        assert "job_id" in row
        assert "score" in row
        assert "gaps" in row
        assert "rationale" in row


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
    result = agent.run(PROFILE_ID, top_n=10)

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
    result = agent.run(PROFILE_ID, top_n=1)

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
    result = agent.run(PROFILE_ID)

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
    result = agent.run(PROFILE_ID, top_n=1)

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
    result = agent.run(PROFILE_ID, top_n=1)

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
    result = agent.run(PROFILE_ID, top_n=11)

    assert result.candidates_considered == 11
    assert result.scored == 0
    assert result.persisted == 0
    assert len(result.errors) == 10
