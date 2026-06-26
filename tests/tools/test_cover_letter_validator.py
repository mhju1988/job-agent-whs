"""Tests for the cover-letter content validator."""

from __future__ import annotations

from job_agent.models.cover_letter import CoverLetterContent
from job_agent.tools.cover_letter_validator import LetterIssue, passes, validate_letter


def _content(
    *,
    opening: str = "Dear Hiring Manager, I am excited to apply today.",
    body: str = (
        "I have five years of Python experience and have built several "
        "scalable backend services that serve thousands of users reliably."
    ),
    closing: str = "I look forward to discussing this role with you.",
) -> CoverLetterContent:
    return CoverLetterContent(opening=opening, body=body, closing=closing)


def test_valid_content_passes() -> None:
    assert validate_letter(_content()) == []
    assert passes(_content())


def test_banned_phrase_is_flagged_case_insensitively() -> None:
    content = _content(
        body=(
            "I am writing to apply for this role because I have years of "
            "Python experience building reliable backend services at scale."
        )
    )
    issues = validate_letter(content)
    codes = [i.code for i in issues]
    assert "banned_phrase" in codes
    assert not passes(content)


def test_body_too_short_is_flagged() -> None:
    content = _content(body="I know Python well.")
    issues = validate_letter(content)
    assert any(i.code == "body_too_short" for i in issues)


def test_body_too_long_is_flagged() -> None:
    long_body = " ".join(["word"] * 500)
    content = _content(body=long_body)
    issues = validate_letter(content)
    assert any(i.code == "body_too_long" for i in issues)


def test_opening_too_short_is_flagged() -> None:
    content = _content(opening="Hi.")
    issues = validate_letter(content)
    assert any(i.code == "opening_too_short" for i in issues)


def test_closing_too_short_is_flagged() -> None:
    content = _content(closing="Bye")
    # "Bye" is one word → below the 2-word minimum
    issues = validate_letter(content)
    assert any(i.code == "closing_too_short" for i in issues)


def test_german_language_mismatch_is_flagged() -> None:
    # English text submitted under language='de' → flagged
    issues = validate_letter(_content(), language="de")
    assert any(i.code == "language_mismatch" for i in issues)


def test_german_language_match_passes() -> None:
    de_content = CoverLetterContent(
        opening="Sehr geehrte Damen und Herren, ich bewerbe mich hiermit um die Stelle.",
        body=(
            "Ich habe viele Jahre Erfahrung mit Python und habe mehrere "
            "skalierbare Backend-Systeme erfolgreich bei großen Firmen gebaut."
        ),
        closing="Ich freue mich auf Ihre Rückmeldung und stehe gerne zur Verfügung.",
    )
    assert validate_letter(de_content, language="de") == []


def test_issue_message_is_human_readable() -> None:
    issue = LetterIssue(code="banned_phrase", message="contains stock phrase: 'x'")
    assert str(issue) == "[banned_phrase] contains stock phrase: 'x'"


def test_validator_returns_list_of_letter_issues() -> None:
    content = _content(body="short")
    issues = validate_letter(content)
    assert all(isinstance(i, LetterIssue) for i in issues)
