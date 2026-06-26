"""Tests for the jobs + matches routers."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.main import create_app


def _client(db: MagicMock) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("u-1", "t")
    app.dependency_overrides[get_user_db] = lambda: db
    return TestClient(app)


def test_list_jobs_returns_rows() -> None:
    db = MagicMock()
    chain = db.raw.table.return_value.select.return_value.order.return_value.limit.return_value
    chain.execute.return_value.data = [{"id": "j1", "title": "Dev"}]
    r = _client(db).get("/api/jobs")
    assert r.status_code == 200
    assert r.json()[0]["title"] == "Dev"


def test_list_matches_filters_and_does_not_sort() -> None:
    """min_score filters; the server no longer sorts (sorting is client-side),
    so even a legacy ?sort=low_high is ignored and DB (score-desc) order is kept."""
    db = MagicMock()
    rows = [  # already in DB score-desc order
        {"id": "m2", "score": 80, "created_at": "2026-01-02"},
        {"id": "m3", "score": 60, "created_at": "2026-01-03"},
        {"id": "m1", "score": 40, "created_at": "2026-01-01"},
    ]
    chain = db.raw.table.return_value.select.return_value.order.return_value.limit.return_value
    chain.execute.return_value.data = rows

    r = _client(db).get("/api/matches?min_score=50&sort=low_high")
    assert r.status_code == 200
    # 40 filtered out; order preserved (NOT re-sorted to low->high).
    assert [m["id"] for m in r.json()] == ["m2", "m3"]


def _table_chain(db: MagicMock) -> MagicMock:
    """Shared fluent chain for `.table(...).select(...).limit(...).execute()`."""
    return db.raw.table.return_value.select.return_value.limit.return_value


def test_get_match_graph_no_profile_returns_empty() -> None:
    db = MagicMock()
    # No profile row → early return before any match_scores / RPC query.
    _table_chain(db).execute.return_value.data = []

    r = _client(db).get("/api/matches/graph")
    assert r.status_code == 200
    assert r.json() == {"profile": None, "jobs": []}


def test_get_match_graph_decouples_stages() -> None:
    """Stage 2 (match_scores) is the union of jobs; Stage 1 attaches where it
    exists. A job with no cosine value still appears with similarity=null."""
    db = MagicMock()

    # .table("profile")  → one profile row.
    _table_chain(db).execute.return_value.data = [
        {"id": "p-1", "skills": ["python", "react"]}
    ]

    # .table("match_scores").select(...).eq(...).order(...).limit(...).execute()
    #   → two scored jobs, joined to jobs(title, company).
    score_chain = (
        db.raw.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value
    )
    score_chain.execute.return_value.data = [
        {
            "job_id": "j2",
            "score": 88,
            "matched_skills": ["python"],
            "gaps": ["go"],
            "rationale": "ok",
            "jobs": {
                "title": "Sr Dev",
                "company": "Acme",
                "requirements": ["python", "go"],
                "description": "Build backend services.",
            },
        },
        {
            "job_id": "j1",
            "score": 55,
            "matched_skills": [],
            "gaps": [],
            "rationale": None,
            "jobs": {
                "title": "Jr Dev",
                "company": "Globex",
                "requirements": [],
                "description": None,
            },
        },
    ]

    # RPC → only j2 has a cosine value (j1 scored via the manual path).
    db.raw.rpc.return_value.execute.return_value.data = [
        {"job_id": "j2", "title": "Sr Dev", "company": "Acme", "similarity": 0.91},
    ]

    r = _client(db).get("/api/matches/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["profile"] == {"skills": ["python", "react"]}

    j2, j1 = body["jobs"]
    # j2 has both stages.
    assert j2["job_id"] == "j2"
    assert j2["title"] == "Sr Dev"
    assert j2["company"] == "Acme"
    assert j2["similarity"] == 0.91
    assert j2["score"] == 88.0
    assert j2["matched_skills"] == ["python"]
    assert j2["gaps"] == ["go"]
    assert j2["requirements"] == ["python", "go"]
    assert j2["description"] == "Build backend services."
    assert j1["requirements"] == []
    assert j1["description"] is None
    # j1 has Stage 2 only — Stage 1 (cosine) is null, but the job still shows.
    assert j1["job_id"] == "j1"
    assert j1["similarity"] is None
    assert j1["score"] == 55.0
    assert j1["matched_skills"] == []


def test_get_match_graph_no_scores_returns_profile_only() -> None:
    """Profile exists but no match_scores → empty job list, profile still sent."""
    db = MagicMock()
    table_mock = db.raw.table.return_value
    # Both the profile query and the match_scores query reuse the same mock; the
    # match_scores branch adds .eq().order().limit() before .execute().
    table_mock.select.return_value.limit.return_value.execute.return_value.data = [
        {"id": "p-1", "skills": ["python"]}
    ]
    (
        table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value
    ).data = []
    db.raw.rpc.return_value.execute.return_value.data = []

    r = _client(db).get("/api/matches/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["profile"] == {"skills": ["python"]}
    assert body["jobs"] == []
