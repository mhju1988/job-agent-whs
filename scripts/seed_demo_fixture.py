"""Seed the deterministic Sprint 2 demo fixture.

Produces three JSON files under tests/fixtures/sprint2_demo/:

  profile.json       — frozen profile row (including embedding) the demo uses
  jobs.json          — frozen jobs that were in Supabase at seed time
  expected_top5.json — RPC top-N rows + recorded LLM (prompt, response) pairs
                       + the resulting MatcherResult

Together these freeze the entire Sprint 2 Matcher pipeline so a peer reviewer
can run::

    pytest tests/agents/test_matcher_agent.py::test_matcher_against_sprint2_demo_fixture

and confirm the reported slide numbers reproduce exactly.

Assumes:
- Supabase migrations 001..006 are applied
- GWDG credentials in .env
- The `jobs` table is populated (run Scout first if not)

Usage:
    uv run python scripts/seed_demo_fixture.py --cv path/to/cv.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from job_agent.agents.base_agent import BaseAgent
from job_agent.agents.matcher_agent import MatcherAgent
from job_agent.db.client import SupabaseClient
from job_agent.tools.cv_parser import CVParser
from job_agent.tools.embedder import Embedder

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sprint2_demo"
DEFAULT_TOP_N = 5
MIN_JOBS_REQUIRED = 5


class RecordingLLM:
    """Wraps a BaseAgent and records every (prompt, response) pair.

    Used during seeding to capture the LLM responses the regression test
    replays. The test is therefore deterministic without needing GWDG.
    """

    def __init__(self, real: BaseAgent) -> None:
        self._real = real
        self.calls: list[dict[str, str]] = []

    def ask(self, prompt: str) -> str:
        response = self._real.ask(prompt)
        self.calls.append({"prompt": prompt, "response": response})
        return response


def _upsert_profile_from_cv(
    cv_path: Path,
    db: SupabaseClient,
    embedder: Embedder,
    cv_parser: CVParser,
) -> dict[str, object]:
    """Parse CV → Profile → embed → upsert. Return the inserted row including id."""
    print(f"[1/6] Parsing CV: {cv_path}")
    profile = cv_parser.parse(cv_path)
    print(f"      Skills: {len(profile.skills)} | "
          f"Experience: {len(profile.experience)} | "
          f"Education: {len(profile.education)}")

    print("[2/6] Embedding profile via GWDG...")
    embedding = embedder.embed_text(profile.to_embedding_text())
    print(f"      Embedding dim: {len(embedding)}")

    row = profile.to_supabase_row()
    row["embedding"] = embedding

    # Delete any prior demo profile to keep this idempotent (single-profile demo).
    db.raw.table("profile").delete().neq(
        "id", "00000000-0000-0000-0000-000000000000"
    ).execute()

    resp = db.raw.table("profile").insert(row).execute()
    inserted = resp.data[0]
    print(f"      Profile ID: {inserted['id']}")
    return inserted


def _fetch_jobs_from_db(db: SupabaseClient, limit: int = 100) -> list[dict[str, object]]:
    print(f"[3/6] Fetching up to {limit} jobs from Supabase...")
    resp = db.raw.table("jobs").select("*").limit(limit).execute()
    jobs = resp.data or []
    print(f"      Found {len(jobs)} jobs")
    return jobs


def _run_matcher_with_recording(
    db: SupabaseClient,
    profile_id: str,
    top_n: int,
    base_agent: BaseAgent,
) -> tuple[object, list[dict[str, str]]]:
    print(f"[4/6] Running matcher (top_n={top_n}) with recording LLM...")
    recorder = RecordingLLM(base_agent)
    matcher = MatcherAgent(db=db, llm_agent=recorder)
    result = matcher.run(profile_id, top_n=top_n, exclude_scored=False)
    print(f"      Considered: {result.candidates_considered} | "
          f"Scored: {result.scored} | Persisted: {result.persisted}")
    if result.errors:
        print(f"      WARNING: {len(result.errors)} errors during matching:")
        for err in result.errors[:5]:
            print(f"        - {err}")
    return result, recorder.calls


def _capture_rpc_rows(
    db: SupabaseClient,
    profile_id: str,
    top_n: int,
) -> list[dict[str, object]]:
    print("[5/6] Re-running RPC to capture top-N rows for the fixture...")
    # exclude_scored=False so we get the same set as the matcher saw the first time
    # (the matcher just inserted them; exclude_scored=True now would return [])
    resp = db.raw.rpc(
        "match_jobs_for_profile",
        {"profile_id": profile_id, "top_n": top_n, "exclude_scored": False},
    ).execute()
    rows = resp.data or []
    print(f"      Captured {len(rows)} RPC rows")
    return rows


def _write_fixtures(
    profile_row: dict[str, object],
    jobs: list[dict[str, object]],
    rpc_rows: list[dict[str, object]],
    llm_calls: list[dict[str, str]],
    matcher_result: object,
) -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[6/6] Writing fixtures to {FIXTURE_DIR}")

    (FIXTURE_DIR / "profile.json").write_text(
        json.dumps(profile_row, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    (FIXTURE_DIR / "jobs.json").write_text(
        json.dumps(jobs, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    expected = {
        "matcher_result": matcher_result.model_dump(),  # type: ignore[attr-defined]
        "rpc_rows": rpc_rows,
        "llm_calls": llm_calls,
    }
    (FIXTURE_DIR / "expected_top5.json").write_text(
        json.dumps(expected, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    for p in sorted(FIXTURE_DIR.iterdir()):
        size_kb = p.stat().st_size / 1024
        print(f"      {p.name:24s} {size_kb:7.1f} KB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cv", type=Path, required=True,
                    help="Path to CV PDF to use as the demo profile")
    ap.add_argument("--top-n", type=int, default=DEFAULT_TOP_N,
                    help=f"Top-N to capture (default {DEFAULT_TOP_N})")
    args = ap.parse_args()

    if not args.cv.exists():
        print(f"ERROR: CV file not found: {args.cv}", file=sys.stderr)
        return 1

    db = SupabaseClient()
    embedder = Embedder()
    base_agent = BaseAgent()
    cv_parser = CVParser(llm_agent=base_agent)

    profile_row = _upsert_profile_from_cv(args.cv, db, embedder, cv_parser)
    profile_id = str(profile_row["id"])

    jobs = _fetch_jobs_from_db(db)
    if len(jobs) < MIN_JOBS_REQUIRED:
        print(
            f"\nERROR: Only {len(jobs)} jobs in DB; need at least {MIN_JOBS_REQUIRED}.\n"
            "Run Scout first, e.g.:\n"
            "  uv run python -c \"from job_agent.agents.scout_agent import ScoutAgent; "
            "from job_agent.tools.arbeitsagentur_client import ArbeitsagenturClient; "
            "ScoutAgent(client=ArbeitsagenturClient.with_default_opener())"
            ".run(query='Python Developer', page_size=20)\"\n",
            file=sys.stderr,
        )
        return 1

    matcher_result, llm_calls = _run_matcher_with_recording(
        db, profile_id, args.top_n, base_agent
    )

    if matcher_result.scored == 0:  # type: ignore[attr-defined]
        print(
            "\nERROR: Matcher scored 0 jobs. Check earlier errors before retrying.",
            file=sys.stderr,
        )
        return 1

    rpc_rows = _capture_rpc_rows(db, profile_id, args.top_n)

    # Re-fetch jobs so the fixture includes any embeddings populated during matching.
    jobs = _fetch_jobs_from_db(db)

    _write_fixtures(profile_row, jobs, rpc_rows, llm_calls, matcher_result)
    print("\nDone. Run the regression test:")
    print("  uv run pytest tests/agents/test_matcher_agent.py::"
          "test_matcher_against_sprint2_demo_fixture -v")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
