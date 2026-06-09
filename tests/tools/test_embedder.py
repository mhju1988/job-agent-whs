"""Tests for src/job_agent/tools/embedder.py — all LLM calls mocked."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from job_agent.config import MissingCredentialsError
from job_agent.tools.embedder import (
    EMBED_DIM,
    MAX_INPUT_WORDS,
    Embedder,
    EmbeddingServiceError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_client(
    query_return: list[float] | None = None,
    docs_return: list[list[float]] | None = None,
    query_side_effect: Exception | None = None,
    docs_side_effect: Exception | None = None,
) -> MagicMock:
    client = MagicMock()
    if query_side_effect is not None:
        client.embed_query.side_effect = query_side_effect
    else:
        default_q = [0.0] * EMBED_DIM
        client.embed_query.return_value = (
            query_return if query_return is not None else default_q
        )
    if docs_side_effect is not None:
        client.embed_documents.side_effect = docs_side_effect
    else:
        default_d = [[0.0] * EMBED_DIM]
        client.embed_documents.return_value = (
            docs_return if docs_return is not None else default_d
        )
    return client


def _long_text(n_words: int = 1000) -> str:
    return " ".join(f"word{i}" for i in range(n_words))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_embed_text_returns_correct_dimension() -> None:
    client = make_client(query_return=[0.0] * EMBED_DIM)
    emb = Embedder(client=client)
    result = emb.embed_text("hello world")
    assert len(result) == EMBED_DIM


def test_embed_text_truncates_long_input() -> None:
    client = make_client(query_return=[0.0] * EMBED_DIM)
    emb = Embedder(client=client)
    emb.embed_text(_long_text(1000))
    call_arg: str = client.embed_query.call_args[0][0]
    word_count = len(call_arg.split())
    assert word_count <= MAX_INPUT_WORDS


def test_embed_text_wrong_dim_raises() -> None:
    client = make_client(query_return=[0.0] * 999)
    emb = Embedder(client=client)
    with pytest.raises(EmbeddingServiceError) as exc_info:
        emb.embed_text("test")
    msg = str(exc_info.value)
    assert "GWDG embeddings" in msg
    assert "docs.hpc.gwdg.de" in msg
    assert "unexpected vector shape" in msg


def test_embed_text_upstream_error_wrapped() -> None:
    client = make_client(query_side_effect=RuntimeError("boom"))
    emb = Embedder(client=client)
    with pytest.raises(EmbeddingServiceError) as exc_info:
        emb.embed_text("test")
    msg = str(exc_info.value)
    assert "GWDG embeddings" in msg
    assert "docs.hpc.gwdg.de" in msg


def test_embed_texts_batch() -> None:
    batch = [[float(i)] * EMBED_DIM for i in range(3)]
    client = make_client(docs_return=batch)
    emb = Embedder(client=client)
    results = emb.embed_texts(["a", "b", "c"])
    assert len(results) == 3
    for vec in results:
        assert len(vec) == EMBED_DIM


def test_embed_texts_batch_truncation_applied_per_item() -> None:
    long_item = _long_text(1000)
    inputs = ["short text", long_item, "also short"]
    docs_return = [[0.0] * EMBED_DIM for _ in inputs]
    client = make_client(docs_return=docs_return)
    emb = Embedder(client=client)
    emb.embed_texts(inputs)
    call_args: list[str] = client.embed_documents.call_args[0][0]
    # The long item was at index 1
    assert len(call_args[1].split()) <= MAX_INPUT_WORDS


def test_missing_credentials_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Clear any env vars set by the host shell so the test is hermetic even
    # when a real .env is exported in the developer's environment.
    for var in ("GWDG_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    from job_agent.config import Settings

    settings = Settings(gwdg_api_key="", supabase_url="", supabase_key="")
    with pytest.raises(MissingCredentialsError):
        Embedder(settings=settings)
