"""Tests for SupabaseClient — no live DB calls."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from job_agent.config import MissingCredentialsError, Settings
from job_agent.db.client import SupabaseClient


def test_raw_returns_injected_client() -> None:
    """Injected client is exposed unchanged via `.raw`."""
    mock_client: MagicMock = MagicMock()
    sc = SupabaseClient(client=mock_client)
    assert sc.raw is mock_client


def test_raises_when_credentials_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing credentials cause MissingCredentialsError on construction."""
    monkeypatch.chdir(tmp_path)  # prevent any .env file from being found
    settings = Settings(supabase_url="", supabase_key="", gwdg_api_key="")
    with pytest.raises(MissingCredentialsError):
        SupabaseClient(settings=settings)


def test_create_client_called_with_settings_values() -> None:
    """create_client is called with the URL and key from Settings."""
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_key="test-key-abc",
        gwdg_api_key="gwdg-key-xyz",
    )
    fake_client = MagicMock()
    with patch("job_agent.db.client.create_client", return_value=fake_client) as mock_cc:
        sc = SupabaseClient(settings=settings)
        mock_cc.assert_called_once_with(settings.supabase_url, settings.supabase_key)
        assert sc.raw is fake_client


def test_for_user_binds_access_token() -> None:
    """for_user builds a client from the anon key and authenticates PostgREST
    with the caller's JWT so RLS sees auth.uid()."""
    settings = Settings(
        supabase_url="https://proj.supabase.co",
        supabase_anon_key="anon-xyz",
        supabase_key="service-xyz",
        gwdg_api_key="gwdg-key-xyz",
    )
    fake_client = MagicMock()
    with patch(
        "job_agent.db.client.create_client", return_value=fake_client
    ) as mock_cc:
        wrapper = SupabaseClient.for_user("jwt-abc", settings=settings)

    # Built from the anon key, not the service key.
    mock_cc.assert_called_once_with(settings.supabase_url, settings.supabase_anon_key)
    # JWT bound to PostgREST so auth.uid() resolves to the user.
    fake_client.postgrest.auth.assert_called_once_with("jwt-abc")
    assert wrapper.raw is fake_client
