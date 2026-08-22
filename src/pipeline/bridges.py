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

import math
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from src.core.models import ThemeInput, Work
from src.pipeline.git_collect import _README_DENSITY_UNIT, _README_MIN_LEN


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




# --- C(ii): theme-relevance x citations hybrid ranking (2026-08-22 ruling) ---
#
# bridge_rank_key ends in raw cited_by_count, so within one betweenness tier the ranking
# is citation-dominated — the direct cause of the "top-10 all hang off the most-travelled
# bridge, all mega-cited off-field papers" residue (field_observations F-01 residue /
# P7). Prescription from the Search Query Precision notebook: z-normalise theme fit and
# log-citations independently over the candidate pool, then combine with the citation
# weight demoted to a tie-breaker:  final = (1-w)*Z(fit) + w*Z(ln(cites+1)), w = 0.15.

_HYBRID_CITATION_WEIGHT = 0.15


def _theme_terms(theme: ThemeInput) -> List[str]:
    return [t for t in (theme.keywords.include or []) if t and t.strip()]


def candidate_theme_fit(work: Work, terms: Sequence[str]) -> float:
    """Density-normalised keyword fit for a PAPER: title hits earn full credit, abstract
    hits earn occurrences-per-10k-chars partial credit (same calibration as the GitHub
    readme fit — mentions in a short focused abstract are signal, incidental mentions in
    long text are not). Returns 0..len(terms)."""
    title = (work.title or "").lower()
    abstract = (work.abstract or "").lower()
    denom = max(len(abstract), _README_MIN_LEN) / _README_DENSITY_UNIT
    credit = 0.0
    for term in terms:
        t = term.lower()
        if t in title:
            credit += 1.0
        elif abstract:
            credit += min(abstract.count(t) / denom, 1.0)
    return credit


def _z_scores(values: Sequence[float]) -> List[float]:
    n = len(values)
    if n == 0:
        return []
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    sd = math.sqrt(var)
    if sd == 0:
        return [0.0] * n
    return [(v - mean) / sd for v in values]


def seed_citers_per_bridge(seeds: Sequence[Work], bridges: Iterable[str]) -> Dict[str, int]:
    """bridge id -> how many distinct seeds cite it (the bridge's thematic centrality)."""
    bset = _as_set(bridges)
    counts: Dict[str, int] = {}
    for seed in seeds:
        for b in set(seed.referenced_works or []) & bset:
            counts[b] = counts.get(b, 0) + 1
    return counts


def annotate_hybrid_rank(
    candidates: Sequence[Work],
    theme: Optional[ThemeInput] = None,
    *,
    seeds: Optional[Sequence[Work]] = None,
    bridges: Optional[Iterable[str]] = None,
    citation_weight: float = _HYBRID_CITATION_WEIGHT,
) -> Sequence[Work]:
    """Stamp ``theme_fit`` / ``bridge_strength`` / ``bridge_hybrid_score`` on source_meta.

    Relevance for a CROSS-DOMAIN candidate has two channels, z-normalised and averaged:

    * lexical ``theme_fit`` (keyword density vs title/abstract) — usually near zero for
      bybridge, because candidates live in other domains' vocabulary BY DESIGN (live
      measurement 2026-08-22: fit > 0 for 0/60 candidates);
    * structural ``bridge_strength`` — the max number of SEEDS citing any bridge the
      candidate routes through. A candidate reached via a bridge that five seeds cite
      (e.g. NSGA-II on the strategy-generation theme) is thematically anchored in a way
      no lexical match can see; one reached via a proceedings bibliography (1 seed) isn't.

    Channels with no signal in this pool (all-zero) are excluded from the average, so the
    score never silently degenerates to citations-only; with NO relevance channel at all,
    every hybrid is 0.0 and :func:`hybrid_bridge_rank_key` falls back to the legacy
    structural ordering.
    """
    terms = _theme_terms(theme) if theme is not None else []
    fits = [candidate_theme_fit(w, terms) if terms else 0.0 for w in candidates]
    citers = seed_citers_per_bridge(seeds, bridges) if seeds and bridges is not None else {}
    bset = _as_set(bridges) if bridges is not None else set()
    strengths = [
        max((citers.get(b, 0) for b in set(w.referenced_works or []) & bset), default=0)
        for w in candidates
    ]
    cites = [math.log1p(max(int(getattr(w, "cited_by_count", 0) or 0), 0)) for w in candidates]

    channels = []
    if any(f > 0 for f in fits):
        channels.append(_z_scores(fits))
    if any(st > 0 for st in strengths):
        channels.append(_z_scores([float(st) for st in strengths]))
    z_cite = _z_scores(cites)

    for i, w in enumerate(candidates):
        meta = w.source_meta if isinstance(getattr(w, "source_meta", None), dict) else {}
        meta["theme_fit"] = round(fits[i], 2)
        meta["bridge_strength"] = strengths[i]
        if channels:
            rel = sum(ch[i] for ch in channels) / len(channels)
            meta["bridge_hybrid_score"] = round(
                (1.0 - citation_weight) * rel + citation_weight * z_cite[i], 4
            )
        else:
            meta["bridge_hybrid_score"] = 0.0
        w.source_meta = meta
    return candidates


def hybrid_bridge_rank_key(work: Work) -> Tuple[float, int, int, int]:
    """Hybrid-first sort key. Unannotated pools carry hybrid 0.0 everywhere, so ordering
    degrades gracefully to the legacy (betweenness, shared, citations) key."""
    meta = getattr(work, "source_meta", None) or {}
    return (
        float(meta.get("bridge_hybrid_score", 0.0) or 0.0),
        int(meta.get("bridge_betweenness", 0) or 0),
        int(meta.get("shared_bridge_count", 0) or 0),
        int(getattr(work, "cited_by_count", 0) or 0),
    )


# --- C(i): head-window diversification (2026-08-22 ruling) -------------------

def diversify_head_by_bridge(
    ranked: Sequence[Work],
    bridges: Iterable[str],
    *,
    window: int = 10,
    per_bridge_cap: int = 2,
) -> List[Work]:
    """Greedy re-order: no single bridge may claim more than ``per_bridge_cap`` slots of
    the first ``window`` results.

    The pool-level diversity fixes (F-07 seed quota, F-12 liveness) left the DISPLAY
    window collapsed: the ranking key gathers candidates routed through the most-travelled
    bridge, so the top-10 read as one bibliography again (measured 100% head-window share
    on 2026-08-22). Same quota philosophy as the seed-side cap, applied at the display
    layer. Candidates deferred out of the window keep their relative order after it.
    """
    bset = _as_set(bridges)
    counts: Dict[str, int] = {}
    head: List[Work] = []
    rest: List[Work] = []
    for cand in ranked:
        if len(head) >= window:
            rest.append(cand)
            continue
        cited = set(cand.referenced_works or []) & bset
        if cited and all(counts.get(b, 0) >= per_bridge_cap for b in cited):
            rest.append(cand)          # every bridge it hangs off is already full
            continue
        for b in cited:
            counts[b] = counts.get(b, 0) + 1
        head.append(cand)
    return head + rest


__all__ = [
    "shared_bridge_count",
    "bridge_field_diversity",
    "annotate_bridge_signals",
    "annotate_hybrid_rank",
    "bridge_rank_key",
    "candidate_theme_fit",
    "diversify_head_by_bridge",
    "hybrid_bridge_rank_key",
    "seed_citers_per_bridge",
    "rank_bridge_candidates",
]
