"""Field-scoped, structured query construction — Phase 1 of the search-precision strategy.

Background: ``docs/research/search_query_precision_strategy.md`` and the 2026-06-23
``DECISION_LOG`` entry. The collection paths historically dumped keywords into OpenAlex's
generic ``search=`` parameter — a shallow full-text (title+abstract+body) match that
OpenAlex documents as 10x more expensive than ``filter=`` and prone to pulling in papers
that merely co-mention the terms. This module builds a :class:`StructuredQuery` that
prefers FIELD-SCOPED matching (``title_and_abstract.search`` plus optional
topic/concept/year/type filters) and renders it to OpenAlex request params, while always
exposing a generic-search fallback so recall can never collapse below the old behaviour.

The schema carries the hooks the later phases use (``cites`` / ``exclude_*`` for Phase 2
citation bridging; ``route="semantic"`` for Phase 3 HyDE pseudo-abstract retrieval) so those
phases extend this builder rather than re-introducing ad-hoc param dicts.

Phase 3 note: the ``"semantic"`` route is now wired to OpenAlex's real embedding/ANN endpoint
``search.semantic`` (verified 2026-06-23). That endpoint returns the ~50 nearest works by
meaning, is capped at 50 (no pagination past page 1), respects ``per-page<=50``, composes with
``type``/year filters but **400s on a ``primary_topic.field.id:!`` negation** — so the semantic
route renders only the safe filters and leaves home-domain exclusion to the client side.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from src.core.models import ThemeInput

# OpenAlex filter grammar reserves these characters as separators (`,` = AND, `|` = OR,
# `!` = NOT, `:` = attribute/value). They must never leak into a free-text value such as a
# title_and_abstract.search phrase, or they silently corrupt the whole filter string.
_FILTER_RESERVED = (",", "|", "!", ":")

ROUTE_FILTER = "filter"
ROUTE_SEARCH = "search"
ROUTE_SEMANTIC = "semantic"

# OpenAlex's 26 fixed Topic-hierarchy Fields (level 2: Domain>Field>Subfield>Topic), id->name.
# Used to resolve a theme's self-declared domain or a seed pool's primary_topic into Field ids
# for home-domain EXCLUSION (the empirically useful direction — see the 2026-06-23 DECISION_LOG:
# field-REQUIRE on the anchor-precise seed query is net-negative, so this drives exclusion, not
# a forced scope).
OPENALEX_FIELDS: Dict[str, str] = {
    "11": "Agricultural and Biological Sciences",
    "12": "Arts and Humanities",
    "13": "Biochemistry, Genetics and Molecular Biology",
    "14": "Business, Management and Accounting",
    "15": "Chemical Engineering",
    "16": "Chemistry",
    "17": "Computer Science",
    "18": "Decision Sciences",
    "19": "Earth and Planetary Sciences",
    "20": "Economics, Econometrics and Finance",
    "21": "Energy",
    "22": "Engineering",
    "23": "Environmental Science",
    "24": "Immunology and Microbiology",
    "25": "Materials Science",
    "26": "Mathematics",
    "27": "Medicine",
    "28": "Neuroscience",
    "29": "Nursing",
    "30": "Pharmacology, Toxicology and Pharmaceutics",
    "31": "Physics and Astronomy",
    "32": "Psychology",
    "33": "Social Sciences",
    "34": "Veterinary",
    "35": "Dentistry",
    "36": "Health Professions",
}

# Common short forms / synonyms a theme may use for a Field name (lowercased -> Field id).
_FIELD_ALIASES: Dict[str, str] = {
    "cs": "17", "computer science": "17", "machine learning": "17",
    "artificial intelligence": "17", "ai": "17", "ml": "17", "informatics": "17",
    "math": "26", "maths": "26", "mathematics": "26", "statistics": "26",
    "physics": "31", "astronomy": "31", "astrophysics": "31",
    "chemistry": "16", "biology": "13", "biochemistry": "13", "genetics": "13",
    "molecular biology": "13", "neuroscience": "28", "medicine": "27", "medical": "27",
    "economics": "20", "finance": "20", "psychology": "32", "engineering": "22",
    "materials science": "25", "materials": "25", "environmental science": "23",
    "social science": "33", "social sciences": "33", "sociology": "33",
    "pharmacology": "30", "energy": "21", "earth science": "19",
}


def sanitize_filter_value(text: str) -> str:
    """Make a free-text string safe to place inside an OpenAlex ``filter=`` value."""
    cleaned = (text or "").strip().strip('"').strip("'")
    for ch in _FILTER_RESERVED:
        cleaned = cleaned.replace(ch, " ")
    return " ".join(cleaned.split())


@dataclass
class StructuredQuery:
    """A field-scoped query plus the precision filters to apply (engine-agnostic).

    anchor_terms        : the lexical anchor, matched against title+abstract (not body).
    field_ids           : OpenAlex Topic *Field* ids (e.g. "17" = Computer Science); OR'd.
    concept_ids         : OpenAlex concept/topic ids to REQUIRE; AND'd.
    exclude_concept_ids : concept/topic ids to NEGATE (home-domain exclusion etc.).
    cites               : OpenAlex work ids; candidate must cite ANY of these (Phase 2 bridge).
    year_from / year_to : inclusive publication-year bounds.
    work_type           : OpenAlex work type (e.g. "article").
    route               : how to execute — ``"filter"`` (field-scoped), ``"search"``
                          (generic full-text), or ``"semantic"`` (OpenAlex ``search.semantic``
                          embedding/ANN — Phase 3 HyDE pseudo-abstract retrieval, top-50 cap).
    """

    anchor_terms: List[str] = field(default_factory=list)
    field_ids: List[str] = field(default_factory=list)
    exclude_field_ids: List[str] = field(default_factory=list)
    concept_ids: List[str] = field(default_factory=list)
    exclude_concept_ids: List[str] = field(default_factory=list)
    cites: List[str] = field(default_factory=list)
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    work_type: Optional[str] = None
    max_referenced_works: Optional[int] = None
    route: str = ROUTE_FILTER

    def anchor_string(self) -> str:
        return " ".join(t for t in (self.anchor_terms or []) if t).strip()

    def is_empty(self) -> bool:
        return not (
            self.anchor_terms or self.field_ids or self.exclude_field_ids
            or self.concept_ids or self.exclude_concept_ids or self.cites
            or self.year_from or self.year_to or self.work_type
            or self.max_referenced_works
        )

    def _filter_string(self) -> str:
        """Render the precision filters into an OpenAlex ``filter=`` value (`,`-joined ANDs)."""
        parts: List[str] = []
        anchor = sanitize_filter_value(self.anchor_string())
        if anchor:
            # Field-scoped: title+abstract only, NOT the full-text body (the noise source).
            parts.append(f"title_and_abstract.search:{anchor}")
        if self.cites:
            parts.append("cites:" + "|".join(self.cites))
        if self.field_ids:
            parts.append("primary_topic.field.id:" + "|".join(str(f) for f in self.field_ids))
        for fid in self.exclude_field_ids:
            parts.append(f"primary_topic.field.id:!{fid}")
        for cid in self.concept_ids:
            parts.append(f"concepts.id:{cid}")
        for cid in self.exclude_concept_ids:
            parts.append(f"concepts.id:!{cid}")
        if self.year_from is not None and self.year_to is not None:
            parts.append(f"publication_year:{self.year_from}-{self.year_to}")
        elif self.year_from is not None:
            parts.append(f"from_publication_date:{self.year_from}-01-01")
        elif self.year_to is not None:
            parts.append(f"to_publication_date:{self.year_to}-12-31")
        if self.work_type:
            parts.append(f"type:{self.work_type}")
        if self.max_referenced_works is not None:
            parts.append(f"referenced_works_count:<{self.max_referenced_works}")
        return ",".join(parts)

    def _semantic_filter_string(self) -> str:
        """The subset of filters that compose with ``search.semantic`` (verified 2026-06-23).

        ``type:article`` and year bounds compose fine, but a ``primary_topic.field.id:!`` negation
        returns HTTP 400 — so field/concept/cites filters are deliberately omitted here and the
        semantic route relies on client-side home-domain exclusion instead.
        """
        parts: List[str] = []
        if self.year_from is not None and self.year_to is not None:
            parts.append(f"publication_year:{self.year_from}-{self.year_to}")
        elif self.year_from is not None:
            parts.append(f"from_publication_date:{self.year_from}-01-01")
        elif self.year_to is not None:
            parts.append(f"to_publication_date:{self.year_to}-12-31")
        if self.work_type:
            parts.append(f"type:{self.work_type}")
        return ",".join(parts)

    def to_params(self, *, per_page: int = 50, page: int = 1) -> Dict[str, Any]:
        """Render to an OpenAlex request param dict for the chosen route."""
        if self.route == ROUTE_SEMANTIC:
            # OpenAlex's embedding/ANN endpoint: returns the ~50 nearest works by meaning. Capped
            # at 50, so clamp per-page; field/concept exclusion is NOT emitted (400s) and is done
            # client-side. This is the route HyDE/Query2doc pseudo-abstracts retrieve through.
            base: Dict[str, Any] = {"per-page": min(per_page, 50), "page": page,
                                    "search.semantic": self.anchor_string()}
            sem_filter = self._semantic_filter_string()
            if sem_filter:
                base["filter"] = sem_filter
            return base
        base = {"per-page": per_page, "page": page}
        if self.route == ROUTE_FILTER:
            flt = self._filter_string()
            if flt:
                base["filter"] = flt
                return base
            # Nothing was field-scopeable -> fall through to generic search (recall-safe).
        # ROUTE_SEARCH (and a filter route with nothing scopeable) executes as generic full-text
        # search so recall is never worse than the legacy behaviour. F-13 (2026-08-28): when the
        # caller declared a home Field, the generic route KEEPS that scope (search= composes with
        # filter= on OpenAlex) — an unscoped generic search is exactly where homograph collisions
        # ('trade' -> trade policy, 'sequential' -> consumer credit) flooded the seed roster.
        base["search"] = self.anchor_string()
        if self.field_ids:
            base["filter"] = "primary_topic.field.id:" + "|".join(str(f) for f in self.field_ids)
        return base

    def fallback(self) -> "StructuredQuery":
        """A recall-safe generic-search twin (same anchor + field scope, ``route='search'``).

        F-13: the twin keeps ``field_ids`` — dropping the home-Field scope on fallback was the
        drift door (the precise filter misses, then the loose retry roams every discipline).
        All OTHER precision filters are still dropped, so recall is no worse than legacy for
        callers that never set field_ids.
        """
        return StructuredQuery(anchor_terms=list(self.anchor_terms),
                               field_ids=list(self.field_ids), route=ROUTE_SEARCH)


def structured_query_from_theme(theme: ThemeInput, *, route: str = ROUTE_FILTER) -> StructuredQuery:
    """Single best field-scoped query for a theme (mirrors ``Collector._query_from_theme``)."""
    terms = [t for t in theme.keywords.include if t]
    if not terms:
        terms = [t for t in (theme.scope.field, theme.goal) if t]
    return StructuredQuery(anchor_terms=terms, route=route)


def structured_query_variants(theme: ThemeInput, *, route: str = ROUTE_FILTER) -> List[StructuredQuery]:
    """Field-scoped variants mirroring ``Collector._query_variants`` (keyword prefix ladder).

    Longest keyword combination first (most precise), then progressively shorter prefixes,
    then a ``scope.field`` / ``goal`` fallback — same relaxation ladder as before, but each
    rung is a field-scoped :class:`StructuredQuery` rather than a generic-search string.
    """
    tokens = [t for t in theme.keywords.include if t]
    variants: List[StructuredQuery] = []
    seen: set = set()

    def _add(terms: List[str]) -> None:
        key = " ".join(terms).lower()
        if terms and key not in seen:
            seen.add(key)
            variants.append(StructuredQuery(anchor_terms=list(terms), route=route))

    if tokens:
        for k in range(len(tokens), 0, -1):
            _add(tokens[:k])
    fallback_terms = [t for t in (theme.scope.field, theme.goal) if t]
    if fallback_terms:
        _add(fallback_terms)
    return variants


def resolve_field_ids(field_name: str) -> List[str]:
    """Best-effort map a free-text domain (e.g. ``theme.scope.field``) to OpenAlex Field ids.

    Deterministic, no network: tries an alias table, then exact/substring matches against the
    26 canonical Field names. Returns every plausible Field id (callers OR them) — a theme's
    self-declared field is often broad, so over-matching here is safer than forcing one field.
    Returns ``[]`` when nothing matches (callers then simply skip field scoping).
    """
    text = (field_name or "").strip().lower()
    if not text:
        return []
    hits: List[str] = []
    seen: set = set()

    def _add(fid: str) -> None:
        if fid and fid not in seen:
            seen.add(fid)
            hits.append(fid)

    def _word(needle: str) -> bool:
        return re.search(r"\b" + re.escape(needle) + r"\b", text) is not None

    # exact alias first (the only path that may match 2-3 char short forms like cs/ai/ml).
    if text in _FIELD_ALIASES:
        _add(_FIELD_ALIASES[text])
    # longer aliases appearing as a WHOLE WORD in the text; the word-boundary + >=4 guards
    # stop matches inside unrelated words (e.g. 'cs' in 'physics', 'chemistry' in 'biochemistry').
    for alias, fid in _FIELD_ALIASES.items():
        if len(alias) >= 4 and _word(alias):
            _add(fid)
    for fid, name in OPENALEX_FIELDS.items():
        nl = name.lower()
        if nl == text or _word(nl) or (len(text) >= 4 and text in nl):
            _add(fid)
    return hits


def dominant_field_ids(works: Iterable[Any], *, max_fields: int = 2, min_count: int = 2) -> List[str]:
    """The Field id(s) that dominate a pool's ``primary_topic`` — the empirical home domain.

    Reads ``source_meta['primary_topic_field_id']`` (populated by the OpenAlex parser) across
    the works and returns the most common Field ids (count >= ``min_count``), most frequent
    first, capped at ``max_fields``. This is the data-driven home-domain signal for EXCLUSION
    in the citation/Track-B paths, preferred over the deprecated L0-concept signal.
    """
    counts: Dict[str, int] = {}
    for w in works:
        meta = getattr(w, "source_meta", None) or {}
        fid = meta.get("primary_topic_field_id")
        if fid:
            counts[str(fid)] = counts.get(str(fid), 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [fid for fid, c in ranked if c >= min_count][:max_fields]


__all__ = [
    "StructuredQuery",
    "sanitize_filter_value",
    "structured_query_from_theme",
    "structured_query_variants",
    "resolve_field_ids",
    "dominant_field_ids",
    "OPENALEX_FIELDS",
    "ROUTE_FILTER",
    "ROUTE_SEARCH",
    "ROUTE_SEMANTIC",
]
