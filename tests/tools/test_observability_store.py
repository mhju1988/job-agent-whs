"""Tests for ObservabilityStore — Supabase client is mocked."""
from datetime import UTC, datetime
from unittest.mock import MagicMock

from job_agent.tools.observability_store import ObservabilityStore
from job_agent.tools.run_context import RunContext

# Cost reference rates (must match implementation)
_PROMPT_RATE = 0.0006 / 1000
_COMPLETION_RATE = 0.0009 / 1000


def _make_ctx(agent: str = "matcher") -> RunContext:
    return RunContext(
        run_id="test-run-uuid",
        agent_name=agent,
        started_at=datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC),
    )


def test_insert_run_writes_correct_row() -> None:
    mock_db = MagicMock()
    store = ObservabilityStore(db=mock_db)
    ctx = _make_ctx("scout")

    store.insert_run(ctx)

    mock_db.raw.table.assert_called_with("agent_runs")
    insert_call = mock_db.raw.table.return_value.insert.call_args
    row = insert_call[0][0]
    assert row["run_id"] == "test-run-uuid"
    assert row["agent_name"] == "scout"
    assert row["status"] == "running"


def test_finish_run_updates_correct_fields() -> None:
    mock_db = MagicMock()
    store = ObservabilityStore(db=mock_db)

    store.finish_run("test-run-uuid", "success")

    update_call = mock_db.raw.table.return_value.update.call_args
    payload = update_call[0][0]
    assert payload["status"] == "success"
    assert "finished_at" in payload
    assert payload["error_message"] is None


def test_finish_run_stores_error_message() -> None:
    mock_db = MagicMock()
    store = ObservabilityStore(db=mock_db)

    store.finish_run("test-run-uuid", "error", "something went wrong")

    update_call = mock_db.raw.table.return_value.update.call_args
    payload = update_call[0][0]
    assert payload["status"] == "error"
    assert payload["error_message"] == "something went wrong"


def test_insert_llm_event_computes_cost() -> None:
    mock_db = MagicMock()
    store = ObservabilityStore(db=mock_db)

    store.insert_llm_event(
        run_id="test-run-uuid",
        prompt_snippet="hello",
        response_snippet="world",
        prompt_tokens=1000,
        completion_tokens=500,
        duration_ms=120,
    )

    insert_call = mock_db.raw.table.return_value.insert.call_args
    row = insert_call[0][0]
    assert row["run_id"] == "test-run-uuid"
    assert row["prompt_tokens"] == 1000
    assert row["completion_tokens"] == 500
    expected_cost = 1000 * _PROMPT_RATE + 500 * _COMPLETION_RATE
    assert abs(row["estimated_cost_eur"] - expected_cost) < 1e-9


def test_insert_llm_event_handles_none_tokens() -> None:
    mock_db = MagicMock()
    store = ObservabilityStore(db=mock_db)

    store.insert_llm_event(
        run_id="test-run-uuid",
        prompt_snippet="x",
        response_snippet="y",
        prompt_tokens=None,
        completion_tokens=None,
        duration_ms=50,
    )

    insert_call = mock_db.raw.table.return_value.insert.call_args
    row = insert_call[0][0]
    assert row["prompt_tokens"] is None
    assert row["estimated_cost_eur"] is None
