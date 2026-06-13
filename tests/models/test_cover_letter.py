"""Tests for CoverLetterContent pydantic model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from job_agent.models.cover_letter import CoverLetterContent


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        CoverLetterContent(
            opening="Hello",
            body="Body text",
            closing="Regards",
            extra_field="forbidden",  # type: ignore[call-arg]
        )


def test_required_fields() -> None:
    # Missing 'closing' should raise
    with pytest.raises(ValidationError):
        CoverLetterContent(opening="Hello", body="Body text")  # type: ignore[call-arg]

    # Missing 'opening' should raise
    with pytest.raises(ValidationError):
        CoverLetterContent(body="Body text", closing="Regards")  # type: ignore[call-arg]

    # Missing 'body' should raise
    with pytest.raises(ValidationError):
        CoverLetterContent(opening="Hello", closing="Regards")  # type: ignore[call-arg]


def test_round_trip() -> None:
    data = {"opening": "Dear Hiring Manager,", "body": "I am excited...", "closing": "Best regards"}
    content = CoverLetterContent.model_validate(data)
    assert content.opening == data["opening"]
    assert content.body == data["body"]
    assert content.closing == data["closing"]
    dumped = content.model_dump()
    assert dumped == data
    # Re-validate dumped output to ensure full round-trip integrity.
    assert CoverLetterContent.model_validate(dumped).model_dump() == data
