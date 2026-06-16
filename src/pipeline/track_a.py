"""Unified Track A practical-anchor collection across swappable sources.

Today two sources exist — GitHub repositories (:mod:`src.pipeline.git_collect`) and
Hugging Face Hub models/datasets (:mod:`src.pipeline.hf_collect`). Both normalise to
``Work`` objects carrying a 0-100 ``source_meta["reliability_score"]``, so this layer
just collects from each requested source, merges, and re-ranks by that score.

Per-source failure is isolated: if one source raises (network/HTTP/parse), it is
skipped with a recorded error and the other source's anchors are still returned, so
a Hub outage never drops the GitHub anchors and vice versa.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence

from src.core.models import ThemeInput, Work
from src.pipeline.git_collect import GitCollectConfig, collect_track_a_git_works
from src.pipeline.hf_collect import HFCollectConfig, collect_track_a_hf_works

SOURCE_GITHUB = "github"
SOURCE_HUGGINGFACE = "huggingface"
DEFAULT_SOURCES = (SOURCE_GITHUB, SOURCE_HUGGINGFACE)


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
    github_client: Optional[Any] = None,
    hf_client: Optional[Any] = None,
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

    works.sort(key=lambda w: w.source_meta.get("reliability_score", 0), reverse=True)
    return works
