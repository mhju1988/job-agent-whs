"""Tests for src/job_agent/tools/job_normalizer.py."""

from __future__ import annotations

from typing import Any

import pytest

from job_agent.models.job import Job  # noqa: E402
from job_agent.tools.job_normalizer import (
    normalize,
    normalize_adzuna,
    normalize_arbeitsagentur,
    normalize_jsearch,
)

FULL_FIXTURE: dict[str, Any] = {
    "refnr": "REF-001",
    "titel": "Backend Developer",
    "arbeitgeber": "Tech GmbH",
    "arbeitsort": {"ort": "Munich", "plz": "80331"},
}


def test_arbeitsagentur_full_record() -> None:
    job = normalize_arbeitsagentur(FULL_FIXTURE)
    assert isinstance(job, Job)
    assert job.source == "arbeitsagentur"
    assert job.external_id == "REF-001"
    assert job.title == "Backend Developer"
    assert job.company == "Tech GmbH"
    assert job.location == "Munich, 80331"
    assert job.url == "https://www.arbeitsagentur.de/jobsuche/jobdetail/REF-001"
    assert job.requirements == []
    assert job.description is None


def test_arbeitsagentur_fallback_to_hashid() -> None:
    raw = {
        "hashId": "HASH-999",
        "titel": "Data Analyst",
        "arbeitgeber": "BigCo",
        "arbeitsort": {"ort": "Hamburg"},
    }
    job = normalize_arbeitsagentur(raw)
    assert job.external_id == "HASH-999"
    assert job.url == "https://www.arbeitsagentur.de/jobsuche/jobdetail/HASH-999"


def test_arbeitsagentur_missing_id_raises() -> None:
    raw = {"titel": "Designer", "arbeitgeber": "Studio"}
    with pytest.raises(ValueError, match="missing id"):
        normalize_arbeitsagentur(raw)


def test_arbeitsagentur_location_concat() -> None:
    raw = {
        "refnr": "X1",
        "titel": "Dev",
        "arbeitsort": {"ort": "Berlin", "plz": "10115"},
    }
    job = normalize_arbeitsagentur(raw)
    assert job.location == "Berlin, 10115"


def test_arbeitsagentur_location_ort_only() -> None:
    raw = {
        "refnr": "X2",
        "titel": "Dev",
        "arbeitsort": {"ort": "Berlin"},
    }
    job = normalize_arbeitsagentur(raw)
    assert job.location == "Berlin"


def test_dispatcher_routes_to_arbeitsagentur() -> None:
    job_direct = normalize_arbeitsagentur(FULL_FIXTURE)
    job_dispatch = normalize("arbeitsagentur", FULL_FIXTURE)
    assert job_direct.external_id == job_dispatch.external_id
    assert job_direct.url == job_dispatch.url
    assert job_direct.title == job_dispatch.title


def test_adzuna_stub_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        normalize_adzuna({})


def test_dispatcher_unknown_source_raises() -> None:
    with pytest.raises(ValueError, match="unknown source"):
        normalize("indeed", {})


# ---------------------------------------------------------------------------
# Detail-endpoint enrichment (task 2)
# ---------------------------------------------------------------------------


_MIN_LIST_ROW: dict[str, Any] = {
    "refnr": "10010",
    "titel": "Backend Engineer",
    "arbeitgeber": "Acme GmbH",
}


def test_normalize_without_detail_uses_list_description() -> None:
    """Backwards-compatible: no detail arg → description stays None."""
    job = normalize_arbeitsagentur(_MIN_LIST_ROW)
    assert job.description is None
    assert job.external_id == "10010"


def test_normalize_with_detail_prefers_full_description() -> None:
    """When detail provides ``stellenbeschreibung``, it populates description."""
    detail = {
        "refnr": "10010",
        "stellenbeschreibung": "We are looking for a senior Python engineer "
        "to lead our backend platform team. 5+ years required.",
    }
    job = normalize_arbeitsagentur(_MIN_LIST_ROW, detail=detail)
    assert job.description is not None
    assert "senior Python engineer" in job.description


def test_normalize_with_detail_blank_description_falls_back_to_none() -> None:
    """Whitespace-only stellenbeschreibung is ignored (not a real description)."""
    detail = {"stellenbeschreibung": "   \n  "}
    job = normalize_arbeitsagentur(_MIN_LIST_ROW, detail=detail)
    assert job.description is None


def test_normalize_dispatcher_forwards_detail() -> None:
    """normalize(source, raw, detail=...) threads detail through to arbeitsagentur."""
    detail = {"stellenbeschreibung": "Forwarded text"}
    job = normalize("arbeitsagentur", _MIN_LIST_ROW, detail=detail)
    assert job.description == "Forwarded text"


# ---------------------------------------------------------------------------
# JSearch normaliser (task 3)
# ---------------------------------------------------------------------------


_JSEARCH_FIXTURE: dict[str, Any] = {
    "job_id": "abc-123-XYZ",
    "job_title": "Senior Python Engineer",
    "employer_name": "TechCorp",
    "job_city": "Berlin",
    "job_country": "DE",
    "job_description": "Build scalable APIs in Python. 5+ years required.",
    "job_apply_link": "https://example.com/apply/abc-123",
}


def test_normalize_jsearch_full_record() -> None:
    job = normalize_jsearch(_JSEARCH_FIXTURE)
    assert job.source == "jsearch"
    assert job.external_id == "abc-123-XYZ"
    assert job.title == "Senior Python Engineer"
    assert job.company == "TechCorp"
    assert job.location == "Berlin, DE"
    assert job.description is not None
    assert "scalable APIs" in job.description
    assert job.url == "https://example.com/apply/abc-123"


def test_normalize_jsearch_missing_job_id_raises() -> None:
    raw = dict(_JSEARCH_FIXTURE)
    raw.pop("job_id")
    with pytest.raises(ValueError, match="missing job_id"):
        normalize_jsearch(raw)


def test_normalize_jsearch_missing_title_raises() -> None:
    raw = dict(_JSEARCH_FIXTURE)
    raw.pop("job_title")
    with pytest.raises(ValueError, match="missing job_title"):
        normalize_jsearch(raw)


def test_normalize_jsearch_location_skips_empty_parts() -> None:
    raw = dict(_JSEARCH_FIXTURE)
    raw["job_city"] = None
    job = normalize_jsearch(raw)
    assert job.location == "DE"


def test_normalize_jsearch_no_location_at_all() -> None:
    raw = dict(_JSEARCH_FIXTURE)
    raw["job_city"] = None
    raw["job_country"] = None
    job = normalize_jsearch(raw)
    assert job.location is None


def test_normalize_jsearch_ignores_detail_arg() -> None:
    """`detail` is accepted for signature uniformity but must be ignored."""
    detail = {"stellenbeschreibung": "SHOULD NOT WIN"}
    job = normalize_jsearch(_JSEARCH_FIXTURE, detail=detail)
    assert "scalable APIs" in (job.description or "")
    assert "SHOULD NOT WIN" not in (job.description or "")


def test_normalize_dispatcher_routes_jsearch() -> None:
    job = normalize("jsearch", _JSEARCH_FIXTURE)
    assert job.source == "jsearch"
    assert job.title == "Senior Python Engineer"
