"""LLMRouter: routes LLM invoke() to NIM (primary) with GWDG as fallback."""
from __future__ import annotations

import logging
import threading
import urllib.request
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

log = logging.getLogger(__name__)


class LLMRouter:
    """Routes LLM calls to a primary provider (NIM) with an automatic fallback (GWDG).

    A daemon thread health-checks the primary every *health_interval_s* seconds.
    On any primary failure the router falls back and pessimistically marks NIM as
    down; the background thread restores the flag when NIM recovers.
    Exposes the same .invoke() interface as ChatOpenAI — drop-in replacement.
    """

    def __init__(
        self,
        primary: ChatOpenAI,
        fallback: ChatOpenAI,
        nim_health_url: str,
        nim_api_key: str,
        health_interval_s: int = 60,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._nim_health_url = nim_health_url
        self._nim_api_key = nim_api_key
        self._last_provider = "gwdg"
        # Not lock-protected: invoke() is single-threaded per instance.
        # Each API request gets its own BaseAgent → its own LLMRouter via DI.
        self._lock = threading.Lock()
        self._stop = threading.Event()
        # Synchronous first check so the first invoke() sees the correct health
        # state immediately. Subsequent updates run in the background thread.
        self._nim_healthy = self._check_nim()
        self._thread = threading.Thread(
            target=self._health_loop,
            args=(health_interval_s,),
            daemon=True,
            name="nim-health",
        )
        self._thread.start()

    # ------------------------------------------------------------------
    # Health check (background thread)
    # ------------------------------------------------------------------

    def _health_loop(self, interval_s: int) -> None:
        while not self._stop.is_set():
            healthy = self._check_nim()
            with self._lock:
                old = self._nim_healthy
                self._nim_healthy = healthy
            if healthy != old:
                log.info("NIM health changed → %s", "UP" if healthy else "DOWN")
            self._stop.wait(interval_s)

    def _check_nim(self) -> bool:
        try:
            req = urllib.request.Request(
                f"{self._nim_health_url}/models",
                headers={"Authorization": f"Bearer {self._nim_api_key}"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return bool(resp.status == 200)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # LLM interface — drop-in for ChatOpenAI
    # ------------------------------------------------------------------

    def invoke_with_provider(self, messages: Any, **kwargs: Any) -> tuple[BaseMessage, str]:
        """Invoke the LLM, returning ``(response, provider_used_this_call)``.

        The provider is returned as a local — safe to read under concurrency,
        unlike the shared ``last_provider`` field. Falls back to GWDG when NIM is
        flagged unhealthy or invoke() raises any exception. JSON validation
        belongs at the agent level, not here.
        """
        with self._lock:
            nim_healthy = self._nim_healthy

        if nim_healthy:
            try:
                response = self._primary.invoke(messages, **kwargs)
                return response, "nim"
            except Exception as exc:
                log.warning(
                    "NIM invoke failed (%s: %s), falling back to GWDG",
                    type(exc).__name__,
                    exc,
                )
                with self._lock:
                    self._nim_healthy = False

        response = self._fallback.invoke(messages, **kwargs)
        return response, "gwdg"

    def invoke(self, messages: Any, **kwargs: Any) -> BaseMessage:
        """Drop-in for ChatOpenAI.invoke. Records ``last_provider`` as a side effect.

        NOTE: ``last_provider`` is the shared field and is NOT concurrency-safe;
        concurrent callers must use ``invoke_with_provider`` (provider returned
        per-call).
        """
        response, provider = self.invoke_with_provider(messages, **kwargs)
        self._last_provider = provider
        return response

    @property
    def last_provider(self) -> str:
        """Name of the provider that answered the most recent invoke() call."""
        return self._last_provider
