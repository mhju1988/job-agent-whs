"""Content-level validation for LLM-generated cover letter text.

The pydantic ``CoverLetterContent`` model only enforces *shape* (three strings).
This module enforces *quality* constraints that catch the failure modes we see
with the small GWDG/NIM models: stock filler, wrong-language output, and
runaway length. It is deliberately dependency-free (no langdetect) so it stays
cheap and deterministic.

``validate_letter`` returns a list of human-readable issues; an empty list means
the letter passed. The renderer uses the issue list to drive a bounded
generate→validate→retry loop.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from job_agent.models.cover_letter import CoverLetterContent

#: Phrases that signal generic, templated, or machine-generated prose.
#: Matched case-insensitively as substrings of the joined letter text. Keep
#: this list conservative — false positives here would reject valid letters.
BANNED_PHRASES: tuple[str, ...] = (
    "as an ai",
    "i am writing to apply for",  # stock opener the prompt already discourages
    "to whom it may concern",
    "i am confident that",  # hollow filler
    "perfect fit for",  # hollow superlative
    "in today's fast-paced",
    "needle in a haystack",
    "delve into",
    "it is worth noting that",
)

#: German closed-class/function words. A German letter must contain several of
#: these; their near-total absence is a reliable signal that the model ignored
#: the "write in German" instruction and emitted English instead.
_GERMAN_STOPWORDS: frozenset[str] = frozenset(
    {
        "ich", "und", "die", "der", "das", "mit", "von", "fur", "für",
        "ein", "eine", "mich", "sich", "auf", "als", "bei", "den", "dem",
        "ist", "haben", "habe", "werden", "kann", "sowie", "auch", "nicht",
        "sondern", "diese", "meine", "meiner", "sowohl", "wurde", "wird",
    }
)

#: Word-count bounds per section. Lower bounds guard against the model
#: returning a near-empty string; upper bounds guard against runaway length.
_MIN_WORDS_OPENING = 4
_MIN_WORDS_BODY = 12
_MAX_WORDS_OPENING = 120
_MAX_WORDS_BODY = 350
_MIN_WORDS_CLOSING = 2
_MAX_WORDS_CLOSING = 60


@dataclass(frozen=True)
class LetterIssue:
    """A single validation finding."""

    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


def _normalize(text: str) -> str:
    """Lowercase + strip accents for word/phrase matching.

    Accent stripping lets 'Grüßen' match 'gruessen'-style normalisation and
    keeps the German-stopword check robust to umlaut variants.
    """
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _word_count(text: str) -> int:
    return len(text.split())


def _german_word_ratio(text: str) -> float:
    """Fraction of German stopwords present (0–1) in *text*."""
    words = _normalize(text).split()
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in _GERMAN_STOPWORDS)
    return hits / len(words)


def validate_letter(
    content: CoverLetterContent,
    *,
    language: str = "en",
) -> list[LetterIssue]:
    """Return a list of quality issues for *content*; empty list means pass.

    Parameters
    ----------
    content:    the parsed cover-letter content.
    language:   requested language ("en" or "de"). "de" enforces a minimum
                German stopword presence; "en" applies no positive-language
                check (only banned-phrase + length).
    """
    issues: list[LetterIssue] = []
    full = f"{content.opening}\n{content.body}\n{content.closing}"
    full_norm = _normalize(full)

    # --- Banned phrases --------------------------------------------------
    for phrase in BANNED_PHRASES:
        if _normalize(phrase) in full_norm:
            issues.append(
                LetterIssue(
                    code="banned_phrase",
                    message=f"contains stock/generic phrase: {phrase!r}",
                )
            )

    # --- Length per section ---------------------------------------------
    opening_wc = _word_count(content.opening)
    body_wc = _word_count(content.body)
    closing_wc = _word_count(content.closing)

    if opening_wc < _MIN_WORDS_OPENING:
        issues.append(
            LetterIssue(
                "opening_too_short",
                f"opening has {opening_wc} words (min {_MIN_WORDS_OPENING})",
            )
        )
    elif opening_wc > _MAX_WORDS_OPENING:
        issues.append(
            LetterIssue(
                "opening_too_long",
                f"opening has {opening_wc} words (max {_MAX_WORDS_OPENING})",
            )
        )

    if body_wc < _MIN_WORDS_BODY:
        issues.append(
            LetterIssue(
                "body_too_short",
                f"body has {body_wc} words (min {_MIN_WORDS_BODY})",
            )
        )
    elif body_wc > _MAX_WORDS_BODY:
        issues.append(
            LetterIssue(
                "body_too_long",
                f"body has {body_wc} words (max {_MAX_WORDS_BODY})",
            )
        )

    if closing_wc < _MIN_WORDS_CLOSING:
        issues.append(
            LetterIssue(
                "closing_too_short",
                f"closing has {closing_wc} words (min {_MIN_WORDS_CLOSING})",
            )
        )
    elif closing_wc > _MAX_WORDS_CLOSING:
        issues.append(
            LetterIssue(
                "closing_too_long",
                f"closing has {closing_wc} words (max {_MAX_WORDS_CLOSING})",
            )
        )

    # --- Language match (German) ----------------------------------------
    # A German letter must contain a meaningful share of German function
    # words. Below the threshold, the model almost certainly ignored the
    # language instruction.
    if language == "de":
        ratio = _german_word_ratio(full)
        if ratio < 0.04:
            issues.append(
                LetterIssue(
                    "language_mismatch",
                    f"requested German but only {ratio:.0%} German stopwords found",
                )
            )

    return issues


def passes(content: CoverLetterContent, *, language: str = "en") -> bool:
    """Convenience: True iff ``validate_letter`` finds no issues."""
    return not validate_letter(content, language=language)
