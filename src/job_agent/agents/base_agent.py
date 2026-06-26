"""Base agent: thin synchronous wrapper around the GWDG LLM endpoint."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, NamedTuple

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from job_agent.config import Settings, get_settings
from job_agent.tools.llm_router import LLMRouter

if TYPE_CHECKING:
    from job_agent.tools.observability_store import ObservabilityStore

#: Standard preamble for prompts that must return parseable JSON. Small models
#: (e.g. Llama-3.1-8B served by GWDG) frequently add explanatory prose around
#: JSON unless told otherwise. Prepend this to any prompt whose response is
#: parsed via `json.loads` to keep the contract reliable across the project.
JSON_ONLY_PREAMBLE = (
    "Respond with a single JSON object only. "
    "Do not add any explanation, prose, or markdown code fences.\n\n"
)


class AskResult(NamedTuple):
    """Result of ``ask_with_provider``: response text + the provider that answered."""

    content: str
    provider: str


class BaseAgent:
    """Wraps a chat model and exposes a single `ask` method.

    Dependency-injection pattern: pass `llm` in tests to avoid live calls.
    When `llm` is omitted the agent builds a `ChatOpenAI` pointed at GWDG,
    but only after `require_live_credentials()` succeeds.

    Pass `obs` to enable observability recording; omit (or pass None) in tests.

    Note: when `settings` is omitted, `get_settings()` is used (the cached
    singleton). Tests that exercise this default path must call
    `get_settings.cache_clear()` to avoid leaking real env values across tests.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        llm: BaseChatModel | None = None,
        obs: ObservabilityStore | None = None,
    ) -> None:
        self._obs = obs
        if llm is not None:
            self._llm: BaseChatModel | LLMRouter = llm
        else:
            _settings = settings if settings is not None else get_settings()
            _settings.require_live_credentials()
            if _settings.nim_api_key:
                _nim = ChatOpenAI(
                    base_url=_settings.nim_api_base,
                    api_key=_settings.nim_api_key,  # type: ignore[arg-type]
                    model=_settings.nim_model,
                    temperature=0,
                    timeout=_settings.nim_timeout,
                )
                _gwdg = ChatOpenAI(
                    base_url=_settings.gwdg_api_base,
                    api_key=_settings.gwdg_api_key,  # type: ignore[arg-type]
                    model=_settings.gwdg_model,
                    temperature=0,
                    timeout=_settings.gwdg_timeout,
                )
                self._llm = LLMRouter(
                    primary=_nim,
                    fallback=_gwdg,
                    nim_health_url=_settings.nim_api_base,
                    nim_api_key=_settings.nim_api_key,
                    health_interval_s=_settings.nim_health_interval_s,
                )
            else:
                self._llm = ChatOpenAI(
                    base_url=_settings.gwdg_api_base,
                    api_key=_settings.gwdg_api_key,  # type: ignore[arg-type]
                    model=_settings.gwdg_model,
                    temperature=0,
                    timeout=_settings.gwdg_timeout,
                )

    @property
    def last_provider(self) -> str:
        """Provider name ('nim' or 'gwdg') that answered the last ask() call.

        Reads the shared router field. NOT concurrency-safe — concurrent callers
        must use ``ask_with_provider``, which captures the provider per-call.
        Single-shot callers are safe here (no concurrent writer).
        """
        if isinstance(self._llm, LLMRouter):
            return self._llm.last_provider
        return "gwdg"

    def ask(self, prompt: str) -> str:
        """Send a single human message and return the response text."""
        from job_agent.tools.run_context import get_current_run

        t0 = time.perf_counter()
        response = self._llm.invoke([HumanMessage(content=prompt)])
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if self._obs is not None:
            ctx = get_current_run()
            usage = (response.response_metadata or {}).get("token_usage", {})
            self._obs.insert_llm_event(
                run_id=ctx.run_id if ctx else "unknown",
                prompt_snippet=prompt[:500],
                response_snippet=str(response.content)[:500],
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                duration_ms=elapsed_ms,
                provider=self.last_provider,
            )

        return str(response.content)

    def ask_with_provider(self, prompt: str) -> AskResult:
        """Like ask(), but returns the provider captured per-call (concurrency-safe).

        Concurrent callers (e.g. the matcher's ThreadPoolExecutor) MUST use this
        instead of ask() + last_provider, which races on the shared router field.
        The provider is taken from this call's return value, and the obs event is
        stamped with that same local — never read back off the shared field.
        """
        from job_agent.tools.run_context import get_current_run

        t0 = time.perf_counter()
        if isinstance(self._llm, LLMRouter):
            response, provider = self._llm.invoke_with_provider(
                [HumanMessage(content=prompt)]
            )
        else:
            response = self._llm.invoke([HumanMessage(content=prompt)])
            provider = "gwdg"
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if self._obs is not None:
            ctx = get_current_run()
            usage = (response.response_metadata or {}).get("token_usage", {})
            self._obs.insert_llm_event(
                run_id=ctx.run_id if ctx else "unknown",
                prompt_snippet=prompt[:500],
                response_snippet=str(response.content)[:500],
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                duration_ms=elapsed_ms,
                provider=provider,
            )

        return AskResult(content=str(response.content), provider=provider)
