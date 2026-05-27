"""Synchronous HTTP client for the Bundesagentur für Arbeit job search API.

Rate limit: ≤ 100 requests per rolling hour (docs/legal.md §3).
Uses only stdlib — no httpx/requests.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from collections.abc import Callable
from typing import Any


class ArbeitsagenturAPIError(Exception):
    """Raised on non-2xx HTTP responses from the Arbeitsagentur API."""

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"Arbeitsagentur API error {status}: {body[:200]}")


class RateLimitExceeded(Exception):  # noqa: N818
    """Raised when the client-side rate limit would be exceeded."""

    def __init__(self, max_requests_per_hour: int) -> None:
        super().__init__(
            f"Rate limit of {max_requests_per_hour} requests/hour would be exceeded."
        )


class ArbeitsagenturClient:
    """Client for the Arbeitsagentur job-search REST API v4."""

    BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
    DETAIL_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails"
    API_KEY = "jobboerse-jobsuche"
    DEFAULT_USER_AGENT = "job-agent/0.1 (academic project; +https://github.com/...)"

    def __init__(
        self,
        opener: Any,
        max_requests_per_hour: int = 100,
        user_agent: str | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Constructor is always DI-safe: ``opener`` is required.

        Use :meth:`with_default_opener` for the production path (constructs a
        live ``urllib.request`` opener). Tests must pass a mock.
        """
        self._max_requests_per_hour = max_requests_per_hour
        self._user_agent = user_agent or self.DEFAULT_USER_AGENT
        self._opener = opener  # must have .open(request) -> response
        self._clock: Callable[[], float] = clock or __import__("time").time
        # Timestamps of recent requests (rolling window)
        self._request_times: deque[float] = deque()

    @classmethod
    def with_default_opener(
        cls,
        max_requests_per_hour: int = 100,
        user_agent: str | None = None,
        clock: Callable[[], float] | None = None,
    ) -> ArbeitsagenturClient:
        """Production factory: build a client backed by stdlib urllib."""
        return cls(
            opener=urllib.request.build_opener(),
            max_requests_per_hour=max_requests_per_hour,
            user_agent=user_agent,
            clock=clock,
        )

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _enforce_rate_limit(self) -> None:
        """Raise RateLimitExceeded if adding one more request would breach the cap."""
        now = self._clock()
        window_start = now - 3600.0
        # Evict timestamps older than 1 hour
        while self._request_times and self._request_times[0] < window_start:
            self._request_times.popleft()
        if len(self._request_times) >= self._max_requests_per_hour:
            raise RateLimitExceeded(self._max_requests_per_hour)
        self._request_times.append(now)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        keyword: str | None = None,
        location: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        """Search for jobs and return the raw parsed JSON response dict."""
        self._enforce_rate_limit()

        params: dict[str, str] = {}
        if keyword is not None:
            params["was"] = keyword
        if location is not None:
            params["wo"] = location
        params["page"] = str(page)
        params["size"] = str(page_size)

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(
            url,
            headers={
                "X-API-Key": self.API_KEY,
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
            raise ArbeitsagenturAPIError(exc.code, body) from exc

        try:
            parsed: dict[str, Any] = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            snippet = raw[:200].decode("utf-8", errors="replace") if raw else ""
            raise ArbeitsagenturAPIError(200, f"non-JSON body: {snippet}") from exc
        return parsed

    def fetch_detail(self, ref_nr: str) -> dict[str, Any]:
        """Fetch the full job detail (incl. ``stellenbeschreibung``) for a ref_nr.

        Hits ``/v4/jobdetails/{ref_nr}``. Counts against the same rolling-hour
        rate limiter as :meth:`search`. Returns the parsed JSON dict.
        """
        if not ref_nr:
            raise ArbeitsagenturAPIError(0, "fetch_detail: empty ref_nr")

        self._enforce_rate_limit()

        # ref_nr may contain '/' or other URL-unsafe chars in edge cases.
        url = f"{self.DETAIL_URL}/{urllib.parse.quote(ref_nr, safe='')}"
        req = urllib.request.Request(
            url,
            headers={
                "X-API-Key": self.API_KEY,
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
            raise ArbeitsagenturAPIError(exc.code, body) from exc

        try:
            parsed: dict[str, Any] = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            snippet = raw[:200].decode("utf-8", errors="replace") if raw else ""
            raise ArbeitsagenturAPIError(200, f"non-JSON body: {snippet}") from exc
        return parsed
