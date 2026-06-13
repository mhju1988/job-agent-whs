"""Tests for CoverLetterRenderer."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import jinja2
import pytest
from jinja2 import DictLoader, StrictUndefined

from job_agent.models.job import Job
from job_agent.models.profile import Profile
from job_agent.tools.cover_letter_template import (
    CoverLetterError,
    CoverLetterRenderer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(**kwargs: Any) -> Job:
    defaults: dict[str, Any] = {
        "source": "adzuna",
        "external_id": "job-001",
        "url": "https://example.com/job/1",
        "title": "Software Engineer",
        "company": "Acme Corp",
        "description": "Build great software.",
        "scraped_at": datetime(2025, 1, 1, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return Job(**defaults)


def _make_profile(**kwargs: Any) -> Profile:
    defaults: dict[str, Any] = {
        "summary": "Experienced developer.",
        "skills": ["Python", "SQL"],
    }
    defaults.update(kwargs)
    return Profile(**defaults)


def _valid_content_json() -> str:
    return json.dumps({
        "opening": "Dear Hiring Manager, I am thrilled to apply.",
        "body": "I have 5 years of Python experience.\nI love building scalable systems.",
        "closing": "I look forward to discussing this opportunity.",
    })


def _make_renderer(llm_response: str) -> tuple[CoverLetterRenderer, MagicMock]:
    mock_agent = MagicMock()
    mock_agent.ask.return_value = llm_response
    renderer = CoverLetterRenderer(llm_agent=mock_agent)
    return renderer, mock_agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_render_happy_path() -> None:
    renderer, _ = _make_renderer(_valid_content_json())
    job = _make_job()
    profile = _make_profile()

    result = renderer.render(
        candidate_name="Jane Doe",
        profile=profile,
        job=job,
        matched_skills=["Python", "SQL"],
        gaps_addressed=["Kubernetes", "Rust"],
    )

    assert "Jane Doe" in result
    assert "Software Engineer" in result
    assert "Acme Corp" in result
    assert "Dear Hiring Manager, I am thrilled to apply." in result
    assert "I have 5 years of Python experience." in result
    assert "I look forward to discussing this opportunity." in result
    assert "Python, SQL" in result
    assert "{{" not in result


def test_render_strips_json_fence() -> None:
    fenced = f"```json\n{_valid_content_json()}\n```"
    renderer, _ = _make_renderer(fenced)

    result = renderer.render(
        candidate_name="Jane Doe",
        profile=_make_profile(),
        job=_make_job(),
        matched_skills=["Python"],
    )

    assert "Dear Hiring Manager, I am thrilled to apply." in result
    assert "{{" not in result


def test_render_invalid_json_raises() -> None:
    renderer, _ = _make_renderer("not json at all")

    with pytest.raises(CoverLetterError, match="invalid JSON"):
        renderer.render(
            candidate_name="Jane Doe",
            profile=_make_profile(),
            job=_make_job(),
            matched_skills=["Python"],
        )


def test_render_invalid_schema_raises() -> None:
    # Valid JSON but missing required 'closing' field
    bad_json = json.dumps({"opening": "Hello", "body": "Body text"})
    renderer, _ = _make_renderer(bad_json)

    with pytest.raises(CoverLetterError) as exc_info:
        renderer.render(
            candidate_name="Jane Doe",
            profile=_make_profile(),
            job=_make_job(),
            matched_skills=["Python"],
        )

    # Should be chained to a ValidationError
    assert exc_info.value.__cause__ is not None


def test_render_empty_gaps_omits_section() -> None:
    renderer, _ = _make_renderer(_valid_content_json())

    result = renderer.render(
        candidate_name="Jane Doe",
        profile=_make_profile(),
        job=_make_job(),
        matched_skills=["Python"],
        gaps_addressed=None,
    )

    assert "Areas I am actively developing" not in result
    assert "{{" not in result


def test_render_unresolved_placeholder_raises() -> None:
    # Inject a broken template via DI that references an unknown variable
    broken_template = "Hello {{ candidate.name }} and {{ ghost }}"
    env = jinja2.Environment(
        loader=DictLoader({"cover_letter.jinja2": broken_template}),
        autoescape=False,
        undefined=StrictUndefined,
    )
    mock_agent = MagicMock()
    mock_agent.ask.return_value = _valid_content_json()
    renderer = CoverLetterRenderer(llm_agent=mock_agent, env=env)

    with pytest.raises(CoverLetterError):
        renderer.render(
            candidate_name="Jane Doe",
            profile=_make_profile(),
            job=_make_job(),
            matched_skills=["Python"],
        )


def test_render_passes_matched_skills_to_prompt() -> None:
    renderer, mock_agent = _make_renderer(_valid_content_json())
    skills = ["Python", "FastAPI", "Docker"]

    renderer.render(
        candidate_name="Jane Doe",
        profile=_make_profile(),
        job=_make_job(),
        matched_skills=skills,
    )

    call_args = mock_agent.ask.call_args
    assert call_args is not None
    # Use named-attribute access — robust if ask() ever switches to kwargs.
    prompt: str = call_args.args[0] if call_args.args else call_args.kwargs["prompt"]
    for skill in skills:
        assert skill in prompt


# ---------------------------------------------------------------------------
# Language support (task 4) — German template + LLM hint
# ---------------------------------------------------------------------------


def test_renderer_defaults_to_en() -> None:
    """No language arg → English template + no German LLM hint."""
    renderer, mock_agent = _make_renderer(_valid_content_json())
    rendered = renderer.render(
        candidate_name="Jane Doe",
        profile=_make_profile(),
        job=_make_job(),
        matched_skills=["Python"],
    )
    # English boilerplate from cover_letter.jinja2.
    assert "Subject:" in rendered
    assert "Betreff:" not in rendered
    # Prompt should NOT include the German hint.
    prompt = mock_agent.ask.call_args.args[0]
    assert "Write the cover letter in German." not in prompt


def test_renderer_loads_de_template() -> None:
    """language='de' → German template renders + LLM gets a German hint."""
    mock_agent = MagicMock()
    mock_agent.ask.return_value = _valid_content_json()
    renderer = CoverLetterRenderer(llm_agent=mock_agent, language="de")
    rendered = renderer.render(
        candidate_name="Max Mustermann",
        profile=_make_profile(),
        job=_make_job(),
        matched_skills=["Python"],
    )
    # German boilerplate is non-empty and used the de template.
    assert rendered.strip()
    assert "Betreff:" in rendered
    assert "Sehr geehrte Damen und Herren" in rendered
    assert "Mit freundlichen Grüßen" in rendered
    # Prompt carries the German hint.
    prompt = mock_agent.ask.call_args.args[0]
    assert "Write the cover letter in German." in prompt


def test_renderer_rejects_unknown_language() -> None:
    """Invalid language value raises CoverLetterError at construction."""
    with pytest.raises(CoverLetterError, match="unsupported language"):
        CoverLetterRenderer(llm_agent=MagicMock(), language="fr")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Signature block — profile.full_name drives the closing signature
# ---------------------------------------------------------------------------


def test_en_template_signature_uses_profile_full_name() -> None:
    """profile.full_name non-None → rendered EN letter signs with that name."""
    renderer, _ = _make_renderer(_valid_content_json())
    rendered = renderer.render(
        candidate_name="John Doe",
        profile=_make_profile(full_name="Max Mustermann"),
        job=_make_job(),
        matched_skills=["Python"],
    )
    assert "Sincerely," in rendered
    assert "Max Mustermann" in rendered


def test_en_template_signature_falls_back_to_your_name() -> None:
    """profile.full_name=None → EN signature falls back to 'Your Name'."""
    renderer, _ = _make_renderer(_valid_content_json())
    rendered = renderer.render(
        candidate_name="John Doe",
        profile=_make_profile(full_name=None),
        job=_make_job(),
        matched_skills=["Python"],
    )
    assert "Sincerely," in rendered
    assert "Your Name" in rendered


def test_de_template_signature_uses_profile_full_name() -> None:
    """profile.full_name non-None → rendered DE letter signs with that name."""
    mock_agent = MagicMock()
    mock_agent.ask.return_value = _valid_content_json()
    renderer = CoverLetterRenderer(llm_agent=mock_agent, language="de")
    rendered = renderer.render(
        candidate_name="John Doe",
        profile=_make_profile(full_name="Max Mustermann"),
        job=_make_job(),
        matched_skills=["Python"],
    )
    assert "Mit freundlichen Grüßen" in rendered
    assert "Max Mustermann" in rendered


def test_de_template_signature_falls_back_to_ihr_name() -> None:
    """profile.full_name=None → DE signature falls back to 'Ihr Name' (not 'Your Name')."""
    mock_agent = MagicMock()
    mock_agent.ask.return_value = _valid_content_json()
    renderer = CoverLetterRenderer(llm_agent=mock_agent, language="de")
    rendered = renderer.render(
        candidate_name="John Doe",
        profile=_make_profile(full_name=None),
        job=_make_job(),
        matched_skills=["Python"],
    )
    assert "Mit freundlichen Grüßen" in rendered
    assert "Ihr Name" in rendered
    # Defensive: the English fallback must NOT leak into the DE template.
    assert "Your Name" not in rendered
