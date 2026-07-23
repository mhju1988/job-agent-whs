"""Tests for the hidden_jobs service helper."""

from __future__ import annotations

from unittest.mock import MagicMock

from job_agent.services.hidden_jobs import fetch_hidden_job_ids


def test_fetch_hidden_job_ids_returns_set() -> None:
    db = MagicMock()
    chain = db.raw.table.return_value.select.return_value
    chain.execute.return_value.data = [{"job_id": "j1"}, {"job_id": "j2"}]
    assert fetch_hidden_job_ids(db) == {"j1", "j2"}
    db.raw.table.assert_called_with("hidden_jobs")


def test_fetch_hidden_job_ids_empty() -> None:
    db = MagicMock()
    db.raw.table.return_value.select.return_value.execute.return_value.data = []
    assert fetch_hidden_job_ids(db) == set()


def test_fetch_hidden_job_ids_none_data() -> None:
    db = MagicMock()
    db.raw.table.return_value.select.return_value.execute.return_value.data = None
    assert fetch_hidden_job_ids(db) == set()
