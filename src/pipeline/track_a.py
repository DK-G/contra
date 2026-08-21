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

from typing import Any, Callable, List, Optional, Sequence

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
    fit = work.source_meta.get("theme_fit_score", 0) or 0
    fit_max = _FIT_MAX_GITHUB if work.publication_type == "github_repository" else _FIT_MAX_OTHER
    try:
        return min(max(float(fit) / fit_max, 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def annotate_anchor_rank(works: Sequence[Work]) -> None:
    """Stamp source_meta with `relevance` (0-1) and `anchor_rank_score` (the sort key)."""
    for w in works:
        relevance = _relevance_of(w)
        reliability = w.source_meta.get("reliability_score", 0) or 0
        w.source_meta["relevance"] = round(relevance, 2)
        w.source_meta["anchor_rank_score"] = round(
            reliability * (_RANK_RELEVANCE_FLOOR + (1.0 - _RANK_RELEVANCE_FLOOR) * relevance), 1
        )


def anchor_rank_key(work: Work) -> float:
    """Sort key for Track A anchors. Falls back to raw reliability when unannotated."""
    meta = work.source_meta or {}
    if "anchor_rank_score" in meta:
        return float(meta["anchor_rank_score"])
    return float(meta.get("reliability_score", 0) or 0)
