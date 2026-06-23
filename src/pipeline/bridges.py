"""Citation-bridge scoring — Phase 2 of the search-precision strategy (bybridge).

Background: ``docs/research/search_query_precision_strategy.md`` and the 2026-06-23
``DECISION_LOG``. bybridge collects papers that cite the same foundational works as the
near-field seeds (bibliographic coupling). This module adds two cheap, data-in-hand signals
the NotebookLM research highlighted for surfacing genuine *cross-community* bridges:

* **co-citation strength** (``shared_bridge_count``): how many distinct shared-citation
  bridges a candidate cites. More shared bridges = a stronger structural tie to the seeds.
* **bridge betweenness** (``bridge_field_diversity`` / ``bridge_betweenness``): a bridge cited
  by candidates spanning many *different* OpenAlex Fields is a connector between segregated
  scholarly communities — Document Co-Citation Analysis's "concept symbol" / high-betweenness
  bridge. A candidate routing through such a bridge is a better contrarian find than one whose
  shared bridge only ever circulates inside one field.

Both signals are computed from data already fetched (the candidates' ``referenced_works`` and
their ``primary_topic_field_id``, populated in Phase 1), so they add zero API cost. The
functions are pure and stored on ``Work.source_meta`` so every consumer (mcp, delegate,
classify) ranks off one implementation rather than re-deriving it.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set, Tuple

from src.core.models import Work


def _as_set(bridges: Iterable[str]) -> Set[str]:
    return bridges if isinstance(bridges, set) else set(bridges)


def shared_bridge_count(work: Work, bridges: Iterable[str]) -> int:
    """Number of DISTINCT shared-citation bridges this work cites (co-citation strength)."""
    bset = _as_set(bridges)
    return sum(1 for ref in set(work.referenced_works or []) if ref in bset)


def bridge_field_diversity(candidates: Sequence[Work], bridges: Iterable[str]) -> Dict[str, int]:
    """For each bridge, how many DISTINCT primary_topic Fields the candidates citing it span.

    A bridge whose citing candidates come from many Fields connects segregated communities (a
    high-'betweenness' concept symbol); one whose candidates are all in a single Field does not.
    Returns ``bridge id -> distinct-Field count``. Candidates with no ``primary_topic_field_id``
    contribute to the bridge's presence but not to its Field diversity.
    """
    bset = _as_set(bridges)
    fields_by_bridge: Dict[str, Set[str]] = {}
    for cand in candidates:
        fid = (getattr(cand, "source_meta", None) or {}).get("primary_topic_field_id")
        for b in set(cand.referenced_works or []) & bset:
            slot = fields_by_bridge.setdefault(b, set())
            if fid:
                slot.add(str(fid))
    return {b: len(fs) for b, fs in fields_by_bridge.items()}


def annotate_bridge_signals(candidates: Sequence[Work], bridges: Iterable[str]) -> Sequence[Work]:
    """Stamp each candidate's ``source_meta`` with ``shared_bridge_count`` + ``bridge_betweenness``.

    ``bridge_betweenness`` = the max Field-diversity among the bridges the candidate cites (does
    it route through at least one cross-community connector?). Idempotent; returns the same list.
    """
    bset = _as_set(bridges)
    diversity = bridge_field_diversity(candidates, bset)
    for cand in candidates:
        hit = set(cand.referenced_works or []) & bset
        meta = cand.source_meta if isinstance(getattr(cand, "source_meta", None), dict) else {}
        meta["shared_bridge_count"] = len(hit)
        meta["bridge_betweenness"] = max((diversity.get(b, 0) for b in hit), default=0)
        cand.source_meta = meta
    return candidates


def bridge_rank_key(work: Work) -> Tuple[int, int, int]:
    """Descending sort key for annotated bridge candidates.

    Cross-community betweenness first (the contrarian payoff), then co-citation strength, then
    citation count as a deterministic tie-break. Reads the annotations set by
    :func:`annotate_bridge_signals` (defaults to 0 when unannotated). Use with ``reverse=True``.
    """
    meta = getattr(work, "source_meta", None) or {}
    return (
        int(meta.get("bridge_betweenness", 0) or 0),
        int(meta.get("shared_bridge_count", 0) or 0),
        int(getattr(work, "cited_by_count", 0) or 0),
    )


def rank_bridge_candidates(candidates: Sequence[Work], bridges: Iterable[str]) -> List[Work]:
    """Annotate then return candidates ordered by :func:`bridge_rank_key` (best first)."""
    annotate_bridge_signals(candidates, bridges)
    return sorted(candidates, key=bridge_rank_key, reverse=True)


__all__ = [
    "shared_bridge_count",
    "bridge_field_diversity",
    "annotate_bridge_signals",
    "bridge_rank_key",
    "rank_bridge_candidates",
]
