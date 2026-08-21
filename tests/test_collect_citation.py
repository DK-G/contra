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


def test_collect_citation_candidates_excludes_by_dominant_field_when_available(monkeypatch):
    # Phase 2: seeds carrying a dominant primary_topic Field exclude the home domain by
    # primary_topic.field (less aggressive, non-deprecated) INSTEAD OF L0 concepts.
    client = _FakeClient()
    _patch_collector(monkeypatch, client)

    def _seed_with_field(wid, refs, fid):
        s = _seed(wid, refs, ["C1"])
        s.source_meta = {"primary_topic_field_id": fid}
        return s

    seeds = [_seed_with_field("WA", ["W100", "W101"], "17"),
             _seed_with_field("WB", ["W100"], "17")]
    out = collect_citation_candidates(seeds, CollectConfig(max_pages=2), max_count=10)

    flt = client.calls[0]["filter"]
    assert "primary_topic.field.id:!17" in flt
    assert "concepts.id:!" not in flt          # field exclusion replaces concept exclusion
    assert "shared_bridge_count" in out[0].source_meta   # candidates annotated (Phase 2)


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


# --- F-07: duplicate seed records must not swallow the bridge pool -----------
# docs/field_observations_seihai.md F-07. The same proceedings entered the seed set twice
# under two DOIs; its 150 refs counted as "cited by 2 seeds" and filled all 50 pool slots,
# so the round-robin diversity guarantee never ran. Two guards: fold duplicate records,
# and cap each seed group at cap // 4 in BOTH tiers.

def _seed_doi(work_id: str, refs: List[str], doi: str | None = None, title: str | None = None) -> Work:
    w = _seed(work_id, refs, ["C1"])
    w.doi = doi
    if title is not None:
        w.title = title
    return w


def test_duplicate_seeds_by_ref_set_are_folded_and_capped():
    """The F-07 shape: 2 duplicate records with 150 identical refs + 18 seeds with refs."""
    dup_refs = [f"D{i}" for i in range(150)]
    seeds = [
        _seed_doi("DUP_A", dup_refs, doi="10.46299/isg.p.2024.1.8", title="Priority Areas"),
        _seed_doi("DUP_B", list(dup_refs), doi="10.46299/isg.2024.1.8", title="Proceedings VIII"),
    ]
    seeds += [_seed_doi(f"S{i}", [f"S{i}_R{j}" for j in range(18)], doi=f"10.1/{i}") for i in range(18)]
    pool = _bridge_pool_from_seeds(seeds, cap=50)
    assert len(pool) == 50
    from_dup = [r for r in pool if r.startswith("D")]
    assert len(from_dup) <= 50 // 4                    # quota, not 50/50
    assert len({r.split("_")[0] for r in pool if not r.startswith("D")}) >= 10  # many seeds contribute


def test_duplicate_seeds_do_not_create_a_shared_tier():
    """Two records of ONE work must not make their refs look 'cited by 2 seeds'."""
    dup_refs = [f"D{i}" for i in range(20)]
    a = _seed_doi("DUP_A", dup_refs, doi="10.9/a", title="Same Work")
    b = _seed_doi("DUP_B", list(dup_refs), doi="10.9/b", title="Same Work")
    other = _seed_doi("S0", [f"X{i}" for i in range(20)], doi="10.9/c", title="Other")
    pool = _bridge_pool_from_seeds([a, b, other], cap=20)
    # folded -> 2 groups, quota 5 each, then backfill; the real seed keeps a genuine share
    assert len([r for r in pool if r.startswith("X")]) >= 5


def test_seed_quota_applies_to_the_shared_tier_too():
    """A shared tier big enough to fill `cap` must still leave room for other seeds."""
    shared = [f"H{i}" for i in range(60)]
    a = _seed_doi("A", shared + ["A1"], doi="10.1/a", title="A")
    b = _seed_doi("B", list(shared) + ["B1"], doi="10.1/b", title="B")
    c = _seed_doi("C", [f"C{i}" for i in range(30)], doi="10.1/c", title="C")
    pool = _bridge_pool_from_seeds([a, b, c], cap=40)
    assert len(pool) == 40
    assert len([r for r in pool if r.startswith("C")]) >= 10   # C is not shut out by the shared tier


def test_single_seed_still_fills_the_pool():
    """The quota is fairness, not a ceiling: nobody else to be fair to -> full pool."""
    pool = _bridge_pool_from_seeds([_seed("WA", [f"W{i}" for i in range(100)], ["C1"])], cap=50)
    assert len(pool) == 50


def test_backfill_keeps_pool_full_when_others_are_ref_poor():
    rich = _seed_doi("R", [f"R{i}" for i in range(80)], doi="10.2/r", title="R")
    poor = _seed_doi("P", ["P0"], doi="10.2/p", title="P")
    pool = _bridge_pool_from_seeds([rich, poor], cap=50)
    assert len(pool) == 50
    assert "P0" in pool


def test_distinct_papers_sharing_a_few_refs_are_not_folded():
    a = _seed_doi("A", [f"A{i}" for i in range(20)] + ["S1", "S2"], doi="10.3/a", title="Alpha")
    b = _seed_doi("B", [f"B{i}" for i in range(20)] + ["S1", "S2"], doi="10.3/b", title="Beta")
    pool = _bridge_pool_from_seeds([a, b], cap=10)
    assert pool[0] in ("S1", "S2")     # genuinely shared refs still rank first
