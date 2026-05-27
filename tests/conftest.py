"""Shared pytest fixtures."""

import pytest

from job_agent.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Reset the @lru_cache on get_settings before every test.

    Prevents cross-test leakage of real .env values when one test reads
    settings and another asserts on empty defaults.
    """
    get_settings.cache_clear()
