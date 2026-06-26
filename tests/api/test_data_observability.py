"""Tests for the data-deletion + observability routers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from job_agent.agents.tracker_agent import DeleteSummary
from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.main import create_app


def _client(db: MagicMock) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("u-1", "t")
    app.dependency_overrides[get_user_db] = lambda: db
    return TestClient(app)


def test_delete_my_data_calls_tracker_with_user_id() -> None:
    db = MagicMock()
    tracker = MagicMock()
    tracker.delete_my_data.return_value = DeleteSummary(
        profiles_deleted=1, matches_deleted=2, applications_deleted=3, files_deleted=4
    )
    with patch("job_agent.api.routers.data.TrackerAgent", return_value=tracker):
        r = _client(db).post("/api/data/delete")
    assert r.status_code == 200
    assert r.json()["applications_deleted"] == 3
    tracker.delete_my_data.assert_called_once_with(user_id="u-1")


def test_observability_runs_and_events() -> None:
    db = MagicMock()
    store = MagicMock()
    store.fetch_runs.return_value = [{"run_id": "r1", "agent_name": "matcher"}]
    store.fetch_events_for_run.return_value = [{"prompt_tokens": 10}]
    with patch("job_agent.api.routers.observability.ObservabilityStore", return_value=store):
        client = _client(db)
        runs = client.get("/api/observability/runs")
        events = client.get("/api/observability/runs/r1/events")
    assert runs.status_code == 200
    assert runs.json()[0]["run_id"] == "r1"
    assert events.json()[0]["prompt_tokens"] == 10
