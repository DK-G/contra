"""Unified Track A practical-anchor collection across swappable sources.

Today three sources exist — GitHub repositories (:mod:`src.pipeline.git_collect`),
Hugging Face Hub models/datasets (:mod:`src.pipeline.hf_collect`), and Kaggle
datasets/notebooks (:mod:`src.pipeline.kaggle_collect`). All normalise to ``Work``
objects carrying a 0-100 ``source_meta["reliability_score"]``, so this layer just
collects from each requested source, merges, and re-ranks by that score.

Per-source failure is isolated: if one source raises (network/HTTP/parse), it is
skipped with a recorded error and the other sources' anchors are still returned, so
a Hub outage never drops the GitHub anchors and vice versa. Kaggle additionally
self-skips (returns no anchors, not an error) when no credentials are configured.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence, Tuple

from src.core.models import ThemeInput, Work
from src.pipeline.git_collect import GitCollectConfig, collect_track_a_git_works
from src.pipeline.hf_collect import HFCollectConfig, collect_track_a_hf_works
from src.pipeline.kaggle_collect import KaggleCollectConfig, collect_track_a_kaggle_works

SOURCE_GITHUB = "github"
SOURCE_HUGGINGFACE = "huggingface"
SOURCE_KAGGLE = "kaggle"
DEFAULT_SOURCES = (SOURCE_GITHUB, SOURCE_HUGGINGFACE, SOURCE_KAGGLE)


def normalize_sources(sources: Optional[Sequence[str]]) -> List[str]:
    """Validate/clean a requested source list, preserving order and dropping dupes.

    Accepts the ``huggingface`` aliases ``hf``/``huggingface_hub``. Unknown names are
    dropped. An empty/None request falls back to all sources.
    """
    if not sources:
        return list(DEFAULT_SOURCES)
    alias = {
        "github": SOURCE_GITHUB,
        "gh": SOURCE_GITHUB,
        "huggingface": SOURCE_HUGGINGFACE,
        "hf": SOURCE_HUGGINGFACE,
        "huggingface_hub": SOURCE_HUGGINGFACE,
        "kaggle": SOURCE_KAGGLE,
        "kg": SOURCE_KAGGLE,
        "kaggle_hub": SOURCE_KAGGLE,
    }
    out: List[str] = []
    for name in sources:
        key = alias.get(str(name).strip().lower())
        if key and key not in out:
            out.append(key)
    return out or list(DEFAULT_SOURCES)


def collect_track_a_works(
    theme: ThemeInput,
    *,
    sources: Optional[Sequence[str]] = None,
    git_config: Optional[GitCollectConfig] = None,
    hf_config: Optional[HFCollectConfig] = None,
    kaggle_config: Optional[KaggleCollectConfig] = None,
    github_client: Optional[Any] = None,
    hf_client: Optional[Any] = None,
    kaggle_client: Optional[Any] = None,
    on_error: Optional[Callable[[str, Exception], None]] = None,
) -> List[Work]:
    """Collect Track A anchors from the requested sources, merged and ranked.

    ``on_error(source_name, exc)`` is invoked when a source fails (default: swallow),
    letting callers log without aborting the whole collection.
    """
    selected = normalize_sources(sources)
    works: List[Work] = []

    if SOURCE_GITHUB in selected:
        try:
            works.extend(
                collect_track_a_git_works(theme, config=git_config, client=github_client)
            )
        except Exception as exc:  # network/HTTP/parse — isolate this source
            if on_error:
                on_error(SOURCE_GITHUB, exc)

    if SOURCE_HUGGINGFACE in selected:
        try:
            works.extend(
                collect_track_a_hf_works(theme, config=hf_config, client=hf_client)
            )
        except Exception as exc:
            if on_error:
                on_error(SOURCE_HUGGINGFACE, exc)

    if SOURCE_KAGGLE in selected:
        try:
            works.extend(
                collect_track_a_kaggle_works(theme, config=kaggle_config, client=kaggle_client)
            )
        except Exception as exc:
            if on_error:
                on_error(SOURCE_KAGGLE, exc)

    annotate_anchor_rank(works)
    works.sort(key=anchor_rank_key, reverse=True)
    return works


# --- F-03: relevance as a MULTIPLICATIVE ranking term ------------------------
#
# Reliability measures repo QUALITY (impl/doc, maintenance, community, security);
# theme relevance was computed by every source (theme_fit_score: keyword hits in
# name/description/topics/readme) but never entered the ranking — on GitHub it was an
# orphaned "backwards compatibility metric", on HF/Kaggle a +20 additive term drowned
# by ~80 quality points. Six weeks of field observations (F-03) show the consequence:
# well-built but off-topic repos outrank the on-topic ones (2026-08-20: the ONE
# irrelevant candidate scored 86, the two relevant ones 83/82).
#
# The confirmed prescription is multiplication, not addition: an anchor is useful only
# as quality AND relevance together.  rank = reliability * (FLOOR + (1-FLOOR)*relevance)
# The floor keeps zero-lexical-match anchors rankable (the matcher is crude; killing
# them outright would empty thin themes) while letting any nonzero relevance dominate:
# at FLOOR=0.35 both observed real bugs (8/17: 84 vs 79, 8/20: 86 vs 83) flip even if
# the relevant repo matched only weakly (~0.1) and the irrelevant one not at all.

_RANK_RELEVANCE_FLOOR = 0.35
# theme_fit_score scale differs per source: GitHub caps at 30, HF/Kaggle at 20.
_FIT_MAX_GITHUB = 30
_FIT_MAX_OTHER = 20


def _relevance_of(work: Work) -> float:
    fit = (getattr(work, "source_meta", None) or {}).get("theme_fit_score", 0) or 0
    fit_max = _FIT_MAX_GITHUB if getattr(work, "publication_type", None) == "github_repository" else _FIT_MAX_OTHER
    try:
        return min(max(float(fit) / fit_max, 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def annotate_anchor_rank(works: Sequence[Work]) -> None:
    """Stamp source_meta with `relevance` (0-1), `anchor_rank_score` and `relevance_tier`."""
    for w in works:
        relevance = _relevance_of(w)
        reliability = w.source_meta.get("reliability_score", 0) or 0
        w.source_meta["relevance"] = round(relevance, 2)
        w.source_meta["anchor_rank_score"] = round(
            reliability * (_RANK_RELEVANCE_FLOOR + (1.0 - _RANK_RELEVANCE_FLOOR) * relevance), 1
        )
        w.source_meta["relevance_tier"] = 1 if relevance > 0 else 0


# --- F-29 (byrepo, first half): a zero-match anchor never outranks a matching one ----------
#
# The floor above keeps zero-match anchors RANKABLE, but at 0.35 it also lets a high-Reliability
# zero-match anchor beat a weakly matching one: 2026-09-12 two relevance-0.0 repos (an AI
# red-team framework, Reliability 100 -> 35.0; an agent framework -> 30.1) sat above the
# on-topic rpact (0.33 -> 32.9); 09-16 a Go trie (0.0) took rank 3; 09-18 two 0.0 trading bots
# took 2 of the top 4. The sort is now two-tier: anchors with ANY keyword match first, ordered
# by the unchanged score; zero-match anchors after them, also by score. Nothing is removed —
# a thin theme with no matches still returns its zero-match anchors, which is the floor's
# original purpose (F-03, 2026-08-21). What this does NOT touch is the order among matching
# anchors (09-11: freqtrade 0.20 x 89 over MSML 0.40 x 54) — that needs the floor itself to
# move, which re-orders every run and is left as the open half of F-29.

def anchor_rank_key(work: Work) -> Tuple[int, float]:
    """Sort key for Track A anchors: (relevance tier, rank score).

    Falls back to raw reliability (and a tier recomputed from the fit) when unannotated.
    """
    meta = work.source_meta or {}
    if "anchor_rank_score" in meta:
        tier = meta.get("relevance_tier")
        if tier is None:
            tier = 1 if anchor_relevance(work) > 0 else 0
        return (int(tier), float(meta["anchor_rank_score"]))
    return (1 if _relevance_of(work) > 0 else 0, float(meta.get("reliability_score", 0) or 0))



def rank_tier_note(meta: dict) -> str:
    """Suffix for the 順位スコア line: says why a higher score sits below a lower one (F-29)."""
    if (meta or {}).get("relevance_tier") == 0:
        return "・一致キーワード 0 件のため、一致のあるアンカーすべての後ろに並ぶ"
    return ""

# --- F-17: the 関係度 label must be a function of theme relevance ------------
#
# Until 2026-09-01 the structured byrepo path stamped `relationship_level` (rendered as
# 「関係度」= degree of relation TO THE THEME) from the RELIABILITY band — a repo-quality
# measure with no theme in it. seihai 2026-08-27: the one on-topic anchor (frouros,
# relevance 1.0, reliability 62) read 「中」 while two off-topic ones (Kats / a security
# tool, relevance 0.33, reliability ≈ 90 / 83) read 「高」. The ranking was right (F-03);
# the label was a different quantity wearing the wrong name. The 8/29 refinement — "not
# inverted, just unrelated to the coefficient" — is exactly this.
#
# Bands are calibrated on that real case, not on round numbers: 0.33 (one keyword hit in
# three) must read 低, which also matches the existing all-anchors-low warning at 0.35.
RELEVANCE_LOW = 0.35     # below: 低  (same threshold as the byrepo low-relevance warning)
RELEVANCE_HIGH = 0.67    # at/above: 高


def anchor_relevance(work: Work) -> float:
    """Theme relevance (0-1) of a Track A anchor; recomputed when not yet annotated."""
    meta = work.source_meta or {}
    if "relevance" in meta:
        try:
            return float(meta["relevance"] or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return _relevance_of(work)


def relevance_level(relevance: float) -> str:
    """高/中/低 band of theme relevance — what the 関係度 label is supposed to mean."""
    if relevance >= RELEVANCE_HIGH:
        return "高"
    if relevance >= RELEVANCE_LOW:
        return "中"
    return "低"
