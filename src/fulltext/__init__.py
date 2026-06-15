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
from src.fulltext.core import CoreProvider
from src.fulltext.europepmc import EuropePmcProvider
from src.fulltext.ia_scholar import IaScholarProvider
from src.fulltext.oa_pdf import OaPdfProvider


def build_default_chain(cache_dir: str = "data/fulltext") -> ProviderChain:
    """The default OA full-text resolution chain (plan.md provider order), per-id cache backed.

      1. arXiv e-print  — keyless, lowest noise (LaTeX source).
      2. Europe PMC     — keyless, non-arXiv OA full text (JATS XML).
      3. IA Scholar     — keyless, archived OA full text via fatcat (best-effort PDF).
      4. CORE           — broad OA coverage; only active when CORE_API_KEY is set (else skipped).
      5. OpenAlex oa_url PDF — generic best-effort fallback (Unpaywall-derived oa_url).

    Each provider returns None when it cannot resolve a work, so the chain degrades gracefully
    to the abstract-only path. CORE self-disables without its env key.
    """
    return ProviderChain(
        [
            ArxivProvider(),
            EuropePmcProvider(),
            IaScholarProvider(),
            CoreProvider(),
            OaPdfProvider(),
        ],
        cache=FulltextCache(cache_dir),
    )


__all__ = [
    "FullText",
    "FulltextProvider",
    "ProviderChain",
    "FulltextCache",
    "ArxivProvider",
    "EuropePmcProvider",
    "IaScholarProvider",
    "CoreProvider",
    "OaPdfProvider",
    "needs_fulltext",
    "effective_abstract",
    "attach_fulltext",
    "build_default_chain",
]
