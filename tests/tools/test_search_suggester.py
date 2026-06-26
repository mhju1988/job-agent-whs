"""Tests for SearchSuggester — mocked LLM, no live calls."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from job_agent.tools.search_suggester import SearchSuggester


def _llm(response: str) -> MagicMock:
    m = MagicMock()
    m.ask.return_value = response
    return m


def test_suggest_parses_ordered_list() -> None:
    resp = json.dumps(
        [
            {"keyword": "Backend Python Developer", "location": "Berlin", "rationale": "x"},
            {"keyword": "Data Engineer"},
        ]
    )
    out = SearchSuggester(llm_agent=_llm(resp)).suggest("candidate brief")
    assert [s.keyword for s in out] == ["Backend Python Developer", "Data Engineer"]
    assert out[0].location == "Berlin"


def test_suggest_filters_empty_then_caps() -> None:
    resp = json.dumps(
        [{"keyword": "A"}, {"keyword": "   "}, {"keyword": "B"}, {"keyword": "C"}]
    )
    out = SearchSuggester(llm_agent=_llm(resp)).suggest("c", max_suggestions=2)
    assert [s.keyword for s in out] == ["A", "B"]


def test_suggest_handles_fenced_json() -> None:
    resp = '```json\n[{"keyword": "Cloud Engineer"}]\n```'
    out = SearchSuggester(llm_agent=_llm(resp)).suggest("c")
    assert [s.keyword for s in out] == ["Cloud Engineer"]


def test_suggest_tolerates_trailing_prose() -> None:
    # apertus-70b often appends commentary after the JSON → "Extra data".
    resp = (
        '[{"keyword": "Backend Python Developer"}]\n\n'
        "These roles best match the candidate's Python and SQL experience."
    )
    out = SearchSuggester(llm_agent=_llm(resp)).suggest("c")
    assert [s.keyword for s in out] == ["Backend Python Developer"]


def test_suggest_tolerates_leading_prose() -> None:
    resp = 'Here are my suggestions:\n[{"keyword": "Data Engineer"}]'
    out = SearchSuggester(llm_agent=_llm(resp)).suggest("c")
    assert [s.keyword for s in out] == ["Data Engineer"]


def test_suggest_returns_empty_on_bad_json() -> None:
    assert SearchSuggester(llm_agent=_llm("not json at all")).suggest("c") == []


def test_suggest_returns_empty_on_llm_failure() -> None:
    llm = MagicMock()
    llm.ask.side_effect = RuntimeError("endpoint down")
    assert SearchSuggester(llm_agent=llm).suggest("c") == []
