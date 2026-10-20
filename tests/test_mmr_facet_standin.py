"""F-61 (survey 2026-10-14 EX将棋): under materials_lean the echoed candidates have no concept
tags, so MMR reduced to score order and all 3 output slots went to one facet. The echoed
`facet` stands in for the tags (same facet = 0.18, the measured within-facet concept Jaccard)."""

from __future__ import annotations

from src.core.models import Concept
from src.pipeline.classify import _SAME_FACET_SIM, _mmr_rerank, _redundancy
from src.pipeline.delegate import work_from_material


def _m(wid, facet=None, tags=None):
    m = {"id": wid, "title": wid, "abstract": "a"}
    if facet:
        m["facet"] = facet
    if tags:
        m["concept_tags"] = [{"name": n, "level": 1, "score": 0.5} for n in tags]
    return m


def test_lean_picks_spread_over_facets():
    mats = [_m("A1", "ecology"), _m("A2", "ecology"), _m("A3", "ecology"), _m("B1", "sport")]
    works = {m["id"]: work_from_material(m) for m in mats}
    scored = [(0.60, "A1", {}), (0.58, "A2", {}), (0.56, "A3", {}), (0.52, "B1", {})]
    picks = [i for _s, i, _d in _mmr_rerank(scored, works, lam=0.7, count=3)]
    assert picks == ["A1", "B1", "A2"]


def test_without_facet_lean_stays_score_order():
    works = {m["id"]: work_from_material(m) for m in [_m("A1"), _m("A2"), _m("A3"), _m("B1")]}
    scored = [(0.60, "A1", {}), (0.58, "A2", {}), (0.56, "A3", {}), (0.52, "B1", {})]
    assert [i for _s, i, _d in _mmr_rerank(scored, works, lam=0.7, count=3)] == ["A1", "A2", "A3"]


def test_concept_tags_take_precedence_over_facet():
    a = work_from_material(_m("A", "f", ["x", "y"]))
    b = work_from_material(_m("B", "f", ["z"]))
    assert _redundancy(a, b) == 0.0
    assert _redundancy(work_from_material(_m("C", "f")), work_from_material(_m("D", "f"))) == _SAME_FACET_SIM
