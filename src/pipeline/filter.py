"""Filtering utilities for collected works (Phase 1 stub)."""

from __future__ import annotations

from typing import Iterable, List, Sequence

from src.core.models import Work


def filter_retracted(works: Iterable[Work]) -> List[Work]:
    return [w for w in works if not w.is_retracted]


def filter_has_abstract(works: Iterable[Work]) -> List[Work]:
    return [w for w in works if w.abstract and w.abstract.strip()]


def prioritize_abstract(works: Sequence[Work]) -> List[Work]:
    with_abstract = [w for w in works if w.abstract and w.abstract.strip()]
    without_abstract = [w for w in works if not (w.abstract and w.abstract.strip())]
    return with_abstract + without_abstract


def limit_count(works: Iterable[Work], max_count: int) -> List[Work]:
    if max_count <= 0:
        return []
    return list(works)[:max_count]


__all__ = ["filter_retracted", "filter_has_abstract", "prioritize_abstract", "limit_count"]
