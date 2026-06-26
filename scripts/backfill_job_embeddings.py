"""Backfill ``jobs.embedding`` for jobs scraped before Scout embedded them.

Jobs scraped via the normal Scout pipeline now get a vector at scrape time
(see ScoutAgent.embedder). This script is a one-time / on-demand backfill for
jobs already in the table that lack an embedding — without it the stage-1
cosine-match RPC (``match_jobs_for_profile``) silently skips them via its
``where j.embedding is not null`` guard, so they never appear in the fit graph.

Idempotent: only touches rows whose ``embedding IS NULL``. Safe to re-run.

Embedding is done one job per request: the GWDG multilingual-e5 endpoint caps
each *request* at 512 tokens (not each text), so batching many jobs in one call
fails as soon as any long description pushes the batch over the limit. Per-job
calls route through ``Embedder.embed_text`` which truncates each text to stay
under the limit, and an error on one job never sinks the others.

Usage::

    uv run python scripts/backfill_job_embeddings.py [--dry-run]

Pre-conditions: migrations applied, GWDG /embeddings endpoint reachable.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, cast

from job_agent.db.client import SupabaseClient
from job_agent.tools.embedder import Embedder, EmbeddingServiceError

log = logging.getLogger("backfill_job_embeddings")


def _job_text(row: dict[str, Any]) -> str:
    """Rebuild a job's embedding text from a raw DB row.

    Mirrors ``Job.to_embedding_text()`` but operates on the untyped dict that
    PostgREST returns, so we don't need to construct a validated ``Job`` just
    to embed.
    """
    parts: list[str] = []
    if row.get("title"):
        parts.append(str(row["title"]))
    if row.get("company"):
        parts.append(str(row["company"]))
    reqs = row.get("requirements") or []
    if reqs:
        parts.append(", ".join(cast("list[str]", reqs)))
    if row.get("description"):
        parts.append(str(row["description"]))
    return "\n".join(parts)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="List counts only; write nothing.")
    args = parser.parse_args()

    db = SupabaseClient()
    embedder = Embedder()

    rows = (
        db.raw.table("jobs")
        .select("id, title, company, requirements, description, embedding")
        .execute()
        .data
        or []
    )
    missing = [r for r in rows if r.get("embedding") is None]
    log.info("jobs total=%d, missing embeddings=%d", len(rows), len(missing))

    if args.dry_run:
        log.info("dry-run: no writes performed.")
        return 0

    if not missing:
        log.info("nothing to do — every job already has an embedding.")
        return 0

    # One request per job: per-text truncation keeps each under the 512-token
    # cap, and a failure on one job is logged without aborting the rest.
    done = 0
    errors = 0
    for row in missing:
        try:
            vec = embedder.embed_text(_job_text(row))
        except EmbeddingServiceError as exc:
            log.error(
                "job %s failed: %s",
                row.get("id"),
                str(exc).splitlines()[0],
            )
            errors += 1
            continue
        db.raw.table("jobs").update({"embedding": vec}).eq("id", row["id"]).execute()
        done += 1
        if done % 10 == 0:
            log.info("embedded %d/%d", done, len(missing))

    log.info("done: embedded=%d, errors=%d", done, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
