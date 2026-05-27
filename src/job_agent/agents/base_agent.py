"""Base agent: thin synchronous wrapper around the GWDG LLM endpoint."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from job_agent.config import Settings, get_settings


class BaseAgent:
    """Wraps a chat model and exposes a single `ask` method.

    Dependency-injection pattern: pass `llm` in tests to avoid live calls.
    When `llm` is omitted the agent builds a `ChatOpenAI` pointed at GWDG,
    but only after `require_live_credentials()` succeeds.

    Note: when `settings` is omitted, `get_settings()` is used (the cached
    singleton). Tests that exercise this default path must call
    `get_settings.cache_clear()` to avoid leaking real env values across tests.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        llm: BaseChatModel | None = None,
    ) -> None:
        if llm is not None:
            self._llm: BaseChatModel = llm
            return
        _settings = settings if settings is not None else get_settings()
        _settings.require_live_credentials()
        self._llm = ChatOpenAI(
            base_url=_settings.gwdg_api_base,
            api_key=_settings.gwdg_api_key,  # type: ignore[arg-type]
            model=_settings.gwdg_model,
            temperature=0,
        )

    def ask(self, prompt: str) -> str:
        """Send a single human message and return the response text."""
        response = self._llm.invoke([HumanMessage(content=prompt)])
        # `.content` may be a list of content blocks in multimodal responses;
        # str() collapses it to a plain string for our text-only use case.
        return str(response.content)
