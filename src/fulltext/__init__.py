"""OA full-text provider layer (swappable; arXiv is the first increment)."""

from __future__ import annotations

from src.fulltext.arxiv import ArxivProvider
from src.fulltext.base import (
    FullText,
    FulltextProvider,
    ProviderChain,
    attach_fulltext,
    effective_abstract,
    needs_fulltext,
)
from src.fulltext.cache import FulltextCache


def build_default_chain(cache_dir: str = "data/fulltext") -> ProviderChain:
    """The default resolution chain: arXiv first (keyless), backed by a per-id local cache.

    CORE / Europe PMC / OpenAlex oa_url PDF providers are appended here in later increments.
    """
    return ProviderChain([ArxivProvider()], cache=FulltextCache(cache_dir))


__all__ = [
    "FullText",
    "FulltextProvider",
    "ProviderChain",
    "FulltextCache",
    "ArxivProvider",
    "needs_fulltext",
    "effective_abstract",
    "attach_fulltext",
    "build_default_chain",
]
