"""Full-text provider layer: protocol, provider chain, gating, and abstract enrichment.

This is the swappable OA full-text resolution layer that補強s thin abstracts so the
Track B mechanism判定 (P/M structure abduction in classify.py) has more material to work
with. It is an INPUT layer only — it never changes the serendipity score formula or its
gate thresholds (spec.md §4). Resolution order is defined by the provider chain; the first
increment ships only the arXiv provider (see arxiv.py), with CORE / Europe PMC / OpenAlex
oa_url PDF deferred to later increments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple, runtime_checkable

from src.core.models import Work


@dataclass
class FullText:
    """A resolved full-text excerpt for one work (already cleaned + length-capped).

    `text` is the de-noised excerpt the provider produced — never the raw LaTeX/PDF — so it
    can be concatenated onto an abstract and fed straight to the LLM scorer.
    """
    work_id: str
    source: str
    source_id: str = ""
    url: str = ""
    text: str = ""
    char_count: int = 0
    fetched_at: str = ""
    truncated: bool = False


@runtime_checkable
class FulltextProvider(Protocol):
    """A swappable full-text source. Returns None when it cannot resolve the work."""

    name: str

    def resolve_fulltext(self, work: Work) -> Optional[FullText]:
        ...


class ProviderChain:
    """Try providers in priority order; return the first full text resolved.

    A per-work-id cache (optional) short-circuits resolution AND records misses, so a
    re-run never re-fetches the same work. A provider raising is treated as a miss for that
    provider (the chain moves on); the existing abstract-only flow is the ultimate fallback.
    """

    def __init__(self, providers: List[FulltextProvider], cache=None) -> None:
        self.providers = list(providers)
        self.cache = cache

    def resolve(self, work: Work) -> Optional[FullText]:
        wid = work.id
        if self.cache is not None and wid:
            cached, ft = self.cache.lookup(wid)
            if cached:
                return ft
        result: Optional[FullText] = None
        for provider in self.providers:
            try:
                result = provider.resolve_fulltext(work)
            except Exception:  # a flaky provider must not break the pipeline
                result = None
            if result is not None:
                break
        if self.cache is not None and wid:
            self.cache.store(wid, result)
        return result


def _is_oa(work: Work) -> bool:
    """Open-access signal from parsed OpenAlex metadata (or an arXiv hint in source_meta).

    arXiv works are inherently OA; an oa_url / arxiv url is also a sufficient OA signal even
    when the boolean is_oa flag is absent.
    """
    sm = getattr(work, "source_meta", None) or {}
    return bool(sm.get("is_oa") or sm.get("oa_url") or sm.get("arxiv_id") or sm.get("arxiv_url"))


# Default short-abstract threshold. OpenAlex abstracts reconstructed from the inverted index
# are often a single thin sentence; below this length the mechanism判定 is starved, which is
# exactly the case full text補強 targets. CLI-tunable via --fulltext-max-abstract.
_DEFAULT_MAX_ABSTRACT_CHARS = 280


def needs_fulltext(work: Work, *, max_abstract_chars: int = _DEFAULT_MAX_ABSTRACT_CHARS) -> bool:
    """Gate full-text fetching: only OA works whose abstract is short (無駄打ち防止).

    Returns False for closed-access works (we cannot legally/usefully fetch them here) and for
    works whose abstract is already substantial (full text would add little mechanism signal).
    """
    if not _is_oa(work):
        return False
    abstract = work.abstract or ""
    return len(abstract) < max_abstract_chars


def effective_abstract(work: Work, abstract_chars: int = 500, fulltext_chars: int = 1200) -> str:
    """The text handed to the mechanism scorer: abstract, optionally augmented with full text.

    When no full text has been attached (the default / --fulltext off) this returns exactly
    ``(work.abstract or "")[:abstract_chars]`` — byte-identical to the prior scorer input, so
    behavior and existing tests are unchanged. When a full-text excerpt is present it is
    appended (the abstract is kept, never replaced) so the LLM sees more mechanism material.
    The score formula and thresholds are untouched; only the input text differs.
    """
    base = (work.abstract or "")[:abstract_chars]
    sm = getattr(work, "source_meta", None) or {}
    excerpt = sm.get("fulltext_excerpt")
    if excerpt:
        excerpt = str(excerpt)[:fulltext_chars]
        if base:
            return f"{base}\n\n[全文抜粋]\n{excerpt}"
        return f"[全文抜粋]\n{excerpt}"
    return base


def attach_fulltext(work: Work, fulltext: Optional[FullText]) -> bool:
    """Store a resolved excerpt onto the work's source_meta (no models.py change required).

    Returns True if something was attached. Non-breaking: source_meta is an existing flexible
    dict field, so this carries the full text without altering the Work dataclass structure.
    """
    if fulltext is None or not fulltext.text:
        return False
    work.source_meta["fulltext_excerpt"] = fulltext.text
    work.source_meta["fulltext_source"] = fulltext.source
    work.source_meta["fulltext_source_id"] = fulltext.source_id
    return True


__all__ = [
    "FullText",
    "FulltextProvider",
    "ProviderChain",
    "needs_fulltext",
    "effective_abstract",
    "attach_fulltext",
]
