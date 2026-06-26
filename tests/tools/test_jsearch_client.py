"""Tests for JSearchClient — zero live network calls."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock

import pytest

from job_agent.tools.jsearch_client import JSearchAPIError, JSearchClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_response(payload: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    return resp


def _make_opener(payload: dict[str, Any]) -> MagicMock:
    opener = MagicMock()
    opener.open.return_value = _fake_response(payload)
    return opener


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------


def test_constructor_rejects_empty_api_key() -> None:
    with pytest.raises(ValueError, match="RapidAPI key not configured"):
        JSearchClient(opener=MagicMock(), api_key="")


# ---------------------------------------------------------------------------
# Test 1 — URL, query params, and RapidAPI headers
# ---------------------------------------------------------------------------


def test_search_builds_correct_url_and_headers() -> None:
    payload = {"status": "OK", "data": []}
    opener = _make_opener(payload)
    client = JSearchClient(opener=opener, api_key="test-key-123")

    result = client.search(keyword="Python Developer", location="Berlin")
    assert result == payload

    req: urllib.request.Request = opener.open.call_args.args[0]
    # Query: "<kw> in <loc>"
    assert "query=Python+Developer+in+Berlin" in req.full_url
    assert "num_pages=1" in req.full_url
    # Defaults to the German index — JSearch's own default is 'us', which
    # returns no results for German locations, so 'de' is the project default.
    assert "country=de" in req.full_url
    # RapidAPI auth headers
    assert req.headers["X-rapidapi-key"] == "test-key-123"
    assert req.headers["X-rapidapi-host"] == "jsearch.p.rapidapi.com"
    assert req.get_method() == "GET"


def test_search_country_param_overrides_default() -> None:
    """An explicit country= overrides the 'de' default in the URL."""
    opener = _make_opener({"data": []})
    client = JSearchClient(opener=opener, api_key="k")
    client.search(keyword="python", country="us")
    req: urllib.request.Request = opener.open.call_args.args[0]
    assert "country=us" in req.full_url
    assert "country=de" not in req.full_url


def test_search_empty_inputs_fall_back_to_default_query() -> None:
    """JSearch requires a non-empty query — client falls back to 'developer'."""
    opener = _make_opener({"data": []})
    client = JSearchClient(opener=opener, api_key="k")
    client.search()
    req: urllib.request.Request = opener.open.call_args.args[0]
    assert "query=developer" in req.full_url


# ---------------------------------------------------------------------------
# Test 2 — HTTPError → JSearchAPIError
# ---------------------------------------------------------------------------


def test_search_http_error_raises_typed_exception() -> None:
    opener = MagicMock()
    http_err = urllib.error.HTTPError(
        url="http://example.com",
        code=500,
        msg="Internal Server Error",
        hdrs=MagicMock(),  # type: ignore[arg-type]
        fp=BytesIO(b"upstream boom"),
    )
    opener.open.side_effect = http_err

    client = JSearchClient(opener=opener, api_key="k")
    with pytest.raises(JSearchAPIError) as exc_info:
        client.search(keyword="python")

    assert exc_info.value.status == 500
    assert "upstream boom" in exc_info.value.body
    assert "JSearch API error 500" in exc_info.value.message


# ---------------------------------------------------------------------------
# Test 3 — 429 carries the canonical quota-exceeded message
# ---------------------------------------------------------------------------


def test_search_429_carries_quota_message() -> None:
    """RapidAPI throttling (429) must surface the canonical message so the
    Streamlit UI can switch on it."""
    opener = MagicMock()
    http_err = urllib.error.HTTPError(
        url="http://example.com",
        code=429,
        msg="Too Many Requests",
        hdrs=MagicMock(),  # type: ignore[arg-type]
        fp=BytesIO(b"monthly quota exhausted"),
    )
    opener.open.side_effect = http_err

    client = JSearchClient(opener=opener, api_key="k")
    with pytest.raises(JSearchAPIError) as exc_info:
        client.search()

    assert exc_info.value.status == 429
    assert exc_info.value.message == "RapidAPI monthly quota exceeded"


# ---------------------------------------------------------------------------
# Test 4 — non-JSON body → JSearchAPIError
# ---------------------------------------------------------------------------


def test_search_non_json_body_raises() -> None:
    opener = MagicMock()
    resp = MagicMock()
    resp.read.return_value = b"<html>maintenance page</html>"
    opener.open.return_value = resp

    client = JSearchClient(opener=opener, api_key="k")
    with pytest.raises(JSearchAPIError) as exc_info:
        client.search(keyword="python")

    assert "non-JSON" in exc_info.value.body
