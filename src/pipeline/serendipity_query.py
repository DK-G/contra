"""Serendipity (Track B) query generation + pre-execution validation — Phase 3 of the
search-precision strategy (byserendipity).

Background: ``docs/research/search_query_precision_strategy.md`` §3 and the 2026-06-23
``DECISION_LOG``. Three evidence-grounded pieces (NotebookLM note 145af5df, 77 sources, plus
live OpenAlex verification on 2026-06-23):

* **Targeted abstraction** (§3.2): re-describe the theme as domain-neutral FUNCTION words while
  KEEPING the structural constraints that define its relational shape (drop only irrelevant
  surface attributes; abstract at most ~3 levels). The earlier "strip ALL theme words / fully
  abstract" prompt over-abstracted into noise — analogy research shows retaining the core
  relational constraints beats abstracting everything away.
* **HyDE / Query2doc grounding** (§3.3): for each distant facet, generate a short hypothetical
  abstract of a paper in THAT distant domain that exhibits the structure, and retrieve it through
  OpenAlex's embedding/ANN endpoint (``route="semantic"`` -> ``search.semantic``, verified to
  exist and return semantically-nearest works, top-50). Complementary integration: the theme's
  domain-neutral structural anchor is concatenated with the pseudo-abstract, since the
  pseudo-document alone underperforms ``query + pseudo-document``.
* **QA-Expand multi-faceting** (§3.3): split into up to 3 DISTINCT distant facets so the search
  does not converge on one popularity-biased interpretation.

A **pre-execution validation layer** (§3.4) keeps only queries that return non-empty,
non-home-converged results; when every generated query fails, callers fall back to the Phase 1
lexical baseline (a Corrective-RAG quality gate, so bad material never reaches the selection
stage). Concept-level relevance to the theme is intentionally NOT scored here — that is the
immutable ``purpose_sim * mechanism_dist`` selection stage's job (``classify.py``; spec.md §7
forbids touching the score design). This module only generates and structurally validates queries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.core.models import ThemeInput, Work
from src.pipeline.query import ROUTE_SEMANTIC, StructuredQuery

# QA-Expand recommends at most 3 distinct facets (NotebookLM: "generate up to 3 distinct relevant
# questions"); more facets revisit popularity-biased interpretations rather than broadening.
MAX_FACETS = 3

# Validation thresholds (§3.4). Calibrated against live OpenAlex on 2026-06-23 (see DECISION_LOG).
# A semantic query returns up to 50 nearest works; if too few survive home-domain exclusion, or if
# the home Field dominates the raw neighbours, the query collapsed back home (or is too thin).
_MIN_RESULTS = 3            # raw semantic neighbours required (endpoint returns up to 50)
_MAX_HOME_FRACTION = 0.6    # reject if > this share of raw neighbours sit in the theme's home Field
_MIN_DISTANT = 1            # at least one candidate must survive home-domain exclusion


@dataclass
class SerendipitySpec:
    """The targeted abstraction of a theme plus its distant-domain facets.

    structure : the theme's relational structure in domain-neutral FUNCTION words (with the
                constraints that define its shape kept, surface topic words dropped).
    facets    : up to ``MAX_FACETS`` distant domains, each with a hypothetical abstract written
                in THAT domain's own vocabulary.
    """

    structure: str = ""
    facets: List["SerendipityFacet"] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.facets


@dataclass
class SerendipityFacet:
    domain: str
    pseudo_abstract: str


# ---------------------------------------------------------------------------
# Generation: targeted abstraction + distant facets + HyDE pseudo-abstracts
# ---------------------------------------------------------------------------

def _parse_object(text: str) -> Optional[dict]:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start:end])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def generate_serendipity_facets(
    theme: ThemeInput, model: str = "gpt-4o-mini", n: int = MAX_FACETS
) -> SerendipitySpec:
    """Generate a targeted abstraction of the theme + up to ``n`` distant-domain pseudo-abstracts.

    Returns an empty :class:`SerendipitySpec` on LLM failure or unparseable output, so callers
    transparently fall back to the lexical baseline (the Corrective-RAG quality gate).
    """
    from src.openai_client import OpenAIError, extract_output_text, responses_create

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You design cross-domain analogy SEARCHES for a research theme using "
                    "TARGETED ABSTRACTION + hypothetical-document grounding (HyDE/Query2doc).\n"
                    "STEP 1 — Describe the theme's core RELATIONAL STRUCTURE in domain-neutral "
                    "FUNCTION words, but KEEP the structural constraints that define its shape "
                    "(e.g. 'a threshold above which a self-reinforcing feedback loop runs away "
                    "under a fixed resource cap'). Do NOT keep the theme's surface topic nouns. "
                    "Do NOT over-abstract into bare words like 'system'/'process'/'entity' "
                    "(abstract at most ~3 levels — deeper is too general to be useful).\n"
                    f"STEP 2 — Pick up to {n} DISTINCT DISTANT domains, each from a different "
                    "field/discipline than the theme AND than each other, where that same "
                    "structure plausibly appears.\n"
                    "STEP 3 — For each domain write a short HYPOTHETICAL ABSTRACT (2-4 sentences, "
                    "~80 words) of a paper IN THAT domain that exhibits the structure, written in "
                    "that domain's OWN concrete vocabulary, mechanisms and (plausible) findings — "
                    "NOT the theme's words.\n"
                    "HARD CONSTRAINTS: never use the theme's own field name or surface keywords "
                    "(given below) in the structure or any abstract; do not target the theme's own "
                    "phenomenon/population.\n"
                    'Return JSON only: {"structure":"...","facets":[{"domain":"...",'
                    '"pseudo_abstract":"..."}]}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research theme: {theme.theme_overview[:300]}\n"
                    f"Theme's goal: {theme.goal}\n"
                    f"Theme's own field (too near, avoid): {theme.scope.field}\n"
                    f"Theme's surface keywords (too near, NEVER use): "
                    f"{', '.join(theme.keywords.include)}\n\n"
                    f"Produce the domain-neutral structure and up to {n} distant facets with "
                    "hypothetical abstracts, as JSON only."
                ),
            },
        ],
        # Query2doc uses the default temperature of 1.0 to sample pseudo-documents.
        "temperature": 1.0,
    }
    try:
        text = extract_output_text(responses_create(payload)).strip()
    except OpenAIError:
        return SerendipitySpec()
    obj = _parse_object(text)
    if not obj:
        return SerendipitySpec()
    structure = str(obj.get("structure") or "").strip()
    facets: List[SerendipityFacet] = []
    seen_domains: set = set()
    for item in obj.get("facets") or []:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip()
        pseudo = str(item.get("pseudo_abstract") or "").strip()
        key = domain.lower()
        if pseudo and key not in seen_domains:
            seen_domains.add(key)
            facets.append(SerendipityFacet(domain=domain, pseudo_abstract=pseudo))
        if len(facets) >= n:
            break
    return SerendipitySpec(structure=structure, facets=facets)


def build_semantic_query(
    structure: str, pseudo_abstract: str, *, work_type: Optional[str] = "article"
) -> StructuredQuery:
    """A semantic-route query combining the theme's structural anchor with a distant pseudo-abstract.

    Complementary integration (Query2doc/HyDE): concatenating the domain-neutral structural anchor
    with the distant-domain pseudo-abstract makes the embedding capture BOTH the transferable
    structure and the distant domain's concrete vocabulary — the pseudo-abstract alone underperforms
    ``query + pseudo-document`` (NotebookLM). ``work_type`` composes safely with ``search.semantic``;
    home-domain exclusion is applied client-side (the field-id negation 400s on that endpoint).
    """
    text = " ".join(t for t in (structure, pseudo_abstract) if t).strip()
    return StructuredQuery(anchor_terms=[text], route=ROUTE_SEMANTIC, work_type=work_type)


# ---------------------------------------------------------------------------
# Pre-execution validation (§3.4): non-empty + home-convergence
# ---------------------------------------------------------------------------

def _field_id(work: Work) -> str:
    return str((getattr(work, "source_meta", None) or {}).get("primary_topic_field_id") or "")


def home_field_fraction(works: Sequence[Work], home_field_ids: Iterable[str]) -> float:
    """Share of works whose primary_topic Field is one of the theme's home Fields (0.0 if empty).

    Works with no ``primary_topic_field_id`` count as non-home (they cannot be confirmed home), so
    this is a conservative collapse signal — it only fires on works KNOWN to be in the home domain.
    """
    works = list(works)
    if not works:
        return 0.0
    home = {str(f) for f in home_field_ids if f}
    if not home:
        return 0.0
    in_home = sum(1 for w in works if _field_id(w) in home)
    return in_home / len(works)


def exclude_home_field(works: Sequence[Work], home_field_ids: Iterable[str]) -> List[Work]:
    """Drop works whose primary_topic Field is a home Field (client-side home-domain exclusion).

    Used for the semantic route, where OpenAlex 400s on a ``primary_topic.field.id:!`` filter, so
    the exclusion the citation path does server-side must run here on the parsed Field id instead.
    """
    home = {str(f) for f in home_field_ids if f}
    if not home:
        return list(works)
    return [w for w in works if _field_id(w) not in home]


def validate_semantic_results(
    works: Sequence[Work],
    home_field_ids: Iterable[str],
    *,
    min_results: int = _MIN_RESULTS,
    max_home_fraction: float = _MAX_HOME_FRACTION,
    min_distant: int = _MIN_DISTANT,
) -> Tuple[bool, str]:
    """Pre-execution gate for a generated semantic query's raw results (§3.4).

    Valid iff the query returned enough neighbours, did NOT converge on the home domain, and leaves
    at least ``min_distant`` candidates after home-domain exclusion. Returns ``(is_valid, reason)``;
    ``reason`` is ``"ok"`` when valid, else the failure code (for diagnostics / fallback logging).
    """
    works = list(works)
    if len(works) < min_results:
        return False, "too_few"
    frac = home_field_fraction(works, home_field_ids)
    if frac > max_home_fraction:
        return False, "home_converged"
    if len(exclude_home_field(works, home_field_ids)) < min_distant:
        return False, "no_distant"
    return True, "ok"


__all__ = [
    "MAX_FACETS",
    "SerendipitySpec",
    "SerendipityFacet",
    "generate_serendipity_facets",
    "build_semantic_query",
    "home_field_fraction",
    "exclude_home_field",
    "validate_semantic_results",
]
