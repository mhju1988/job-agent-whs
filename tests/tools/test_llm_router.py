"""Tests for LLMRouter — all ChatOpenAI calls are mocked; no live network."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from job_agent.tools.llm_router import LLMRouter


def _make_router(nim_healthy: bool = True) -> tuple[LLMRouter, MagicMock, MagicMock]:
    """Create a router with mocked providers and a frozen health state.

    Patches _health_loop so the daemon thread starts but does nothing,
    then manually sets _nim_healthy to the desired state.
    """
    primary = MagicMock()
    fallback = MagicMock()
    with patch.object(LLMRouter, "_health_loop"):
        router = LLMRouter(
            primary=primary,
            fallback=fallback,
            nim_health_url="https://integrate.api.nvidia.com/v1",
            nim_api_key="test-nim-key",
            health_interval_s=3600,
        )
    router._nim_healthy = nim_healthy
    return router, primary, fallback


def test_router_uses_nim_when_healthy() -> None:
    """When NIM is healthy, primary is called and last_provider is 'nim'."""
    router, primary, fallback = _make_router(nim_healthy=True)
    primary.invoke.return_value = AIMessage(content='{"score": 80}')

    result = router.invoke([HumanMessage(content="test")])

    primary.invoke.assert_called_once()
    fallback.invoke.assert_not_called()
    assert router.last_provider == "nim"
    assert result.content == '{"score": 80}'


def test_router_skips_nim_when_unhealthy() -> None:
    """When NIM is unhealthy, primary is never called; fallback runs instead."""
    router, primary, fallback = _make_router(nim_healthy=False)
    fallback.invoke.return_value = AIMessage(content='{"score": 60}')

    router.invoke([HumanMessage(content="test")])

    primary.invoke.assert_not_called()
    fallback.invoke.assert_called_once()
    assert router.last_provider == "gwdg"


def test_router_falls_back_on_timeout() -> None:
    """TimeoutError from primary causes fallback call and resets _nim_healthy=False."""
    router, primary, fallback = _make_router(nim_healthy=True)
    primary.invoke.side_effect = TimeoutError("timed out")
    fallback.invoke.return_value = AIMessage(content='{"score": 70}')

    result = router.invoke([HumanMessage(content="test")])

    fallback.invoke.assert_called_once()
    assert router.last_provider == "gwdg"
    assert router._nim_healthy is False
    assert result.content == '{"score": 70}'


def test_router_falls_back_on_http_error() -> None:
    """Any exception from primary (e.g. 429) causes fallback and resets healthy flag."""
    router, primary, fallback = _make_router(nim_healthy=True)
    primary.invoke.side_effect = Exception("HTTP 429: quota exceeded")
    fallback.invoke.return_value = AIMessage(content='{"score": 65}')

    router.invoke([HumanMessage(content="test")])

    fallback.invoke.assert_called_once()
    assert router.last_provider == "gwdg"
    assert router._nim_healthy is False


def test_router_accepts_non_json_response_from_nim() -> None:
    """Router is a transport layer — non-JSON prose from NIM is returned as-is.

    JSON validation belongs at the agent level, not in the router. If NIM
    returns prose without raising, the router treats it as a success.
    """
    router, primary, fallback = _make_router(nim_healthy=True)
    primary.invoke.return_value = AIMessage(content="Sure! Here is my analysis in prose only.")

    result = router.invoke([HumanMessage(content="test")])

    primary.invoke.assert_called_once()
    fallback.invoke.assert_not_called()
    assert router.last_provider == "nim"
    assert result.content == "Sure! Here is my analysis in prose only."


def test_router_resets_healthy_flag_on_invoke_failure() -> None:
    """After any primary failure, _nim_healthy is immediately set to False."""
    router, primary, fallback = _make_router(nim_healthy=True)
    primary.invoke.side_effect = RuntimeError("connection reset")
    fallback.invoke.return_value = AIMessage(content='{"x": 1}')

    assert router._nim_healthy is True
    router.invoke([HumanMessage(content="test")])
    assert router._nim_healthy is False


def test_invoke_with_provider_returns_nim_when_healthy() -> None:
    router, primary, fallback = _make_router(nim_healthy=True)
    primary.invoke.return_value = AIMessage(content="ok")
    response, provider = router.invoke_with_provider([HumanMessage(content="x")])
    assert provider == "nim"
    assert response.content == "ok"
    fallback.invoke.assert_not_called()


def test_invoke_with_provider_returns_gwdg_on_fallback() -> None:
    router, primary, fallback = _make_router(nim_healthy=False)
    fallback.invoke.return_value = AIMessage(content="ok")
    response, provider = router.invoke_with_provider([HumanMessage(content="x")])
    assert provider == "gwdg"
    assert response.content == "ok"
