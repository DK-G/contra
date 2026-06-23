"""Tests for Phase 3 serendipity query generation + validation and the semantic Track B path."""

from __future__ import annotations

import json
from typing import Dict, List, Optional

import src.openai_client as openai_client
import src.pipeline.collect as collect_mod
from src.core.models import Keywords, Scope, ThemeInput
from src.openalex.parser import normalize_work
from src.pipeline.query import ROUTE_SEMANTIC
from src.pipeline.serendipity_query import (
    MAX_FACETS,
    SerendipityFacet,
    SerendipitySpec,
    build_semantic_query,
    exclude_home_field,
    generate_serendipity_facets,
    home_field_fraction,
    validate_semantic_results,
)
from src.pipeline.collect import CollectConfig, collect_track_b


def _theme(field: str = "computer science") -> ThemeInput:
    return ThemeInput(
        theme_overview="o" * 200,
        goal="improve information diffusion prediction",
        why_problem="w",
        approach_type="design",
        assumptions=["a"],
        scope=Scope(field=field, scale="micro", time_range="no_limit"),
        keywords=Keywords(include=["information diffusion"], exclude=[]),
    )


def _work(work_id: str, field_id: Optional[str], *, abstract: bool = True):
    """Build a parsed Work with a primary_topic Field id (via the real parser)."""
    payload: Dict = {"id": work_id, "display_name": work_id, "publication_year": 2021}
    if abstract:
        payload["abstract_inverted_index"] = {"foo": [0]}
    if field_id is not None:
        payload["primary_topic"] = {"field": {"id": f"https://openalex.org/fields/{field_id}",
                                              "display_name": f"F{field_id}"}}
    return normalize_work(payload)


# --- build_semantic_query ---------------------------------------------------

def test_build_semantic_query_combines_structure_and_pseudo_abstract():
    sq = build_semantic_query("a threshold feedback loop under a cap",
                              "In ecology, populations collapse past a tipping point...")
    assert sq.route == ROUTE_SEMANTIC
    assert sq.work_type == "article"
    text = sq.anchor_string()
    assert text.startswith("a threshold feedback loop under a cap")
    assert "tipping point" in text
    params = sq.to_params(per_page=50)
    assert "search.semantic" in params and "search" not in params
    assert params["filter"] == "type:article"


def test_build_semantic_query_tolerates_empty_structure():
    sq = build_semantic_query("", "only the pseudo abstract")
    assert sq.anchor_string() == "only the pseudo abstract"


# --- home_field_fraction / exclude_home_field -------------------------------

def test_home_field_fraction_and_exclusion():
    works = [_work("W1", "17"), _work("W2", "17"), _work("W3", "13"), _work("W4", None)]
    # 2 of 4 are in the home field 17; W4 (no field) counts as non-home (conservative).
    assert home_field_fraction(works, ["17"]) == 0.5
    assert home_field_fraction([], ["17"]) == 0.0
    assert home_field_fraction(works, []) == 0.0   # no home ids -> nothing is "home"
    kept = exclude_home_field(works, ["17"])
    assert [w.id for w in kept] == ["W3", "W4"]
    assert exclude_home_field(works, []) == works   # no exclusion when no home ids


# --- validate_semantic_results ----------------------------------------------

def test_validate_accepts_distant_spread():
    works = [_work("W1", "13"), _work("W2", "28"), _work("W3", "13"), _work("W4", "17")]
    ok, reason = validate_semantic_results(works, ["17"])
    assert ok and reason == "ok"


def test_validate_rejects_too_few():
    ok, reason = validate_semantic_results([_work("W1", "13")], ["17"], min_results=3)
    assert not ok and reason == "too_few"


def test_validate_rejects_home_converged():
    works = [_work(f"W{i}", "17") for i in range(5)]   # all home
    ok, reason = validate_semantic_results(works, ["17"])
    assert not ok and reason == "home_converged"


def test_validate_rejects_when_no_distant_survivor():
    # 3 raw (passes min + home-fraction at exactly the cap) but only home works survive exclusion.
    works = [_work("W1", "17"), _work("W2", "17"), _work("W3", "17")]
    ok, reason = validate_semantic_results(works, ["17"], max_home_fraction=1.0)
    assert not ok and reason == "no_distant"


# --- generate_serendipity_facets (LLM parse + fallback) ---------------------

def _patch_llm(monkeypatch, output_text=None, raise_err=False):
    def fake(payload, config=None):
        if raise_err:
            raise openai_client.OpenAIError("boom")
        return {"output_text": output_text, "usage": {}}
    monkeypatch.setattr(openai_client, "responses_create", fake)


def test_generate_facets_parses_structure_and_facets(monkeypatch):
    out = json.dumps({
        "structure": "a self-reinforcing cascade past a threshold",
        "facets": [
            {"domain": "epidemiology", "pseudo_abstract": "Outbreaks spread when R0 exceeds one..."},
            {"domain": "materials science", "pseudo_abstract": "Crack propagation accelerates past..."},
            {"domain": "epidemiology", "pseudo_abstract": "dup domain should be dropped"},
            {"domain": "ecology", "pseudo_abstract": ""},   # empty pseudo dropped
            {"domain": "economics", "pseudo_abstract": "Bank runs cascade when..."},
        ],
    })
    _patch_llm(monkeypatch, out)
    spec = generate_serendipity_facets(_theme(), n=MAX_FACETS)
    assert spec.structure.startswith("a self-reinforcing cascade")
    domains = [f.domain for f in spec.facets]
    assert domains == ["epidemiology", "materials science", "economics"]   # dedup + drop-empty, cap 3
    assert all(f.pseudo_abstract for f in spec.facets)


def test_generate_facets_empty_on_llm_error(monkeypatch):
    _patch_llm(monkeypatch, raise_err=True)
    spec = generate_serendipity_facets(_theme())
    assert spec.is_empty()


def test_generate_facets_empty_on_unparseable(monkeypatch):
    _patch_llm(monkeypatch, "not json at all")
    assert generate_serendipity_facets(_theme()).is_empty()


# --- collect_track_b: semantic primary path ---------------------------------

class _SemClient:
    """Returns a fixed top-50-style set for search.semantic; empty otherwise."""

    def __init__(self, results: List[Dict]) -> None:
        self.calls: List[Dict] = []
        self._results = results

    def get(self, params: Dict) -> Dict:
        self.calls.append(params)
        if "search.semantic" in params:
            return {"results": self._results}
        return {"results": []}


def _patch_collector(monkeypatch, client):
    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = client
    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)


def _raw(work_id: str, field_id: Optional[str]) -> Dict:
    d: Dict = {"id": work_id, "display_name": work_id, "publication_year": 2021,
               "abstract_inverted_index": {"foo": [0]}}
    if field_id is not None:
        d["primary_topic"] = {"field": {"id": f"https://openalex.org/fields/{field_id}",
                                        "display_name": f"F{field_id}"}}
    return d


def test_collect_track_b_uses_semantic_and_excludes_home(monkeypatch):
    # one valid facet; raw set = 1 home (17) + 2 distant (13, 28). Home excluded client-side.
    monkeypatch.setattr(collect_mod, "generate_serendipity_facets",
                        lambda *a, **k: SerendipitySpec("struct", [SerendipityFacet("bio", "abs")]))
    client = _SemClient([_raw("WH", "17"), _raw("WD1", "13"), _raw("WD2", "28")])
    _patch_collector(monkeypatch, client)

    out = collect_track_b(_theme(), CollectConfig(per_page=50, max_pages=5),
                          home_field_ids=["17"])
    assert "search.semantic" in client.calls[0]
    assert [w.id for w in out] == ["WD1", "WD2"]   # home WH dropped


def test_collect_track_b_quality_gate_falls_back_to_lexical(monkeypatch):
    # The single facet's semantic query is home-converged (all field 17) -> validation fails ->
    # fall back to the lexical baseline, which returns a hit on a generic `search`.
    monkeypatch.setattr(collect_mod, "generate_serendipity_facets",
                        lambda *a, **k: SerendipitySpec("struct", [SerendipityFacet("bio", "abs")]))
    monkeypatch.setattr(collect_mod, "generate_track_b_queries", lambda *a, **k: ["lexical q"])

    class _C:
        def __init__(self) -> None:
            self.calls: List[Dict] = []

        def get(self, params: Dict) -> Dict:
            self.calls.append(params)
            if "search.semantic" in params:
                return {"results": [_raw(f"WH{i}", "17") for i in range(4)]}   # all home -> reject
            if params.get("search") == "lexical q" and params.get("page") == 1:
                return {"results": [_raw("WLEX", "13")]}
            return {"results": []}

    client = _C()
    _patch_collector(monkeypatch, client)
    out = collect_track_b(_theme(), CollectConfig(per_page=50, max_pages=2),
                          home_field_ids=["17"])
    assert any("search.semantic" in c for c in client.calls)        # semantic was tried
    assert any(c.get("search") == "lexical q" for c in client.calls)  # then fell back
    assert [w.id for w in out] == ["WLEX"]


def test_collect_track_b_use_semantic_false_is_pure_lexical(monkeypatch):
    monkeypatch.setattr(collect_mod, "generate_track_b_queries", lambda *a, **k: ["lexical q"])

    class _C:
        def __init__(self) -> None:
            self.calls: List[Dict] = []

        def get(self, params: Dict) -> Dict:
            self.calls.append(params)
            if params.get("search") == "lexical q" and params.get("page") == 1:
                return {"results": [_raw("WLEX", "13")]}
            return {"results": []}

    client = _C()
    _patch_collector(monkeypatch, client)
    out = collect_track_b(_theme(), CollectConfig(max_pages=2), use_semantic=False)
    assert not any("search.semantic" in c for c in client.calls)
    assert [w.id for w in out] == ["WLEX"]


def test_collect_track_b_falls_back_when_no_facets_generated(monkeypatch):
    # generation failed (offline) -> empty spec -> straight to lexical without any semantic call.
    monkeypatch.setattr(collect_mod, "generate_serendipity_facets", lambda *a, **k: SerendipitySpec())
    monkeypatch.setattr(collect_mod, "generate_track_b_queries", lambda *a, **k: ["lexical q"])

    class _C:
        def __init__(self) -> None:
            self.calls: List[Dict] = []

        def get(self, params: Dict) -> Dict:
            self.calls.append(params)
            if params.get("search") == "lexical q":
                return {"results": [_raw("WLEX", "13")]}
            return {"results": []}

    client = _C()
    _patch_collector(monkeypatch, client)
    out = collect_track_b(_theme(), CollectConfig(max_pages=2), home_field_ids=["17"])
    assert not any("search.semantic" in c for c in client.calls)
    assert [w.id for w in out] == ["WLEX"]
