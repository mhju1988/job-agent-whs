"""Tests for job_agent.services.profile_service — no live calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from job_agent.models.profile import Profile
from job_agent.services.profile_service import ProfileSaveResult, save_profile_from_pdf

USER_ID = "00000000-0000-0000-0000-0000000000aa"


def _fake_profile() -> Profile:
    return Profile(summary="x", skills=["Python"], experience=[], education=[], languages=[])


def test_save_profile_deletes_only_this_user_then_inserts_with_user_id() -> None:
    db = MagicMock()
    parser = MagicMock()
    parser.parse_bytes.return_value = _fake_profile()
    embedder = MagicMock()
    embedder.embed_text.return_value = [0.0] * 1024

    result = save_profile_from_pdf(
        b"%PDF-fake",
        db=db,
        user_id=USER_ID,
        parser=parser,
        embedder=embedder,
        rescore=False,
        suggest=False,
    )

    # delete is scoped to the user (no table wipe)
    delete_eq = db.raw.table.return_value.delete.return_value.eq
    assert ("user_id", USER_ID) in [c.args for c in delete_eq.call_args_list]
    # inserted row carries user_id + embedding
    inserted = db.raw.table.return_value.insert.call_args.args[0]
    assert inserted["user_id"] == USER_ID
    assert inserted["embedding"] == [0.0] * 1024
    assert isinstance(result, ProfileSaveResult)
    assert result.ok is True


def test_save_profile_surfaces_parse_error() -> None:
    from job_agent.tools.cv_parser import CVParseError

    db = MagicMock()
    parser = MagicMock()
    parser.parse_bytes.side_effect = CVParseError("bad pdf")
    embedder = MagicMock()

    result = save_profile_from_pdf(
        b"not a pdf",
        db=db,
        user_id=USER_ID,
        parser=parser,
        embedder=embedder,
        rescore=False,
        suggest=False,
    )

    assert result.ok is False
    assert result.error is not None
    assert "CV parse failed" in result.error
    # Nothing persisted on parse failure.
    db.raw.table.return_value.insert.assert_not_called()


def test_save_profile_populates_suggested_searches() -> None:
    """After saving, suggested_searches is written back into the profile row."""
    from job_agent.tools.search_suggester import SearchSuggestion

    db = MagicMock()
    parser = MagicMock()
    parser.parse_bytes.return_value = _fake_profile()
    embedder = MagicMock()
    embedder.embed_text.return_value = [0.0] * 1024

    fake_suggestions = [SearchSuggestion(keyword="Python Dev", location="Berlin")]

    with patch(
        "job_agent.services.profile_service.SearchSuggester"
    ) as mock_suggester:
        mock_suggester.return_value.suggest.return_value = fake_suggestions
        result = save_profile_from_pdf(
            b"%PDF-fake",
            db=db,
            user_id=USER_ID,
            parser=parser,
            embedder=embedder,
            rescore=False,
        )

    assert result.ok is True
    # The profile row must have been updated with the serialised suggestions.
    update_call = db.raw.table.return_value.update.call_args
    assert update_call is not None
    payload = update_call.args[0]
    assert "suggested_searches" in payload
    assert payload["suggested_searches"] == [{"keyword": "Python Dev", "location": "Berlin"}]
    eq_calls = [c.args for c in db.raw.table.return_value.update.return_value.eq.call_args_list]
    assert ("user_id", USER_ID) in eq_calls


def test_save_profile_suggest_false_skips_llm() -> None:
    """suggest=False must not call SearchSuggester."""
    db = MagicMock()
    parser = MagicMock()
    parser.parse_bytes.return_value = _fake_profile()
    embedder = MagicMock()
    embedder.embed_text.return_value = [0.0] * 1024

    with patch(
        "job_agent.services.profile_service.SearchSuggester"
    ) as mock_suggester:
        save_profile_from_pdf(
            b"%PDF-fake",
            db=db,
            user_id=USER_ID,
            parser=parser,
            embedder=embedder,
            rescore=False,
            suggest=False,
        )

    mock_suggester.assert_not_called()
