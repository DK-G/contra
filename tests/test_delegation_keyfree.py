"""Key-free Track B delegation: agent facets -> semantic collection -> raw materials -> post-gate.

Covers spec_from_payload (agent facets -> SerendipitySpec), material_from_work (the inverse of
work_from_material, so contra's raw collection round-trips through the agent), and
collect_track_b_from_spec (semantic collection that must NEVER call the LLM).
"""

from __future__ import annotations

from typing import Dict, List

import src.pipeline.collect as collect_mod
from src.core.models import Concept, Keywords, Scope, ThemeInput, Work
from src.openalex.client import OpenAlexError
from src.pipeline.collect import CollectConfig, collect_track_b_from_spec
from src.pipeline.delegate import material_from_work, work_from_material
from src.pipeline.serendipity_query import SerendipityFacet, SerendipitySpec, spec_from_payload


def _theme(field: str = "computer science") -> ThemeInput:
    return ThemeInput(
        theme_overview="o" * 50, goal="g", why_problem="w", approach_type="design",
        assumptions=[], scope=Scope(field=field, scale="micro", time_range="no_limit"),
        keywords=Keywords(include=["alpha"], exclude=[]),
    )


# --- spec_from_payload ------------------------------------------------------

def test_spec_from_payload_parses_dedups_caps():
    spec = spec_from_payload("a threshold cascade", [
        {"domain": "ecology", "pseudo_abstract": "populations collapse past a tipping point"},
        {"domain": "Ecology", "pseudo_abstract": "dup domain dropped"},   # case-insensitive dedup
        {"domain": "finance", "pseudo_abstract": ""},                      # empty pseudo dropped
        {"domain": "epidemiology", "pseudo_abstract": "outbreaks when R0 exceeds one"},
        {"domain": "materials", "pseudo_abstract": "crack propagation accelerates"},
    ], n=3)
    assert spec.structure == "a threshold cascade"
    assert [f.domain for f in spec.facets] == ["ecology", "epidemiology", "materials"]


def test_spec_from_payload_empty_when_no_valid_facets():
    assert spec_from_payload("s", [{"domain": "x", "pseudo_abstract": ""}]).is_empty()
    assert spec_from_payload("s", []).is_empty()


# --- material_from_work round-trips with work_from_material ------------------

def test_material_from_work_round_trip():
    w = Work(id="W1", title="t", year=2021, venue="V", doi="10.1/x", cited_by_count=7,
             abstract="abs", concepts=["C-a"],
             concept_tags=[Concept(name="ml", level=1, score=0.5, id="C1")],
             publication_type="article", referenced_works=["R1", "R2"])
    w2 = work_from_material(material_from_work(w))
    assert w2.id == "W1" and w2.title == "t" and w2.year == 2021
    assert w2.abstract == "abs" and w2.doi == "10.1/x" and w2.cited_by_count == 7
    assert w2.concepts == ["C-a"] and w2.referenced_works == ["R1", "R2"]
    assert w2.publication_type == "article"
    assert [(t.name, t.level) for t in w2.concept_tags] == [("ml", 1)]


# --- collect_track_b_from_spec is key-free semantic (no LLM) ----------------

class _SemClient:
    def __init__(self, results: List[Dict]) -> None:
        self.calls: List[Dict] = []
        self._r = results

    def get(self, params: Dict) -> Dict:
        self.calls.append(params)
        return {"results": self._r} if "search.semantic" in params else {"results": []}


def _raw(wid: str, fid) -> Dict:
    d: Dict = {"id": wid, "display_name": wid, "publication_year": 2021,
               "abstract_inverted_index": {"foo": [0]}}
    if fid is not None:
        d["primary_topic"] = {"field": {"id": f"https://openalex.org/fields/{fid}",
                                        "display_name": f"F{fid}"}}
    return d


def _patch_collector(monkeypatch, client):
    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = client
    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)


def test_collect_from_spec_is_keyfree_semantic(monkeypatch):
    # If contra reached for the LLM facet generator this would raise; assert it never does.
    def _boom(*a, **k):
        raise AssertionError("collect_track_b_from_spec must not call the LLM")
    monkeypatch.setattr(collect_mod, "generate_serendipity_facets", _boom)
    client = _SemClient([_raw("WH", "17"), _raw("WD1", "13"), _raw("WD2", "28")])
    _patch_collector(monkeypatch, client)

    spec = SerendipitySpec("struct", [SerendipityFacet("bio", "abs")])
    out = collect_track_b_from_spec(_theme(), spec, CollectConfig(per_page=50, max_pages=5),
                                    home_field_ids=["17"])
    assert "search.semantic" in client.calls[0]      # used the semantic endpoint
    assert [w.id for w in out] == ["WD1", "WD2"]      # home field 17 excluded client-side


def test_collect_from_spec_empty_spec_makes_no_call(monkeypatch):
    client = _SemClient([])
    _patch_collector(monkeypatch, client)
    out = collect_track_b_from_spec(_theme(), SerendipitySpec("", []), CollectConfig())
    assert out == [] and client.calls == []          # empty spec -> no API call at all


class _FlakyClient:
    """500s on the first facet's query (the semantic endpoint is intermittently down), then OK."""

    def __init__(self, results: List[Dict]) -> None:
        self.calls = 0
        self._r = results

    def get(self, params: Dict) -> Dict:
        self.calls += 1
        if self.calls == 1:
            raise OpenAlexError("request failed: HTTP Error 500: Internal Server Error")
        return {"results": self._r}


def test_collect_from_spec_skips_flaky_facet(monkeypatch):
    # facet 'a' 500s and is skipped; facet 'b' still contributes (one flaky facet != whole abort).
    client = _FlakyClient([_raw("WD1", "13"), _raw("WD2", "28"), _raw("WD3", "13")])
    _patch_collector(monkeypatch, client)
    spec = SerendipitySpec("struct", [SerendipityFacet("a", "abs1"), SerendipityFacet("b", "abs2")])
    out = collect_track_b_from_spec(_theme(), spec, CollectConfig(per_page=50, max_pages=5),
                                    home_field_ids=["17"])
    assert client.calls == 2
    assert [w.id for w in out] == ["WD1", "WD2", "WD3"]
