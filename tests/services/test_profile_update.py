"""Tests for update_profile_fields (partial profile edit + re-embed)."""

from __future__ import annotations

from unittest.mock import MagicMock

from job_agent.services.profile_service import update_profile_fields
from job_agent.tools.embedder import EmbeddingServiceError

USER = "u-1"


def _db_with_profile() -> MagicMock:
    db = MagicMock()
    chain = db.raw.table.return_value.select.return_value.eq.return_value.limit.return_value
    chain.execute.return_value.data = [
        {
            "full_name": "A",
            "summary": "old",
            "skills": ["Python"],
            "experience": [],
            "education": [],
            "languages": ["EN"],
        }
    ]
    return db


def test_skills_only_reembeds_and_updates() -> None:
    db = _db_with_profile()
    emb = MagicMock()
    emb.embed_text.return_value = [0.1] * 1024

    res = update_profile_fields(db, USER, skills=["Python", "SQL"], embedder=emb)

    assert res.ok and res.profile is not None
    assert res.profile["skills"] == ["Python", "SQL"]
    # embedding text reflects the NEW skills
    assert "SQL" in emb.embed_text.call_args.args[0]
    # update payload carries skills + embedding, NOT summary
    payload = db.raw.table.return_value.update.call_args.args[0]
    assert payload["skills"] == ["Python", "SQL"] and "embedding" in payload
    assert "summary" not in payload


def test_summary_only_updates_summary_not_skills() -> None:
    db = _db_with_profile()
    emb = MagicMock()
    emb.embed_text.return_value = [0.1] * 1024

    res = update_profile_fields(db, USER, summary="new summary", embedder=emb)

    assert res.ok
    payload = db.raw.table.return_value.update.call_args.args[0]
    assert payload["summary"] == "new summary" and "skills" not in payload


def test_no_profile_returns_error_and_no_write() -> None:
    db = MagicMock()
    chain = db.raw.table.return_value.select.return_value.eq.return_value.limit.return_value
    chain.execute.return_value.data = []
    emb = MagicMock()

    res = update_profile_fields(db, USER, skills=["X"], embedder=emb)

    assert res.ok is False and res.error == "no profile"
    db.raw.table.return_value.update.assert_not_called()
    emb.embed_text.assert_not_called()


def test_embed_failure_returns_error_and_no_write() -> None:
    db = _db_with_profile()
    emb = MagicMock()
    emb.embed_text.side_effect = EmbeddingServiceError("gwdg down")

    res = update_profile_fields(db, USER, skills=["X"], embedder=emb)

    assert res.ok is False and res.error is not None
    db.raw.table.return_value.update.assert_not_called()
