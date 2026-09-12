"""Theme-relevance matching for Track A anchors (GitHub / HuggingFace / Kaggle).

Why this module exists (``docs/field_observations_seihai.md`` F-14 / F-20, eight weeks of
zero useful harvest):

The three collectors each carried their own copy of "count include-keyword hits", and the copy
had three defects that made the relevance coefficient unable to order anything.

1. **Substring matching.** ``"cuped" in strong`` matched ``OpenPrinting/cups-filters`` — the
   printing subsystem was seated at rank 5 of a CUPED variance-reduction query (2026-09-05).
   Matching is now done on a normalised token stream at word boundaries.
2. **Separator blindness.** ``"quality-diversity"`` did not match the prose "quality diversity",
   so the subject's standard library lost credit it had earned. Normalisation folds ``-``/``_``/
   punctuation into spaces on BOTH sides before matching.
3. **Saturation.** The score was ``credit * 10`` capped at the source's maximum, so THREE matched
   keywords reached the cap and every further distinction vanished: on 2026-09-10 four anchors
   all scored relevance 1.0 and the ranking fell back to repo quality alone, seating an unrelated
   agent-skills collection above ``icaros-usc/pyribs`` by 1.0 point. Relevance is now the
   COVERAGE of the caller's keywords (credit / number of include keywords), so 3 of 5 reads 0.6
   and 5 of 5 reads 1.0.

The module is deterministic and LLM-free; the callers keep their own reliability scoring.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

# Body text (README / model card / dataset description) earns density-normalised partial credit:
# presence alone made LENGTH a relevance proxy, since a mega-README mentions everything once.
README_MIN_LEN = 1_000        # don't inflate credit for near-empty readmes
README_DENSITY_UNIT = 10_000  # occurrences per 10k chars (calibrated on live probes)

_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize(text: Any) -> str:
    """Lowercase, fold every non-alphanumeric run into a single space, and pad for matching."""
    return f" {_NON_WORD.sub(' ', str(text or '').lower()).strip()} "


def phrase_in(haystack_norm: str, needle_norm: str) -> bool:
    """Word-boundary containment on normalised text ('cuped' never matches 'cups')."""
    return bool(needle_norm.strip()) and needle_norm in haystack_norm


def phrase_count(haystack_norm: str, needle_norm: str) -> int:
    needle = needle_norm.strip()
    if not needle:
        return 0
    return haystack_norm.count(f" {needle} ")


def keyword_fit(
    include: Sequence[str],
    exclude: Sequence[str],
    strong_text: Any,
    body_text: Any = "",
    *,
    scale: int,
    exclude_penalty: int = 10,
    exclude_cap: int = 20,
) -> Dict[str, Any]:
    """Score how much of the caller's keyword set this anchor actually covers.

    ``strong_text`` is the identity surface (name / description / topics / tags) and earns full
    credit per keyword; ``body_text`` earns density-normalised partial credit. Returns the
    source-scaled ``score`` plus the parts the caller needs to explain it: ``coverage`` (0-1),
    ``matched`` (the keywords that hit, with where), and ``exclude_hits``.
    """
    strong = normalize(strong_text)
    body = normalize(body_text)
    body_len = max(len(str(body_text or "")), README_MIN_LEN) / README_DENSITY_UNIT

    terms = [t for t in (str(x or "").strip() for x in include) if t]
    credit = 0.0
    matched: List[Dict[str, Any]] = []
    for term in terms:
        needle = normalize(term)
        if phrase_in(strong, needle):
            credit += 1.0
            matched.append({"keyword": term, "where": "name/description/topics", "credit": 1.0})
        elif body.strip():
            part = min(phrase_count(body, needle) / body_len, 1.0)
            if part > 0:
                credit += part
                matched.append({"keyword": term, "where": "readme", "credit": round(part, 2)})

    exclude_hits = 0
    for term in (str(x or "").strip() for x in exclude):
        if not term:
            continue
        needle = normalize(term)
        if phrase_in(strong, needle) or phrase_in(body, needle):
            exclude_hits += 1

    coverage = (credit / len(terms)) if terms else 0.0
    score = int(round(coverage * scale)) - min(exclude_hits * exclude_penalty, exclude_cap)
    return {
        "score": max(score, 0),
        "coverage": round(coverage, 3),
        "credit": round(credit, 3),
        "keywords": len(terms),
        "matched": matched,
        "exclude_hits": exclude_hits,
    }


def matched_summary(matched: Sequence[Dict[str, Any]], keywords: int) -> str:
    """One human-readable line: which keywords hit, and where — the per-anchor evidence.

    F-14: every anchor's RELATIONSHIP line read the same template sentence, so the caller could
    not tell a subject hit from a coincidence. This is the deterministic part of that answer.
    """
    if not matched:
        return f"一致キーワード なし（0/{keywords}）"
    parts = []
    for m in matched:
        where = "名前/説明/topics" if m.get("where") == "name/description/topics" else "README"
        credit = m.get("credit", 0)
        parts.append(f"{m['keyword']}（{where}{'' if credit >= 1.0 else f'・部分 {credit}'}）")
    return f"一致キーワード {len(matched)}/{keywords}: " + " / ".join(parts)


__all__ = [
    "README_MIN_LEN",
    "README_DENSITY_UNIT",
    "keyword_fit",
    "matched_summary",
    "normalize",
    "phrase_count",
    "phrase_in",
]
