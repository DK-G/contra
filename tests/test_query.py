"""Tests for the field-scoped StructuredQuery builder (Phase 1 search-precision)."""

from __future__ import annotations

from typing import Dict, List

from src.core.models import Keywords, Scope, ThemeInput, Work
from src.openalex.parser import normalize_work
from src.pipeline.collect import CollectConfig, Collector, collect_and_filter
from src.pipeline.query import (
    OPENALEX_FIELDS,
    ROUTE_FILTER,
    ROUTE_SEARCH,
    StructuredQuery,
    dominant_field_ids,
    resolve_field_ids,
    sanitize_filter_value,
    structured_query_from_theme,
    structured_query_variants,
)


def _theme(include: List[str], field: str = "computer science", goal: str = "improve X") -> ThemeInput:
    return ThemeInput(
        theme_overview="o" * 200,
        goal=goal,
        why_problem="w",
        approach_type="a",
        assumptions=["x", "y"],
        scope=Scope(field=field, scale="micro", time_range="no_limit"),
        keywords=Keywords(include=include, exclude=[]),
    )


# --- sanitize_filter_value --------------------------------------------------

def test_sanitize_strips_filter_reserved_chars():
    assert sanitize_filter_value('a, b | c: d!') == "a b c d"
    assert sanitize_filter_value('  "graph networks"  ') == "graph networks"
    assert sanitize_filter_value("") == ""


# --- StructuredQuery.to_params ----------------------------------------------

def test_filter_route_scopes_to_title_and_abstract():
    sq = StructuredQuery(anchor_terms=["graph neural networks", "drug discovery"])
    params = sq.to_params(per_page=25, page=2)
    assert params["filter"] == "title_and_abstract.search:graph neural networks drug discovery"
    assert "search" not in params
    assert params["per-page"] == 25 and params["page"] == 2


def test_filter_route_renders_all_precision_filters():
    sq = StructuredQuery(
        anchor_terms=["attention"],
        field_ids=["17", "26"],
        concept_ids=["C1"],
        exclude_concept_ids=["C9"],
        cites=["W1", "W2"],
        year_from=2018,
        year_to=2025,
        work_type="article",
    )
    flt = sq.to_params()["filter"]
    assert "title_and_abstract.search:attention" in flt
    assert "cites:W1|W2" in flt
    assert "primary_topic.field.id:17|26" in flt
    assert "concepts.id:C1" in flt
    assert "concepts.id:!C9" in flt
    assert "publication_year:2018-2025" in flt
    assert "type:article" in flt


def test_year_open_bounds_use_date_filters():
    assert "from_publication_date:2020-01-01" in StructuredQuery(
        anchor_terms=["a"], year_from=2020).to_params()["filter"]
    assert "to_publication_date:2010-12-31" in StructuredQuery(
        anchor_terms=["a"], year_to=2010).to_params()["filter"]


def test_filter_route_with_nothing_scopeable_falls_through_to_search():
    sq = StructuredQuery(anchor_terms=[], route=ROUTE_FILTER)
    params = sq.to_params()
    assert "filter" not in params
    assert params["search"] == ""


def test_search_route_emits_generic_search():
    sq = StructuredQuery(anchor_terms=["foo", "bar"], route=ROUTE_SEARCH)
    params = sq.to_params()
    assert params["search"] == "foo bar"
    assert "filter" not in params


def test_semantic_route_renders_search_semantic_endpoint():
    # Phase 3: the semantic route is wired to OpenAlex's real embedding/ANN endpoint
    # `search.semantic` (verified 2026-06-23). It must NOT emit a generic `search` param.
    sq = StructuredQuery(anchor_terms=["how do proteins fold into native structure"],
                         route="semantic")
    params = sq.to_params(per_page=50)
    assert params["search.semantic"] == "how do proteins fold into native structure"
    assert "search" not in params and "filter" not in params


def test_semantic_route_clamps_per_page_and_composes_safe_filters_only():
    # search.semantic is capped at 50 and composes with type/year, but 400s on a field-id
    # negation — so per-page is clamped to 50 and only type/year render; field exclusion is
    # deliberately dropped (handled client-side).
    sq = StructuredQuery(
        anchor_terms=["coupled oscillator synchronization"],
        route="semantic",
        work_type="article",
        year_from=2015,
        year_to=2024,
        exclude_field_ids=["31"],   # must NOT leak into the semantic filter
    )
    params = sq.to_params(per_page=200)
    assert params["per-page"] == 50
    assert params["filter"] == "publication_year:2015-2024,type:article"
    assert "primary_topic.field.id" not in params["filter"]


def test_fallback_is_recall_safe_search_twin():
    # F-13 (2026-08-28): the twin now KEEPS the home-Field scope — dropping it on fallback was
    # the drift door (homograph collisions roam every discipline on an unscoped generic search).
    # Every other precision filter is still dropped.
    sq = StructuredQuery(anchor_terms=["a", "b"], field_ids=["17"], cites=["W1"])
    fb = sq.fallback()
    assert fb.route == ROUTE_SEARCH
    assert fb.field_ids == ["17"] and fb.cites == []
    params = fb.to_params()
    assert params["search"] == "a b"
    assert params["filter"] == "primary_topic.field.id:17"


def test_fallback_without_field_scope_is_pure_generic_search():
    fb = StructuredQuery(anchor_terms=["a"], cites=["W1"]).fallback()
    params = fb.to_params()
    assert params["search"] == "a" and "filter" not in params


def test_anchor_comma_cannot_corrupt_the_filter_grammar():
    # A comma in a keyword must not introduce a spurious second filter clause.
    flt = StructuredQuery(anchor_terms=["systems, control"]).to_params()["filter"]
    assert flt == "title_and_abstract.search:systems control"


# --- builders ---------------------------------------------------------------

def test_structured_query_from_theme_prefers_keywords():
    sq = structured_query_from_theme(_theme(["a", "b"]))
    assert sq.anchor_terms == ["a", "b"] and sq.route == ROUTE_FILTER


def test_structured_query_from_theme_falls_back_to_field_and_goal():
    sq = structured_query_from_theme(_theme([], field="biology", goal="map pathways"))
    assert sq.anchor_terms == ["biology", "map pathways"]


def test_variants_form_a_shrinking_prefix_ladder():
    variants = structured_query_variants(_theme(["x", "y", "z"]))
    anchors = [v.anchor_string() for v in variants]
    assert anchors[0] == "x y z"     # most precise first
    assert anchors[1] == "x y"
    assert anchors[2] == "x"
    assert anchors[-1] == "computer science improve X"   # field+goal fallback rung
    assert all(v.route == ROUTE_FILTER for v in variants)


# --- collect wiring ---------------------------------------------------------

class _FilterHitClient:
    """One hit on the first (filter) page, then empty."""

    def __init__(self) -> None:
        self.calls: List[Dict] = []

    def get(self, params: Dict) -> Dict:
        self.calls.append(params)
        if len(self.calls) == 1:
            return {"results": [{"id": "W1", "display_name": "hit",
                                 "publication_year": 2021,
                                 "abstract_inverted_index": {"foo": [0]}}]}
        return {"results": []}


def test_collect_uses_field_scoped_filter_first():
    collector = Collector(CollectConfig(max_pages=3))
    collector.client = _FilterHitClient()
    out = collector.collect(_theme(["graph neural networks"]))
    assert "title_and_abstract.search:graph neural networks" in collector.client.calls[0]["filter"]
    assert [w.id for w in out] == ["W1"]


class _FilterEmptyThenSearchClient:
    """Filter route returns nothing; the generic-search fallback returns a hit."""

    def __init__(self) -> None:
        self.calls: List[Dict] = []

    def get(self, params: Dict) -> Dict:
        self.calls.append(params)
        if "filter" in params:
            return {"results": []}
        if "search" in params and params["search"]:
            if sum(1 for c in self.calls if "search" in c) == 1:
                return {"results": [{"id": "WS", "display_name": "fallback hit",
                                     "publication_year": 2021,
                                     "abstract_inverted_index": {"foo": [0]}}]}
        return {"results": []}


def test_collect_falls_back_to_generic_search_when_filter_empty():
    collector = Collector(CollectConfig(max_pages=2))
    collector.client = _FilterEmptyThenSearchClient()
    out = collector.collect(_theme(["obscure thin theme"]))
    assert "filter" in collector.client.calls[0]
    assert any("search" in c for c in collector.client.calls)
    assert [w.id for w in out] == ["WS"]


# --- Topic-ID resolution (Phase 1 completion) -------------------------------

def test_exclude_field_ids_and_max_referenced_works_render():
    sq = StructuredQuery(
        cites=["W1", "W2"],
        exclude_field_ids=["17"],
        work_type="article",
        max_referenced_works=100,
    )
    flt = sq.to_params()["filter"]
    assert flt == "cites:W1|W2,primary_topic.field.id:!17,type:article,referenced_works_count:<100"


def test_resolve_field_ids_maps_common_domains():
    assert resolve_field_ids("computer science") == ["17"]
    assert resolve_field_ids("CS") == ["17"]
    assert resolve_field_ids("Biochemistry, Genetics and Molecular Biology") == ["13"]
    assert resolve_field_ids("quantum gravity zoology") == []   # no match -> skip scoping
    assert all(fid in OPENALEX_FIELDS for fid in resolve_field_ids("neuroscience"))


def _work_in_field(work_id: str, field_id: str) -> Work:
    return Work(id=work_id, title=work_id, year=2021, venue="", doi=None,
                cited_by_count=0, abstract="a",
                source_meta={"primary_topic_field_id": field_id})


def test_dominant_field_ids_picks_the_home_domain():
    works = [_work_in_field(f"W{i}", "17") for i in range(4)]
    works += [_work_in_field("W10", "13"), _work_in_field("W11", "13")]
    works += [_work_in_field("W20", "31")]   # singleton -> below min_count
    assert dominant_field_ids(works, max_fields=2, min_count=2) == ["17", "13"]
    assert dominant_field_ids([], min_count=2) == []


def test_parser_extracts_primary_topic_field_into_source_meta():
    payload = {
        "id": "W1",
        "display_name": "paper",
        "publication_year": 2022,
        "primary_topic": {
            "field": {"id": "https://openalex.org/fields/17", "display_name": "Computer Science"},
        },
    }
    w = normalize_work(payload)
    assert w.source_meta["primary_topic_field_id"] == "17"
    assert w.source_meta["primary_topic_field_name"] == "Computer Science"


def test_collect_and_filter_routes_base_variants_through_filter(monkeypatch):
    # No assumption queries (offline), so only the field-scoped base variants run.
    import src.pipeline.collect as collect_mod
    monkeypatch.setattr(collect_mod, "generate_assumption_queries", lambda *a, **k: [])

    client = _FilterHitClient()

    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = client

    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)
    out = collect_and_filter(_theme(["alpha", "beta"]), CollectConfig(max_pages=2),
                             use_assumption_queries=True)
    assert "title_and_abstract.search:alpha beta" in client.calls[0]["filter"]
    assert [w.id for w in out] == ["W1"]
