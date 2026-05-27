"""Tests for ScoutAgent — all LLM/DB/HTTP calls mocked."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from job_agent.agents.scout_agent import ScoutAgent, ScoutResult  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_job(i: int) -> dict[str, Any]:
    """Return a minimal valid Arbeitsagentur list-response item."""
    return {
        "refnr": f"REF-{i:04d}",
        "titel": f"Software Engineer {i}",
        "arbeitgeber": f"Company {i}",
        "arbeitsort": {"ort": "Berlin", "plz": "10115"},
    }


def _make_mocks(raw_jobs: list[dict[str, Any]]) -> tuple[MagicMock, MagicMock]:
    """Return (client_mock, db_mock) pre-configured for a search returning raw_jobs."""
    client = MagicMock()
    client.search.return_value = {"stellenangebote": raw_jobs}

    db = MagicMock()
    db.raw.table.return_value.upsert.return_value.execute.return_value = MagicMock(
        data=[{}] * len(raw_jobs)
    )
    return client, db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScoutAgentEndToEnd:
    def test_run_end_to_end_10_jobs(self) -> None:
        """Sprint 2 gate: 10 jobs fetched, normalized, upserted."""
        raw_jobs = [_make_raw_job(i) for i in range(10)]
        client, db = _make_mocks(raw_jobs)

        agent = ScoutAgent(client=client, db=db)
        result = agent.run(keyword="Python", location="Berlin")

        assert isinstance(result, ScoutResult)
        assert result.fetched == 10
        assert result.normalized == 10
        assert result.upserted == 10
        assert result.errors == []

        # upsert called once with 10 dicts and correct on_conflict kwarg
        upsert_mock = db.raw.table.return_value.upsert
        upsert_mock.assert_called_once()
        args, kwargs = upsert_mock.call_args
        upserted_rows = args[0]
        assert len(upserted_rows) == 10
        assert all(isinstance(r, dict) for r in upserted_rows)
        assert kwargs.get("on_conflict") == "source,external_id"

    def test_dedupe_via_db_constraint(self) -> None:
        """Same 10 jobs sent twice — upsert called twice; DB handles dedupe."""
        raw_jobs = [_make_raw_job(i) for i in range(10)]
        client, db = _make_mocks(raw_jobs)

        agent = ScoutAgent(client=client, db=db)
        agent.run()
        agent.run()

        upsert_mock = db.raw.table.return_value.upsert
        assert upsert_mock.call_count == 2

        # Both calls should carry on_conflict
        for c in upsert_mock.call_args_list:
            assert c.kwargs.get("on_conflict") == "source,external_id"
            assert len(c.args[0]) == 10

    def test_partial_normalize_failures_collected(self) -> None:
        """3 jobs missing id fields → normalized==7, errors==3."""
        bad = {"titel": "No ID job", "arbeitgeber": "Acme"}  # no refnr, no hashId
        raw_jobs = [_make_raw_job(i) for i in range(7)] + [bad, bad, bad]

        client = MagicMock()
        client.search.return_value = {"stellenangebote": raw_jobs}

        db = MagicMock()
        db.raw.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[{}] * 7
        )

        agent = ScoutAgent(client=client, db=db)
        result = agent.run()

        assert result.fetched == 10
        assert result.normalized == 7
        assert result.upserted == 7
        assert len(result.errors) == 3

    def test_empty_response_no_upsert_call(self) -> None:
        """Empty stellenangebote list → no upsert call, all counts zero."""
        client = MagicMock()
        client.search.return_value = {"stellenangebote": []}

        db = MagicMock()

        agent = ScoutAgent(client=client, db=db)
        result = agent.run()

        assert result.fetched == 0
        assert result.normalized == 0
        assert result.upserted == 0
        assert result.errors == []

        db.raw.table.return_value.upsert.assert_not_called()

    def test_errors_capped_at_10(self) -> None:
        """11 bad jobs → errors list capped at 10 entries."""
        bad = {"titel": "No ID job", "arbeitgeber": "Acme"}
        raw_jobs = [bad] * 11
        client = MagicMock()
        client.search.return_value = {"stellenangebote": raw_jobs}
        db = MagicMock()

        agent = ScoutAgent(client=client, db=db)
        result = agent.run()

        assert result.fetched == 11
        assert result.normalized == 0
        assert result.upserted == 0
        assert len(result.errors) == 10  # capped

    def test_list_input_supported(self) -> None:
        """Bare list response (no stellenangebote key) works identically."""
        raw_jobs = [_make_raw_job(i) for i in range(10)]

        client = MagicMock()
        client.search.return_value = raw_jobs  # flat list, not a dict

        db = MagicMock()
        db.raw.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[{}] * 10
        )

        agent = ScoutAgent(client=client, db=db)
        result = agent.run()

        assert result.fetched == 10
        assert result.normalized == 10
        assert result.upserted == 10
        assert result.errors == []


# ---------------------------------------------------------------------------
# Detail fetching (task 2)
# ---------------------------------------------------------------------------


def test_scout_run_fetches_details() -> None:
    """Each normalised job triggers fetch_detail; counter reflects success count."""
    raw_jobs = [_make_raw_job(i) for i in range(3)]
    client, db = _make_mocks(raw_jobs)
    client.fetch_detail.return_value = {
        "stellenbeschreibung": "Full detail text for matching."
    }

    agent = ScoutAgent(client=client, db=db)
    result = agent.run()

    assert client.fetch_detail.call_count == 3
    # Called with each external_id (refnr) from the list rows.
    called_refs = [c.args[0] for c in client.fetch_detail.call_args_list]
    assert called_refs == ["REF-0000", "REF-0001", "REF-0002"]
    assert result.details_fetched == 3
    assert result.normalized == 3
    assert result.errors == []

    # Upserted rows now carry the detail-sourced description.
    upserted = db.raw.table.return_value.upsert.call_args.args[0]
    assert all(row["description"] == "Full detail text for matching." for row in upserted)


def test_scout_run_continues_on_detail_fetch_failure() -> None:
    """A failing fetch_detail is logged but does NOT abort the run."""
    from job_agent.tools.arbeitsagentur_client import ArbeitsagenturAPIError

    raw_jobs = [_make_raw_job(i) for i in range(3)]
    client, db = _make_mocks(raw_jobs)
    client.fetch_detail.side_effect = ArbeitsagenturAPIError(503, "upstream down")

    agent = ScoutAgent(client=client, db=db)
    result = agent.run()

    # All 3 jobs normalised (from list rows alone), but no details enriched.
    assert result.normalized == 3
    assert result.upserted == 3
    assert result.details_fetched == 0
    # Each failure is logged.
    assert len(result.errors) == 3
    assert all("detail fetch failed" in e for e in result.errors)
    assert all("upstream down" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Multi-source dispatch (task 3 — JSearch alongside Arbeitsagentur)
# ---------------------------------------------------------------------------


def _make_jsearch_raw(i: int) -> dict[str, Any]:
    return {
        "job_id": f"JS-{i:04d}",
        "job_title": f"Senior Engineer {i}",
        "employer_name": f"JS Company {i}",
        "job_city": "Remote",
        "job_country": "US",
        "job_description": f"Description {i}.",
        "job_apply_link": f"https://example.com/apply/{i}",
    }


def test_scout_constructor_rejects_both_client_and_clients() -> None:
    """Passing legacy client= and new clients= simultaneously is an error."""
    import pytest

    db = MagicMock()
    with pytest.raises(ValueError, match="either `client=` OR `clients=`"):
        ScoutAgent(client=MagicMock(), clients={"arbeitsagentur": MagicMock()}, db=db)


def test_scout_run_dispatches_to_multiple_sources() -> None:
    """run() merges results across all configured clients into one upsert."""
    raw_aa = [_make_raw_job(i) for i in range(2)]
    raw_js = [_make_jsearch_raw(i) for i in range(3)]

    aa_client = MagicMock()
    aa_client.search.return_value = {"stellenangebote": raw_aa}
    # Arbeitsagentur fetch_detail returns plain dict (not MagicMock) so we
    # control the detail-fetch counter precisely.
    aa_client.fetch_detail.return_value = {"stellenbeschreibung": "AA detail."}

    js_client = MagicMock(spec=["search"])  # no fetch_detail attribute
    js_client.search.return_value = {"data": raw_js}

    db = MagicMock()
    db.raw.table.return_value.upsert.return_value.execute.return_value = MagicMock(
        data=[{}] * 5
    )

    agent = ScoutAgent(
        clients={"arbeitsagentur": aa_client, "jsearch": js_client},
        db=db,
    )
    result = agent.run()

    assert result.fetched == 5  # 2 AA + 3 JSearch
    assert result.normalized == 5
    assert result.upserted == 5
    # Detail enrichment only happens for Arbeitsagentur (the only one with fetch_detail).
    assert result.details_fetched == 2
    js_client.search.assert_called_once()
    # The upserted batch carries rows from BOTH sources.
    upserted = db.raw.table.return_value.upsert.call_args.args[0]
    sources = {row["source"] for row in upserted}
    assert sources == {"arbeitsagentur", "jsearch"}


def test_scout_run_sources_param_filters_to_subset() -> None:
    """sources=['arbeitsagentur'] skips JSearch entirely, even if registered."""
    aa_client = MagicMock()
    aa_client.search.return_value = {"stellenangebote": [_make_raw_job(0)]}
    aa_client.fetch_detail.return_value = {"stellenbeschreibung": "x"}

    js_client = MagicMock(spec=["search"])
    js_client.search.return_value = {"data": [_make_jsearch_raw(0)]}

    db = MagicMock()
    db.raw.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{}])

    agent = ScoutAgent(
        clients={"arbeitsagentur": aa_client, "jsearch": js_client},
        db=db,
    )
    result = agent.run(sources=["arbeitsagentur"])

    aa_client.search.assert_called_once()
    js_client.search.assert_not_called()
    assert result.fetched == 1


def test_scout_run_one_source_failure_does_not_abort_other() -> None:
    """If JSearch raises 429, Arbeitsagentur results still land."""
    from job_agent.tools.jsearch_client import JSearchAPIError

    aa_client = MagicMock()
    aa_client.search.return_value = {"stellenangebote": [_make_raw_job(0)]}
    aa_client.fetch_detail.return_value = {"stellenbeschreibung": "x"}

    js_client = MagicMock(spec=["search"])
    js_client.search.side_effect = JSearchAPIError(429, "quota gone")

    db = MagicMock()
    db.raw.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{}])

    agent = ScoutAgent(
        clients={"arbeitsagentur": aa_client, "jsearch": js_client},
        db=db,
    )
    result = agent.run()

    # AA succeeded; JSearch logged-and-skipped.
    assert result.normalized == 1
    assert result.upserted == 1
    assert any("jsearch" in e and "search failed" in e for e in result.errors)
