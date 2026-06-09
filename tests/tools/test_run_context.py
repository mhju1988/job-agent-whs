"""Tests for RunContext — no I/O, pure in-process logic."""
from datetime import timezone

from job_agent.tools.run_context import RunContext, get_current_run, start_run


def test_start_run_sets_context() -> None:
    ctx = start_run("matcher")
    assert get_current_run() is ctx
    assert ctx.agent_name == "matcher"
    assert ctx.started_at.tzinfo == timezone.utc


def test_start_run_generates_unique_run_ids() -> None:
    ctx1 = start_run("scout")
    ctx2 = start_run("writer")
    assert ctx1.run_id != ctx2.run_id


def test_get_current_run_returns_none_with_no_active_run() -> None:
    from contextvars import copy_context

    def _check() -> None:
        # Fresh context — no run started
        assert get_current_run() is None

    copy_context().run(_check)


def test_run_context_has_expected_fields() -> None:
    ctx = start_run("tracker")
    assert isinstance(ctx.run_id, str)
    assert len(ctx.run_id) == 36  # UUID format
