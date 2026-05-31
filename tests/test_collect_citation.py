"""Tests for the citation 2-hop collection path (collect.py)."""

from __future__ import annotations

from typing import Dict, List

from src.core.models import Concept, Work
from src.pipeline.collect import (
    CollectConfig,
    _bridge_pool_from_seeds,
    _seed_l0_concept_ids,
    collect_citation_candidates,
)


def _concept(cid: str, level: int, name: str = "") -> Concept:
    return Concept(name=name or cid, level=level, score=0.5, id=cid)


def _seed(work_id: str, refs: List[str], l0_ids: List[str]) -> Work:
    return Work(
        id=work_id,
        title=work_id,
        year=2020,
        venue="",
        doi=None,
        cited_by_count=0,
        abstract="abstract",
        concept_tags=[_concept(c, 0) for c in l0_ids],
        referenced_works=refs,
    )


# --- _bridge_pool_from_seeds ------------------------------------------------

def test_bridge_pool_prioritises_shared_then_round_robin():
    wa = _seed("WA", ["W100", "W101", "W102"], ["C1"])
    wb = _seed("WB", ["W100", "W200"], ["C1"])
    pool = _bridge_pool_from_seeds([wa, wb], cap=3)
    assert pool[0] == "W100"          # shared by both seeds -> ranked first
    assert "W101" in pool             # WA's contribution
    assert "W200" in pool             # WB's contribution (round-robin gives each a slot)
    assert len(pool) == 3


def test_bridge_pool_caps_total():
    refs = [f"W{i}" for i in range(100)]
    pool = _bridge_pool_from_seeds([_seed("WA", refs, ["C1"])], cap=50)
    assert len(pool) == 50


def test_bridge_pool_dedupes_within_seed():
    pool = _bridge_pool_from_seeds([_seed("WA", ["W1", "W1", "W2"], ["C1"])], cap=10)
    assert pool == ["W1", "W2"]


# --- _seed_l0_concept_ids ---------------------------------------------------

def test_seed_l0_concept_ids_strips_url_and_dedupes():
    s1 = _seed("WA", [], ["https://openalex.org/C1", "C2"])
    s2 = _seed("WB", [], ["https://openalex.org/C1"])
    ids = _seed_l0_concept_ids([s1, s2])
    assert "C1" in ids and "C2" in ids
    assert ids.count("C1") == 1
    assert all(not i.startswith("http") for i in ids)


def test_seed_l0_concept_ids_ignores_non_l0():
    seed = Work(
        id="WA", title="WA", year=2020, venue="", doi=None, cited_by_count=0,
        abstract="a",
        concept_tags=[_concept("C1", 0), _concept("C9", 2)],
        referenced_works=[],
    )
    assert _seed_l0_concept_ids([seed]) == ["C1"]


# --- collect_citation_candidates --------------------------------------------

class _FakeClient:
    """Returns one cross-domain hit on the first call, then empty pages."""

    def __init__(self) -> None:
        self.calls: List[Dict] = []

    def get(self, params: Dict) -> Dict:
        self.calls.append(params)
        if len(self.calls) == 1:
            return {
                "results": [
                    {
                        "id": "WX",
                        "display_name": "cross domain paper",
                        "publication_year": 2021,
                        "abstract_inverted_index": {"foo": [0]},
                        "referenced_works": [],
                    }
                ]
            }
        return {"results": []}


def _patch_collector(monkeypatch, client):
    import src.pipeline.collect as collect_mod

    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = client

    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)


def test_collect_citation_candidates_builds_cites_filter(monkeypatch):
    client = _FakeClient()
    _patch_collector(monkeypatch, client)
    seeds = [_seed("WA", ["W100", "W101"], ["C1", "C2"])]

    out = collect_citation_candidates(seeds, CollectConfig(max_pages=3), max_count=10)

    flt = client.calls[0]["filter"]
    assert "cites:" in flt
    assert "W100" in flt and "W101" in flt
    assert "concepts.id:!C1" in flt and "concepts.id:!C2" in flt
    assert "type:article" in flt
    assert "referenced_works_count:<100" in flt
    assert [w.id for w in out] == ["WX"]   # seed WA excluded, WX returned


def test_collect_citation_candidates_excludes_seeds_and_used(monkeypatch):
    # Make the fake return a seed id and a used id; both must be filtered out.
    class _C(_FakeClient):
        def get(self, params):
            self.calls.append(params)
            if len(self.calls) == 1:
                return {"results": [
                    {"id": "WA", "display_name": "self", "publication_year": 2021},
                    {"id": "USED", "display_name": "used", "publication_year": 2021},
                    {"id": "WX", "display_name": "ok", "publication_year": 2021},
                ]}
            return {"results": []}

    client = _C()
    _patch_collector(monkeypatch, client)
    seeds = [_seed("WA", ["W100"], ["C1"])]
    out = collect_citation_candidates(seeds, CollectConfig(max_pages=2),
                                      max_count=10, used_ids={"USED"})
    assert [w.id for w in out] == ["WX"]


def test_collect_citation_candidates_returns_empty_when_no_bridges(monkeypatch):
    # No referenced_works -> no bridges -> no API call, empty result.
    called = {"n": 0}

    class _C(_FakeClient):
        def get(self, params):
            called["n"] += 1
            return {"results": []}

    _patch_collector(monkeypatch, _C())
    out = collect_citation_candidates([_seed("WA", [], ["C1"])], CollectConfig())
    assert out == []
    assert called["n"] == 0
