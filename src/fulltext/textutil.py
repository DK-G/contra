"""Shared text helpers for full-text providers (length capping, prose-quality heuristics)."""

from __future__ import annotations

import re

_PROSE_CHARS = set(".,;:!?()[]-'\"%/&@+=°ãμ ")


def collapse_ws(text: str) -> str:
    """Collapse all runs of whitespace to single spaces and trim."""
    return re.sub(r"\s+", " ", text).strip()


def extract_excerpt(text: str, max_chars: int = 4000) -> str:
    """Take the leading prose up to max_chars, cut at a sentence end when possible."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    head = text[:max_chars]
    cut = head.rfind(". ")
    if cut > int(max_chars * 0.5):
        head = head[: cut + 1]
    return head.strip()


def prose_ratio(text: str) -> float:
    """Fraction of characters that look like natural-language prose (0.0–1.0).

    Used to reject garbage from best-effort PDF text extraction: a glyph-mangled PDF yields a
    low ratio (lots of control/odd bytes), real prose yields a high one.
    """
    if not text:
        return 0.0
    good = sum(1 for c in text if c.isalnum() or c.isspace() or c in _PROSE_CHARS)
    return good / len(text)


__all__ = ["collapse_ws", "extract_excerpt", "prose_ratio"]
