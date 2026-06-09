"""Tests for the Profile pydantic model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from job_agent.models.profile import Education, Experience, Profile


def _full_profile() -> Profile:
    return Profile(
        full_name="Jane Doe",
        summary="Senior engineer with 10 years experience.",
        skills=["Python", "SQL", "Docker"],
        experience=[
            Experience(
                title="Software Engineer",
                company="Acme GmbH",
                start="2019-01",
                end="2023-06",
                description="Built microservices.",
            )
        ],
        education=[
            Education(
                degree="M.Sc.",
                institution="TU Berlin",
                field="Computer Science",
                start="2015",
                end="2017",
            )
        ],
        languages=["English", "German"],
    )


def test_profile_round_trip() -> None:
    profile = _full_profile()
    row = profile.to_supabase_row()

    # Must contain exactly the profile table columns (no embedding/created_at/updated_at)
    assert set(row.keys()) == {
        "full_name",
        "summary",
        "skills",
        "experience",
        "education",
        "languages",
    }

    assert row["full_name"] == "Jane Doe"
    assert row["summary"] == profile.summary
    assert row["skills"] == ["Python", "SQL", "Docker"]
    assert row["languages"] == ["English", "German"]

    # experience and education must be JSON-safe dicts
    assert isinstance(row["experience"], list)
    assert isinstance(row["experience"][0], dict)
    assert row["experience"][0]["title"] == "Software Engineer"
    assert row["experience"][0]["company"] == "Acme GmbH"

    assert isinstance(row["education"], list)
    assert row["education"][0]["degree"] == "M.Sc."
    assert row["education"][0]["institution"] == "TU Berlin"


def test_extra_fields_forbidden() -> None:
    # `# type: ignore[call-arg]` is intentional: we are deliberately passing an
    # undeclared kwarg to verify pydantic rejects it at runtime.
    with pytest.raises(ValidationError):
        Profile(summary="x", unknown_field="oops")  # type: ignore[call-arg]


def test_extra_fields_forbidden_on_experience() -> None:
    """Sub-models must also forbid extras (LLM may inject keys like 'location')."""
    with pytest.raises(ValidationError):
        Experience(title="t", company="c", location="Berlin")  # type: ignore[call-arg]


def test_extra_fields_forbidden_on_education() -> None:
    with pytest.raises(ValidationError):
        Education(degree="d", institution="i", gpa="4.0")  # type: ignore[call-arg]


def test_highlighted_skills_default_empty() -> None:
    """Profile() must initialise highlighted_skills to an empty list."""
    profile = Profile()
    assert profile.highlighted_skills == []


def test_to_supabase_row_excludes_highlighted_skills() -> None:
    """highlighted_skills must not be persisted — no such column in the DB."""
    profile = Profile(skills=["Python"], highlighted_skills=["Python"])
    row = profile.to_supabase_row()
    assert "highlighted_skills" not in row


def test_to_embedding_text_does_not_double_count_highlighted_skills() -> None:
    """When a skill appears in both `skills` and `highlighted_skills`, the
    embedding text must contain it exactly once — `highlighted_skills` is a
    presentation-only field and must NOT be appended to the embedding input."""
    profile = Profile(skills=["Python"], highlighted_skills=["Python"])
    text = profile.to_embedding_text()
    assert text.lower().count("python") == 1


def test_to_embedding_text_includes_all_sections() -> None:
    profile = _full_profile()
    text = profile.to_embedding_text()

    assert "Senior engineer" in text
    assert "Python" in text
    assert "SQL" in text
    assert "Software Engineer" in text
    assert "Acme GmbH" in text
    assert "Built microservices" in text
    assert "M.Sc." in text
    assert "TU Berlin" in text
    assert "Computer Science" in text
    assert "English" in text
    assert "German" in text


def test_full_name_in_row_but_not_in_embedding_text() -> None:
    """``full_name`` persists to Supabase but must never influence semantic
    similarity (names should not bias score ranking)."""
    profile = Profile(full_name="Jane Doe", skills=["Python"])
    row = profile.to_supabase_row()
    text = profile.to_embedding_text()

    assert row["full_name"] == "Jane Doe"
    assert "Jane" not in text
    assert "Doe" not in text


def test_full_name_defaults_to_none() -> None:
    """``full_name`` is optional — Profile() with no args leaves it None."""
    assert Profile().full_name is None
