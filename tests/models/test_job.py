"""Tests for src/job_agent/models/job.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from job_agent.models.job import Job


def _make_job(**overrides: object) -> Job:
    defaults: dict = {
        "source": "arbeitsagentur",
        "external_id": "abc123",
        "url": "https://example.com/job/abc123",
        "title": "Software Engineer",
    }
    defaults.update(overrides)
    return Job(**defaults)  # type: ignore[arg-type]


def test_job_round_trip() -> None:
    job = _make_job(
        company="Acme GmbH",
        location="Berlin, 10115",
        requirements=["Python", "SQL"],
        description="Great job",
    )
    row = job.to_supabase_row()

    # All non-embedding columns from 001_init.sql must be present
    expected_keys = {
        "source",
        "external_id",
        "url",
        "title",
        "company",
        "location",
        "requirements",
        "description",
        "scraped_at",
    }
    assert expected_keys == set(row.keys())

    # scraped_at must be an ISO 8601 string (not a datetime object)
    assert isinstance(row["scraped_at"], str)
    # Must be parseable
    from datetime import datetime

    datetime.fromisoformat(row["scraped_at"])

    assert row["source"] == "arbeitsagentur"
    assert row["requirements"] == ["Python", "SQL"]


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        _make_job(foo="bar")  # type: ignore[call-overload]


def test_source_literal_enforced() -> None:
    with pytest.raises(ValidationError):
        _make_job(source="indeed")


def test_to_embedding_text_combines_all_fields() -> None:
    """Embedding text joins title → company → requirements → description so the
    job lives in the same embedding space as profiles."""
    job = _make_job(
        company="Acme GmbH",
        requirements=["Python", "SQL"],
        description="Build data pipelines.",
    )
    text = job.to_embedding_text()
    assert "Software Engineer" in text
    assert "Acme GmbH" in text
    assert "Python" in text and "SQL" in text
    assert "Build data pipelines." in text


def test_to_embedding_text_omits_empty_fields() -> None:
    """Missing optional fields don't leave blank lines in the embedding text."""
    job = _make_job()  # title only; no company/requirements/description
    assert job.to_embedding_text() == "Software Engineer"
