"""GWDG embedding tool using langchain-openai's OpenAIEmbeddings."""

from __future__ import annotations

from typing import Any, Final, Protocol

from job_agent.config import Settings


class _EmbeddingsClient(Protocol):
    """Structural type for any client we can use to call /v1/embeddings."""

    def embed_query(self, text: str) -> list[float]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

EMBED_DIM: Final[int] = 1024
# Two-axis truncation against the 512-token hard limit on multilingual-e5.
# Word-based alone is unreliable for German CVs (compound nouns like
# "Bundesausbildungsförderungsgesetz" can tokenize to 8+ subwords, pushing
# the tokens-per-word ratio above 1.8). We additionally cap by character
# count: e5 averages ~4 chars/token on Latin-script text, so 1800 chars caps
# at ~450 tokens with ~12% headroom.
MAX_INPUT_WORDS: Final[int] = 300
MAX_INPUT_CHARS: Final[int] = 1800


class EmbeddingServiceError(Exception):
    """Raised when the GWDG embedding endpoint returns an error or unexpected shape."""


class Embedder:
    """Wraps the GWDG OpenAI-compatible embeddings endpoint."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: _EmbeddingsClient | None = None,
    ) -> None:
        if client is not None:
            self._client: _EmbeddingsClient = client
        else:
            cfg = settings if settings is not None else Settings()
            cfg.require_live_credentials()
            # Deferred import: keeps test import time fast and avoids any
            # network-adjacent client construction at module load.
            # Do NOT hoist to module scope.
            from langchain_openai import OpenAIEmbeddings  # noqa: PLC0415

            self._client = OpenAIEmbeddings(
                model=cfg.gwdg_embed_model,
                base_url=cfg.gwdg_api_base,
                api_key=cfg.gwdg_api_key,  # type: ignore[arg-type]
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate(text: str) -> str:
        words = text.split()
        if len(words) > MAX_INPUT_WORDS:
            words = words[:MAX_INPUT_WORDS]
        out = " ".join(words)
        if len(out) > MAX_INPUT_CHARS:
            # Cut on a word boundary if possible — avoids handing the
            # tokenizer a half-word that explodes into many subword tokens.
            cut = out.rfind(" ", 0, MAX_INPUT_CHARS)
            out = out[: cut if cut > 0 else MAX_INPUT_CHARS]
        return out

    @staticmethod
    def _validate_vector(vec: Any, context: str = "") -> list[float]:
        if not isinstance(vec, list) or len(vec) != EMBED_DIM:
            where = f" for {context}" if context else ""
            raise EmbeddingServiceError(
                f"GWDG embeddings endpoint returned unexpected vector shape{where}: "
                f"expected list of length {EMBED_DIM}, got {type(vec).__name__} "
                f"of length {len(vec) if isinstance(vec, list) else 'N/A'}. "
                "See https://docs.hpc.gwdg.de/services/ai-services/saia/index.html"
                " for service status."
            )
        return vec

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_text(self, text: str) -> list[float]:
        """Return a single embedding vector for *text*."""
        truncated = self._truncate(text)
        try:
            result: Any = self._client.embed_query(truncated)
        except Exception as exc:
            raise EmbeddingServiceError(
                f"GWDG embeddings endpoint call failed ({type(exc).__name__}): {exc}. "
                "see https://docs.hpc.gwdg.de/services/ai-services/saia/index.html"
                " for service status"
            ) from exc
        return self._validate_vector(result)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return a batch of embedding vectors for *texts*."""
        truncated = [self._truncate(t) for t in texts]
        try:
            results: Any = self._client.embed_documents(truncated)
        except Exception as exc:
            raise EmbeddingServiceError(
                f"GWDG embeddings endpoint call failed ({type(exc).__name__}): {exc}. "
                "see https://docs.hpc.gwdg.de/services/ai-services/saia/index.html"
                " for service status"
            ) from exc
        validated: list[list[float]] = []
        for i, vec in enumerate(results):
            validated.append(self._validate_vector(vec, context=f"item {i}"))
        return validated
