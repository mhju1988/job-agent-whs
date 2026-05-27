"""Tests for ArbeitsagenturClient — zero live network calls."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from io import BytesIO
from typing import Any  # noqa: UP035 — stdlib typing for Python 3.11 compat
from unittest.mock import MagicMock

import pytest

from job_agent.tools.arbeitsagentur_client import (
    ArbeitsagenturAPIError,
    ArbeitsagenturClient,
    RateLimitExceeded,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_response(payload: dict[str, Any], status: int = 200) -> MagicMock:
    """Return a mock response whose .read() returns JSON bytes."""
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = json.dumps(payload).encode()
    return resp


def _make_opener(payload: dict[str, Any]) -> MagicMock:
    opener = MagicMock()
    opener.open.return_value = _fake_response(payload)
    return opener


# ---------------------------------------------------------------------------
# Test 1 — correct URL, query params, and headers
# ---------------------------------------------------------------------------


def test_search_builds_correct_url_and_headers() -> None:
    payload = {"maxErgebnisse": 1, "stellenangebote": []}
    opener = _make_opener(payload)

    client = ArbeitsagenturClient(opener=opener)
    result = client.search(keyword="python", location="Berlin", page=1, page_size=5)

    assert result == payload

    # Capture the Request object passed to opener.open
    call_args = opener.open.call_args
    req: urllib.request.Request = call_args[0][0]

    # URL must contain all four query params
    assert "was=python" in req.full_url
    assert "wo=Berlin" in req.full_url
    assert "page=1" in req.full_url
    assert "size=5" in req.full_url

    # Headers
    assert req.get_header("X-api-key") == ArbeitsagenturClient.API_KEY
    assert req.get_header("User-agent") == ArbeitsagenturClient.DEFAULT_USER_AGENT
    assert req.get_header("Accept") == "application/json"


# ---------------------------------------------------------------------------
# Test 2 — None params are omitted
# ---------------------------------------------------------------------------


def test_omits_none_params() -> None:
    payload: dict[str, Any] = {}
    opener = _make_opener(payload)

    client = ArbeitsagenturClient(opener=opener)
    client.search(keyword=None, location="Berlin")

    req: urllib.request.Request = opener.open.call_args[0][0]
    assert "wo=Berlin" in req.full_url
    assert "was=" not in req.full_url


# ---------------------------------------------------------------------------
# Test 3 — non-2xx raises ArbeitsagenturAPIError
# ---------------------------------------------------------------------------


def test_empty_body_raises_api_error() -> None:
    """200 with empty body must not crash on json.loads — surfaces as ArbeitsagenturAPIError."""
    resp = MagicMock()
    resp.read.return_value = b"not-json-at-all"
    opener = MagicMock()
    opener.open.return_value = resp

    client = ArbeitsagenturClient(opener=opener)
    with pytest.raises(ArbeitsagenturAPIError) as exc_info:
        client.search()
    assert "non-JSON" in exc_info.value.body


def test_non_2xx_raises_api_error() -> None:
    opener = MagicMock()
    # Simulate urllib raising HTTPError on open()
    http_err = urllib.error.HTTPError(
        url="http://example.com",
        code=500,
        msg="Internal Server Error",
        hdrs=MagicMock(),  # type: ignore[arg-type]
        fp=BytesIO(b"server boom"),
    )
    opener.open.side_effect = http_err

    client = ArbeitsagenturClient(opener=opener)
    with pytest.raises(ArbeitsagenturAPIError) as exc_info:
        client.search(keyword="python")

    assert exc_info.value.status == 500
    assert "server boom" in exc_info.value.body


# ---------------------------------------------------------------------------
# Test 4 — rate limit blocks after cap
# ---------------------------------------------------------------------------


def test_rate_limit_blocks_after_cap() -> None:
    payload: dict[str, Any] = {}
    opener = _make_opener(payload)

    tick = 0.0

    def fake_clock() -> float:
        return tick

    client = ArbeitsagenturClient(max_requests_per_hour=2, opener=opener, clock=fake_clock)

    client.search()  # request 1
    client.search()  # request 2

    with pytest.raises(RateLimitExceeded):
        client.search()  # request 3 — should be blocked


# ---------------------------------------------------------------------------
# Test 5 — rate limit resets after 1-hour window
# ---------------------------------------------------------------------------


def test_rate_limit_resets_after_window() -> None:
    payload: dict[str, Any] = {}
    opener = _make_opener(payload)

    current_time: list[float] = [0.0]

    def fake_clock() -> float:
        return current_time[0]

    client = ArbeitsagenturClient(max_requests_per_hour=2, opener=opener, clock=fake_clock)

    client.search()  # t=0, request 1
    client.search()  # t=0, request 2

    # Advance clock past 1 hour — both previous timestamps are now outside window
    current_time[0] = 3601.0

    # Should succeed: window reset
    result = client.search()
    assert result == payload


# ---------------------------------------------------------------------------
# fetch_detail — task 2: full job description endpoint
# ---------------------------------------------------------------------------


def test_fetch_detail_returns_parsed_json() -> None:
    payload = {"refnr": "10001", "stellenbeschreibung": "Full job description text."}
    opener = _make_opener(payload)
    client = ArbeitsagenturClient(opener=opener)

    result = client.fetch_detail("10001-XYZ")

    assert result == payload
    # Inspect the Request that urllib actually opened.
    req: urllib.request.Request = opener.open.call_args.args[0]
    assert req.full_url.endswith("/v4/jobdetails/10001-XYZ")
    assert req.headers["X-api-key"] == "jobboerse-jobsuche"
    assert "job-agent" in req.headers["User-agent"]
    assert req.get_method() == "GET"


def test_fetch_detail_raises_on_http_error() -> None:
    opener = MagicMock()
    http_err = urllib.error.HTTPError(
        url="http://example.com",
        code=404,
        msg="Not Found",
        hdrs=MagicMock(),  # type: ignore[arg-type]
        fp=BytesIO(b"no such ref"),
    )
    opener.open.side_effect = http_err

    client = ArbeitsagenturClient(opener=opener)
    with pytest.raises(ArbeitsagenturAPIError) as exc_info:
        client.fetch_detail("missing-ref")

    assert exc_info.value.status == 404
    assert "no such ref" in exc_info.value.body


def test_fetch_detail_empty_ref_raises_without_http_call() -> None:
    opener = MagicMock()
    client = ArbeitsagenturClient(opener=opener)
    with pytest.raises(ArbeitsagenturAPIError):
        client.fetch_detail("")
    opener.open.assert_not_called()


def test_fetch_detail_counts_against_rate_limit() -> None:
    """Detail calls share the rolling budget with search()."""
    payload = {"refnr": "x", "stellenbeschreibung": "y"}
    opener = _make_opener(payload)
    client = ArbeitsagenturClient(opener=opener, max_requests_per_hour=2)

    client.fetch_detail("a")
    client.fetch_detail("b")
    with pytest.raises(RateLimitExceeded):
        client.fetch_detail("c")
