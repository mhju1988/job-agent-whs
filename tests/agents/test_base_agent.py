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
        nim_api_key="",  # force GWDG-only path regardless of env
    )

    with patch("job_agent.agents.base_agent.ChatOpenAI") as mock_chat_openai:
        mock_chat_openai.return_value = MagicMock()

        BaseAgent(settings=dummy_settings)

        mock_chat_openai.assert_called_once_with(
            base_url="https://example.com/v1",
            api_key="test-key-123",
            model="test-model",
            temperature=0,
            timeout=120,
        )


def test_ask_records_llm_event_when_obs_provided() -> None:
    """When obs is injected, ask() writes an llm_events row."""
    from unittest.mock import MagicMock

    from job_agent.tools.observability_store import ObservabilityStore
    from job_agent.tools.run_context import start_run

    start_run("matcher")

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "gap analysis result"
    mock_response.response_metadata = {
        "token_usage": {"prompt_tokens": 200, "completion_tokens": 80}
    }
    mock_llm.invoke.return_value = mock_response

    mock_obs = MagicMock(spec=ObservabilityStore)
    agent = BaseAgent(llm=mock_llm, obs=mock_obs)
    result = agent.ask("analyze this job")

    assert result == "gap analysis result"
    mock_obs.insert_llm_event.assert_called_once()
    call_kwargs = mock_obs.insert_llm_event.call_args.kwargs
    assert call_kwargs["prompt_tokens"] == 200
    assert call_kwargs["completion_tokens"] == 80
    assert call_kwargs["prompt_snippet"] == "analyze this job"
    assert call_kwargs["response_snippet"] == "gap analysis result"
    assert call_kwargs["provider"] == "gwdg"


def test_ask_skips_obs_when_none() -> None:
    """Existing behavior unchanged when obs=None (default)."""
    from unittest.mock import MagicMock

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "hello"
    mock_response.response_metadata = {}
    mock_llm.invoke.return_value = mock_response

    agent = BaseAgent(llm=mock_llm)   # obs defaults to None
    result = agent.ask("hi")
    assert result == "hello"          # no exception, no side effects


def test_ask_handles_missing_token_usage_gracefully() -> None:
    """If GWDG omits token_usage, obs.insert_llm_event is called with None tokens."""
    from unittest.mock import MagicMock

    from job_agent.tools.observability_store import ObservabilityStore
    from job_agent.tools.run_context import start_run

    start_run("writer")

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "result"
    mock_response.response_metadata = {}   # no token_usage key
    mock_llm.invoke.return_value = mock_response

    mock_obs = MagicMock(spec=ObservabilityStore)
    agent = BaseAgent(llm=mock_llm, obs=mock_obs)
    agent.ask("prompt")

    call_kwargs = mock_obs.insert_llm_event.call_args.kwargs
    assert call_kwargs["prompt_tokens"] is None
    assert call_kwargs["completion_tokens"] is None


def test_base_agent_last_provider_returns_gwdg_for_plain_mock() -> None:
    """last_provider is 'gwdg' when self._llm is not an LLMRouter (e.g. test mock)."""
    mock_llm = MagicMock()
    agent = BaseAgent(llm=mock_llm)
    assert agent.last_provider == "gwdg"


def test_ask_with_provider_plain_mock_returns_gwdg() -> None:
    from job_agent.agents.base_agent import AskResult

    mock_llm = MagicMock()  # not an LLMRouter -> else branch -> "gwdg"
    mock_response = MagicMock()
    mock_response.content = "hi"
    mock_response.response_metadata = {}
    mock_llm.invoke.return_value = mock_response

    agent = BaseAgent(llm=mock_llm)
    result = agent.ask_with_provider("q")

    assert isinstance(result, AskResult)
    assert result.content == "hi"
    assert result.provider == "gwdg"
    mock_llm.invoke.assert_called_once_with([HumanMessage(content="q")])


def test_ask_with_provider_router_returns_per_call_provider() -> None:
    from job_agent.agents.base_agent import AskResult
    from job_agent.tools.llm_router import LLMRouter

    mock_router = MagicMock(spec=LLMRouter)  # isinstance(_, LLMRouter) is True
    mock_response = MagicMock()
    mock_response.content = "hi"
    mock_response.response_metadata = {}
    mock_router.invoke_with_provider.return_value = (mock_response, "nim")

    agent = BaseAgent(llm=mock_router)
    result = agent.ask_with_provider("q")

    assert result == AskResult(content="hi", provider="nim")
    mock_router.invoke_with_provider.assert_called_once_with([HumanMessage(content="q")])


def test_ask_with_provider_records_obs_with_local_provider() -> None:
    from job_agent.tools.llm_router import LLMRouter
    from job_agent.tools.observability_store import ObservabilityStore
    from job_agent.tools.run_context import start_run

    start_run("matcher")
    mock_router = MagicMock(spec=LLMRouter)
    mock_response = MagicMock()
    mock_response.content = "result"
    mock_response.response_metadata = {"token_usage": {"prompt_tokens": 5, "completion_tokens": 2}}
    mock_router.invoke_with_provider.return_value = (mock_response, "nim")
    mock_obs = MagicMock(spec=ObservabilityStore)

    agent = BaseAgent(llm=mock_router, obs=mock_obs)
    agent.ask_with_provider("q")

    kwargs = mock_obs.insert_llm_event.call_args.kwargs
    assert kwargs["provider"] == "nim"  # the per-call local, not a shared field


def test_default_llm_uses_router_when_nim_configured() -> None:
    """When nim_api_key is set in settings, BaseAgent builds an LLMRouter."""

    settings = Settings(
        gwdg_api_base="https://gwdg.example.com/v1",
        gwdg_api_key="gwdg-key",
        gwdg_model="apertus",
        nim_api_base="https://integrate.api.nvidia.com/v1",
        nim_api_key="nim-key",
        nim_model="meta/llama-3.1-70b-instruct",
        supabase_url="https://db.example.com",
        supabase_key="sb-key",
    )

    with patch("job_agent.agents.base_agent.LLMRouter") as mock_router_cls, \
         patch("job_agent.agents.base_agent.ChatOpenAI"):
        mock_router_cls.return_value = MagicMock()
        BaseAgent(settings=settings)
        mock_router_cls.assert_called_once()
