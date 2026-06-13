"""Tests for CVParser tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from job_agent.models.profile import Profile
from job_agent.tools.cv_parser import CVParseError, CVParser


def _make_reader(pages_text: list[str]) -> MagicMock:
    """Build a fake PdfReader whose .pages list returns the given text per page."""
    reader = MagicMock()
    pages = []
    for text in pages_text:
        page = MagicMock()
        page.extract_text.return_value = text
        pages.append(page)
    reader.pages = pages
    return reader


def _valid_profile_json() -> str:
    return json.dumps(
        {
            "full_name": "Jane Doe",
            "summary": "Experienced developer.",
            "skills": ["Python", "FastAPI"],
            "experience": [
                {
                    "title": "Backend Developer",
                    "company": "Tech AG",
                    "start": "2020-01",
                    "end": None,
                    "description": "Built APIs.",
                }
            ],
            "education": [
                {
                    "degree": "B.Sc.",
                    "institution": "FH Köln",
                    "field": "Informatik",
                    "start": "2015",
                    "end": "2018",
                }
            ],
            "languages": ["German", "English"],
        }
    )


def test_parse_happy_path() -> None:
    fake_reader = _make_reader(["Page one text.", "Page two text."])
    mock_agent = MagicMock()
    mock_agent.ask.return_value = _valid_profile_json()

    parser = CVParser(
        llm_agent=mock_agent,
        pdf_reader_factory=lambda _path: fake_reader,
    )
    profile = parser.parse(Path("dummy.pdf"))

    assert isinstance(profile, Profile)
    assert profile.summary == "Experienced developer."
    assert "Python" in profile.skills
    assert len(profile.experience) == 1
    assert profile.experience[0].title == "Backend Developer"
    assert len(profile.education) == 1
    assert "German" in profile.languages


def test_parse_strips_json_code_fence() -> None:
    fake_reader = _make_reader(["Some CV text."])
    mock_agent = MagicMock()
    mock_agent.ask.return_value = f"```json\n{_valid_profile_json()}\n```"

    parser = CVParser(
        llm_agent=mock_agent,
        pdf_reader_factory=lambda _path: fake_reader,
    )
    profile = parser.parse(Path("dummy.pdf"))
    assert isinstance(profile, Profile)
    assert profile.summary == "Experienced developer."


def test_parse_strips_plain_code_fence() -> None:
    """LLMs sometimes emit a plain ``` fence with no language tag."""
    fake_reader = _make_reader(["Some CV text."])
    mock_agent = MagicMock()
    mock_agent.ask.return_value = f"```\n{_valid_profile_json()}\n```"

    parser = CVParser(
        llm_agent=mock_agent,
        pdf_reader_factory=lambda _path: fake_reader,
    )
    profile = parser.parse(Path("dummy.pdf"))
    assert isinstance(profile, Profile)
    assert profile.summary == "Experienced developer."


def test_parse_tolerates_literal_control_char_in_llm_json() -> None:
    # German CVs often yield LLM JSON with a LITERAL newline inside a string
    # value (e.g. a multi-line summary) instead of an escaped "\\n". Default
    # json.loads (strict=True) rejects it as "Invalid control character".
    raw = (
        '{"full_name": "Max Mustermann", '
        '"summary": "Erfahrener Entwickler.\n'
        'Schwerpunkt Backend.", '
        '"skills": ["Python", "SQL"], '
        '"experience": [], "education": [], '
        '"languages": ["German"]}'
    )
    assert "\n" in raw  # guard: reproduction needs a real control char
    fake_reader = _make_reader(["CV page text."])
    mock_agent = MagicMock()
    mock_agent.ask.return_value = raw

    parser = CVParser(
        llm_agent=mock_agent,
        pdf_reader_factory=lambda _path: fake_reader,
    )
    profile = parser.parse(Path("dummy.pdf"))

    assert profile.summary is not None
    assert profile.summary.startswith("Erfahrener Entwickler.")
    assert "Python" in profile.skills


def test_parse_empty_pdf_raises() -> None:
    fake_reader = _make_reader(["", ""])
    mock_agent = MagicMock()

    parser = CVParser(
        llm_agent=mock_agent,
        pdf_reader_factory=lambda _path: fake_reader,
    )
    with pytest.raises(CVParseError, match="no text extracted"):
        parser.parse(Path("empty.pdf"))

    mock_agent.ask.assert_not_called()


def test_parse_invalid_json_raises() -> None:
    fake_reader = _make_reader(["Some text on the page."])
    mock_agent = MagicMock()
    mock_agent.ask.return_value = "not json at all"

    parser = CVParser(
        llm_agent=mock_agent,
        pdf_reader_factory=lambda _path: fake_reader,
    )
    with pytest.raises(CVParseError, match="invalid JSON"):
        parser.parse(Path("dummy.pdf"))


def test_parse_invalid_schema_raises() -> None:
    # skills should be a list, not a string
    bad_json = json.dumps(
        {
            "summary": "Dev",
            "skills": "python",  # wrong type
            "experience": [],
            "education": [],
            "languages": [],
        }
    )
    fake_reader = _make_reader(["CV page text."])
    mock_agent = MagicMock()
    mock_agent.ask.return_value = bad_json

    parser = CVParser(
        llm_agent=mock_agent,
        pdf_reader_factory=lambda _path: fake_reader,
    )
    with pytest.raises(CVParseError, match="schema"):
        parser.parse(Path("dummy.pdf"))
