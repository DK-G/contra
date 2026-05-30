"""OpenAlex response parsing and normalization."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.core.models import Concept, Work


class OpenAlexParseError(ValueError):
    pass


def _restore_abstract(inverted_index: Dict[str, List[int]]) -> str:
    words_by_pos: Dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            if pos in words_by_pos:
                continue
            words_by_pos[pos] = word
    if not words_by_pos:
        return ""
    max_pos = max(words_by_pos.keys())
    return " ".join(words_by_pos.get(i, "") for i in range(max_pos + 1)).strip()


def _get_venue(work: Dict[str, Any]) -> str:
    loc = work.get("primary_location") or {}
    source = loc.get("source") or {}
    venue = source.get("display_name") or ""
    return venue


def _get_concepts(work: Dict[str, Any]) -> List[str]:
    concepts = work.get("concepts") or []
    names: List[str] = []
    if isinstance(concepts, list):
        for item in concepts:
            if not isinstance(item, dict):
                continue
            name = item.get("display_name") or ""
            if name:
                names.append(str(name))
    return names


def _get_concept_tags(work: Dict[str, Any]) -> List[Concept]:
    """Build structured concept tags (name/level/score) for objective distance scoring."""
    concepts = work.get("concepts") or []
    tags: List[Concept] = []
    if isinstance(concepts, list):
        for item in concepts:
            if not isinstance(item, dict):
                continue
            name = item.get("display_name") or ""
            if not name:
                continue
            try:
                level = int(item.get("level") or 0)
            except (TypeError, ValueError):
                level = 0
            try:
                score = float(item.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            tags.append(Concept(name=str(name), level=level, score=score))
    return tags


def _get_author_affiliations(work: Dict[str, Any]) -> List[str]:
    authorships = work.get("authorships") or []
    seen = set()
    affiliations: List[str] = []
    if isinstance(authorships, list):
        for author in authorships:
            if not isinstance(author, dict):
                continue
            institutions = author.get("institutions") or []
            if not isinstance(institutions, list):
                continue
            for inst in institutions:
                if not isinstance(inst, dict):
                    continue
                name = inst.get("display_name") or ""
                if not name:
                    continue
                key = str(name)
                if key in seen:
                    continue
                seen.add(key)
                affiliations.append(key)
    return affiliations


def normalize_work(work: Dict[str, Any]) -> Work:
    try:
        work_id = work.get("id") or ""
        title = work.get("display_name") or work.get("title") or ""
        year = int(work.get("publication_year") or 0)
        cited = int(work.get("cited_by_count") or 0)
        doi = work.get("doi") or None
        abstract_index = work.get("abstract_inverted_index") or None
        abstract = None
        if isinstance(abstract_index, dict):
            restored = _restore_abstract(abstract_index)
            abstract = restored if restored else None
        venue = _get_venue(work)
        concepts = _get_concepts(work)
        concept_tags = _get_concept_tags(work)
        affiliations = _get_author_affiliations(work)
        publication_type = work.get("type") or work.get("type_crossref") or None
        is_retracted = bool(work.get("is_retracted") or False)
        title_str = str(title)
        if not is_retracted:
            tl = title_str.upper()
            is_retracted = tl.startswith("RETRACTED:") or tl.startswith("WITHDRAWN:")
    except Exception as exc:  # pragma: no cover - defensive
        raise OpenAlexParseError(f"invalid work payload: {exc}") from exc

    return Work(
        id=str(work_id),
        title=str(title),
        year=year,
        venue=str(venue),
        doi=str(doi) if doi else None,
        cited_by_count=cited,
        abstract=abstract,
        concepts=concepts,
        concept_tags=concept_tags,
        author_affiliations=affiliations,
        publication_type=str(publication_type) if publication_type else None,
        is_retracted=is_retracted,
    )


def normalize_results(payload: Dict[str, Any]) -> List[Work]:
    results = payload.get("results") or []
    if not isinstance(results, list):
        raise OpenAlexParseError("results is not a list")
    return [normalize_work(item) for item in results if isinstance(item, dict)]


__all__ = ["normalize_work", "normalize_results", "OpenAlexParseError"]
