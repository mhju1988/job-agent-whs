"""Fixtures for tools tests."""

import pytest

from job_agent.tools.run_context import _current_run


@pytest.fixture(autouse=True)
def _reset_run_context() -> None:
    """Reset the RunContext ContextVar to None before every test.

    Prevents cross-test leakage where a previous test's start_run call
    pollutes the ambient context for copy_context() calls.
    """
    _current_run.set(None)
