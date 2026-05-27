"""Tests for BaseAgent — all LLM calls are mocked; no live network calls."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from job_agent.agents.base_agent import BaseAgent
from job_agent.config import MissingCredentialsError, Settings


def test_ask_returns_llm_response_content() -> None:
    """Inject a mock llm; ask() must return response.content and call invoke correctly."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "hello from gwdg"
    mock_llm.invoke.return_value = mock_response

    agent = BaseAgent(llm=mock_llm)
    result = agent.ask("hi")

    assert result == "hello from gwdg"
    mock_llm.invoke.assert_called_once_with([HumanMessage(content="hi")])


def test_ask_raises_when_credentials_missing_at_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without llm DI and missing env vars, __init__ raises MissingCredentialsError.

    The error is raised at construction (not lazily on first ask) because
    require_live_credentials() runs inside __init__. Misconfiguration is
    visible immediately rather than at first use.
    """
    monkeypatch.chdir(tmp_path)  # prevent any .env file from being found
    empty_settings = Settings(gwdg_api_key="", supabase_url="", supabase_key="")

    with pytest.raises(MissingCredentialsError):
        BaseAgent(settings=empty_settings)


def test_default_llm_constructed_with_settings_values() -> None:
    """When no llm is injected, ChatOpenAI is built from settings values."""
    dummy_settings = Settings(
        gwdg_api_base="https://example.com/v1",
        gwdg_api_key="test-key-123",
        gwdg_model="test-model",
        supabase_url="https://db.example.com",
        supabase_key="supabase-secret",
    )

    with patch("job_agent.agents.base_agent.ChatOpenAI") as mock_chat_openai:
        mock_chat_openai.return_value = MagicMock()

        BaseAgent(settings=dummy_settings)

        mock_chat_openai.assert_called_once_with(
            base_url="https://example.com/v1",
            api_key="test-key-123",
            model="test-model",
            temperature=0,
        )
