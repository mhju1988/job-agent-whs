"""Tests for delete/hide request schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from job_agent.api.schemas import (
    DeleteApplicationsRequest,
    DeleteApplicationsResponse,
    HideJobsRequest,
)


def test_hide_jobs_request_defaults_empty() -> None:
    assert HideJobsRequest().job_ids == []


def test_hide_jobs_request_accepts_ids() -> None:
    assert HideJobsRequest(job_ids=["a", "b"]).job_ids == ["a", "b"]


def test_hide_jobs_request_rejects_over_cap() -> None:
    with pytest.raises(ValidationError):
        HideJobsRequest(job_ids=[str(i) for i in range(201)])


def test_hide_jobs_request_forbids_extra() -> None:
    with pytest.raises(ValidationError):
        HideJobsRequest(job_ids=[], bogus=1)  # type: ignore[call-arg]


def test_delete_applications_request_accepts_ids() -> None:
    assert DeleteApplicationsRequest(application_ids=["x"]).application_ids == ["x"]


def test_delete_applications_response_shape() -> None:
    r = DeleteApplicationsResponse(deleted=2, files_deleted=3)
    assert r.deleted == 2 and r.files_deleted == 3
