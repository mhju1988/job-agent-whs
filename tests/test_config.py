"""Smoke tests for settings loading. No live API calls."""

import pytest

from job_agent.config import MissingCredentialsError, Settings, get_settings


def test_settings_load_with_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    s = Settings()
    assert s.gwdg_api_base.startswith("https://")
    assert s.gwdg_model
    assert s.log_level == "INFO"


def test_secret_fields_empty_by_default(monkeypatch, tmp_path):
    """Guards against accidentally reading a real .env at the repo root."""
    monkeypatch.chdir(tmp_path)
    # Process env beats the .env file in pydantic-settings, and the project's
    # config.py now anchors .env to the repo root by absolute path — so the
    # chdir trick alone no longer hides real creds. Clear them explicitly.
    for var in ("GWDG_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"):
        monkeypatch.setenv(var, "")
    s = Settings()
    assert s.gwdg_api_key == ""
    assert s.supabase_url == ""
    assert s.supabase_key == ""


def test_require_live_credentials_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for var in ("GWDG_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"):
        monkeypatch.setenv(var, "")
    s = Settings()
    with pytest.raises(MissingCredentialsError):
        s.require_live_credentials()


def test_get_settings_returns_settings_instance(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    assert isinstance(get_settings(), Settings)
