"""Synchronous HTTP client for the JSearch (RapidAPI) job search API.

Rate limit: trusted server-side (RapidAPI throttles; we surface 429 as a
typed error). Free tier is 200 req/month per docs/sources.md §4. There is no
local rolling-window limiter — keep the academic budget intact by being
deliberate about Run-Scout-Now clicks.

Uses only stdlib — no httpx/requests.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any


class JSearchAPIError(Exception):
    """Raised on non-2xx HTTP responses from the JSearch / RapidAPI endpoint.

    A 429 status carries the canonical message "RapidAPI monthly quota
    exceeded" so callers (the Streamlit UI) can switch on it cheaply.
    """

    def __init__(self, status: int, body: str, message: str | None = None) -> None:
        self.status = status
        self.body = body
        if message is None:
            message = (
                "RapidAPI monthly quota exceeded"
                if status == 429
                else f"JSearch API error {status}"
            )
        self.message = message
        super().__init__(f"{message}: {body[:200]}")


class JSearchClient:
    """Client for the JSearch (Google-for-Jobs aggregator) REST API on RapidAPI."""

    BASE_URL = "https://jsearch.p.rapidapi.com/search"
    HOST = "jsearch.p.rapidapi.com"
    DEFAULT_USER_AGENT = "job-agent/0.1 (academic project)"

    def __init__(
        self,
        opener: Any,
        api_key: str,
        user_agent: str | None = None,
        clock: Callable[[], float] | None = None,  # noqa: ARG002 — accepted for parity with ArbeitsagenturClient
    ) -> None:
        """DI-safe constructor.

        ``opener`` must implement ``.open(request) -> response``. The
        ``api_key`` MUST be non-empty — guard at the call site if you want
        a silent skip; this constructor refuses to be built without one.
        """
        if not api_key:
            raise ValueError(
                "RapidAPI key not configured — set RAPIDAPI_KEY in .env"
            )
        self._opener = opener
        self._api_key = api_key
        self._user_agent = user_agent or self.DEFAULT_USER_AGENT

    @classmethod
    def with_default_opener(
        cls,
        api_key: str,
        user_agent: str | None = None,
    ) -> JSearchClient:
        """Production factory: build a client backed by stdlib urllib."""
        return cls(
            opener=urllib.request.build_opener(),
            api_key=api_key,
            user_agent=user_agent,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        keyword: str | None = None,
        location: str | None = None,
        num_pages: int = 1,
    ) -> dict[str, Any]:
        """Search JSearch and return the raw parsed JSON dict.

        The query string follows JSearch's convention of
        ``"<keywords> in <location>"``. Empty keyword/location are tolerated
        — the query is built from whatever non-blank parts are given.
        """
        parts: list[str] = []
        if keyword and keyword.strip():
            parts.append(keyword.strip())
        if location and location.strip():
            parts.append(f"in {location.strip()}")
        query = " ".join(parts) or "developer"  # JSearch requires a non-empty query

        params = {"query": query, "num_pages": str(num_pages)}
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(
            url,
            headers={
                "X-RapidAPI-Key": self._api_key,
                "X-RapidAPI-Host": self.HOST,
                "User-Agent": self._user_agent,
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            response = self._opener.open(req)
            raw = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise JSearchAPIError(exc.code, body) from exc

        try:
            parsed: dict[str, Any] = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            snippet = raw[:200].decode("utf-8", errors="replace") if raw else ""
            raise JSearchAPIError(200, f"non-JSON body: {snippet}") from exc
        return parsed
