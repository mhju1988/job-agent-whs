"""Normalizer functions: raw vendor dicts → Job pydantic models."""

from __future__ import annotations

from typing import Any

from job_agent.models.job import Job


def normalize_arbeitsagentur(
    raw_job: dict[str, Any], detail: dict[str, Any] | None = None
) -> Job:
    """Map a raw Arbeitsagentur list-response item to a Job.

    If ``detail`` is provided (from ``ArbeitsagenturClient.fetch_detail``),
    its ``stellenbeschreibung`` field overrides the list-API description
    (which is None for this endpoint). This gives the Matcher real text to
    embed and score against.
    """
    # --- external_id ---
    external_id: str | None = raw_job.get("refnr") or raw_job.get("hashId")
    if not external_id:
        raise ValueError("normalize_arbeitsagentur: missing id (no refnr or hashId)")

    # --- title ---
    title: str | None = raw_job.get("titel") or raw_job.get("beruf")
    if not title:
        raise ValueError("normalize_arbeitsagentur: missing title (no titel or beruf)")

    # --- company ---
    company: str | None = raw_job.get("arbeitgeber")

    # --- location ---
    location: str | None = None
    arbeitsort = raw_job.get("arbeitsort")
    if isinstance(arbeitsort, dict):
        ort: str | None = arbeitsort.get("ort")
        plz: str | None = arbeitsort.get("plz")
        if ort and plz:
            location = f"{ort}, {plz}"
        elif ort:
            location = ort

    # --- url ---
    url = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{external_id}"

    # --- description (preferred source: detail endpoint) ---
    description: str | None = None
    if detail is not None:
        full = detail.get("stellenbeschreibung")
        if isinstance(full, str) and full.strip():
            description = full

    return Job(
        source="arbeitsagentur",
        external_id=external_id,
        url=url,
        title=title,
        company=company,
        location=location,
        requirements=[],
        description=description,
    )


def normalize_adzuna(raw_job: dict[str, Any]) -> Job:  # noqa: ARG001
    """Stub: Adzuna normalizer not yet implemented."""
    raise NotImplementedError("adzuna normalizer pending — see docs/sources.md §1")


def normalize_jsearch(
    raw_job: dict[str, Any], detail: dict[str, Any] | None = None  # noqa: ARG001
) -> Job:
    """Map a raw JSearch / RapidAPI search-response item to a Job.

    JSearch returns the full description (``job_description``) inline in the
    search response, so there is no separate detail endpoint. The ``detail``
    argument is accepted only for signature uniformity with
    ``normalize_arbeitsagentur`` — its value is ignored.
    """
    # --- external_id ---
    external_id: str | None = raw_job.get("job_id")
    if not external_id:
        raise ValueError("normalize_jsearch: missing job_id")

    # --- title ---
    title: str | None = raw_job.get("job_title")
    if not title:
        raise ValueError("normalize_jsearch: missing job_title")

    # --- company ---
    company: str | None = raw_job.get("employer_name")

    # --- location: city, country (skip empties) ---
    city: str | None = raw_job.get("job_city")
    country: str | None = raw_job.get("job_country")
    location: str | None = None
    location_parts = [p for p in (city, country) if p]
    if location_parts:
        location = ", ".join(location_parts)

    # --- description (full, inline) ---
    description_raw = raw_job.get("job_description")
    description: str | None = (
        description_raw if isinstance(description_raw, str) and description_raw.strip() else None
    )

    # --- url ---
    url: str = raw_job.get("job_apply_link") or ""

    return Job(
        source="jsearch",
        external_id=external_id,
        url=url,
        title=title,
        company=company,
        location=location,
        requirements=[],
        description=description,
    )


def normalize(
    source: str, raw_job: dict[str, Any], detail: dict[str, Any] | None = None
) -> Job:
    """Dispatch to the correct normalizer based on source name.

    ``detail`` is forwarded only to ``normalize_arbeitsagentur`` (the other
    stubs ignore it). Backwards compatible: existing two-arg call sites are
    unaffected.
    """
    if source == "arbeitsagentur":
        return normalize_arbeitsagentur(raw_job, detail=detail)
    if source == "adzuna":
        return normalize_adzuna(raw_job)
    if source == "jsearch":
        return normalize_jsearch(raw_job)
    raise ValueError(f"normalize: unknown source {source!r}")
