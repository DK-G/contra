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
            cid = item.get("id") or ""
            tags.append(Concept(name=str(name), level=level, score=score, id=str(cid)))
    return tags


def _get_source_meta(work: Dict[str, Any]) -> Dict[str, Any]:
    """Collect OA / full-text resolution hints into source_meta (non-breaking enrichment).

    Stores is_oa / oa_url / pdf_url / landing_page_url and, when any location points at
    arXiv, arxiv_url — the full-text provider layer (src/fulltext) derives the arXiv id from
    these. No new Work field is introduced; this rides on the existing flexible source_meta.
    """
    meta: Dict[str, Any] = {}
    oa = work.get("open_access") or {}
    if isinstance(oa, dict):
        meta["is_oa"] = bool(oa.get("is_oa"))
        if oa.get("oa_url"):
            meta["oa_url"] = str(oa.get("oa_url"))
    ploc = work.get("primary_location") or {}
    if isinstance(ploc, dict):
        if ploc.get("pdf_url"):
            meta["pdf_url"] = str(ploc.get("pdf_url"))
        if ploc.get("landing_page_url"):
            meta["landing_page_url"] = str(ploc.get("landing_page_url"))
    # primary_topic.field: the work's home Field in OpenAlex's active Topic hierarchy
    # (Domain>Field>Subfield>Topic). Stored bare ('17') for home-domain resolution/exclusion
    # (src/pipeline/query.dominant_field_ids); concepts are deprecated so this is the durable
    # domain signal. Non-breaking source_meta enrichment, no new Work field.
    ptopic = work.get("primary_topic") or {}
    if isinstance(ptopic, dict):
        fld = ptopic.get("field") or {}
        if isinstance(fld, dict):
            fid = fld.get("id")
            if fid:
                meta["primary_topic_field_id"] = str(fid).rsplit("/", 1)[-1]
            fname = fld.get("display_name")
            if fname:
                meta["primary_topic_field_name"] = str(fname)
        # Subfield/Topic, one and two levels BELOW Field. A Field such as "Economics,
        # Econometrics and Finance" contains international trade, labour economics and asset
        # pricing alike, so a Field-level match says almost nothing about subject fit (F-13,
        # 2026-09-04: a roster of NAFTA/broadband/Fox-News papers scored "100% home field" on a
        # strategy-selection theme). These finer levels are what the drift is actually readable
        # in. Additive source_meta enrichment, same as the Field above.
        sfld = ptopic.get("subfield") or {}
        if isinstance(sfld, dict):
            sid = sfld.get("id")
            if sid:
                meta["primary_topic_subfield_id"] = str(sid).rsplit("/", 1)[-1]
            sname = sfld.get("display_name")
            if sname:
                meta["primary_topic_subfield_name"] = str(sname)
        tid = ptopic.get("id")
        if tid:
            meta["primary_topic_id"] = str(tid).rsplit("/", 1)[-1]
        tname = ptopic.get("display_name")
        if tname:
            meta["primary_topic_name"] = str(tname)
    locations = work.get("locations") or []
    if isinstance(locations, list):
        for loc in locations:
            if not isinstance(loc, dict):
                continue
            for key in ("landing_page_url", "pdf_url"):
                url = loc.get(key)
                if url and "arxiv.org" in str(url).lower():
                    meta.setdefault("arxiv_url", str(url))
    return meta


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
        source_meta = _get_source_meta(work)
        affiliations = _get_author_affiliations(work)
        publication_type = work.get("type") or work.get("type_crossref") or None
        referenced = work.get("referenced_works") or []
        referenced_works = [str(r) for r in referenced if r] if isinstance(referenced, list) else []
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
        source_meta=source_meta,
        referenced_works=referenced_works,
        language=str(work.get("language")) if work.get("language") else None,
    )


def normalize_results(payload: Dict[str, Any]) -> List[Work]:
    results = payload.get("results") or []
    if not isinstance(results, list):
        raise OpenAlexParseError("results is not a list")
    return [normalize_work(item) for item in results if isinstance(item, dict)]


__all__ = ["normalize_work", "normalize_results", "OpenAlexParseError"]
