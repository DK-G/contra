"""Classification utilities (Phase 1 stub)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from src.core.models import Work


@dataclass
class ClassifiedWorks:
    related: List[Work]
    broad: List[Work]
    unrelated: List[Work]
    unrelated_chapters: Dict[str, List[Work]]


def _score_work(work: Work, include: Sequence[str], exclude: Sequence[str]) -> int:
    text = f"{work.title} {work.abstract or ''}".lower()
    score = 0
    for token in include:
        if token and token.lower() in text:
            score += 1
    for token in exclude:
        if token and token.lower() in text:
            score -= 1
    return score


def classify_stub(
    works: Iterable[Work],
    include_keywords: Sequence[str] | None = None,
    exclude_keywords: Sequence[str] | None = None,
) -> ClassifiedWorks:
    # Placeholder: simple keyword scoring + proportional slicing
    include = list(include_keywords or [])
    exclude = list(exclude_keywords or [])

    scored = [(work, _score_work(work, include, exclude)) for work in works]
    scored.sort(key=lambda item: item[1], reverse=True)
    ordered = [w for w, _ in scored]

    total = len(ordered)
    related_count = max(1, round(total * 0.6)) if total else 0
    broad_count = max(0, round(total * 0.3))
    unrelated_count = max(0, total - related_count - broad_count)

    related = ordered[:related_count]
    broad = ordered[related_count : related_count + broad_count]
    unrelated = ordered[related_count + broad_count :]

    chapter_keys = ["反証・対立仮説", "測定・評価の地雷", "手法転用", "制約条件が真逆"]
    unrelated_chapters: Dict[str, List[Work]] = {k: [] for k in chapter_keys}

    for idx, work in enumerate(unrelated):
        key = chapter_keys[idx % len(chapter_keys)]
        unrelated_chapters[key].append(work)

    return ClassifiedWorks(
        related=related,
        broad=broad,
        unrelated=unrelated,
        unrelated_chapters=unrelated_chapters,
    )


__all__ = ["ClassifiedWorks", "classify_stub"]
