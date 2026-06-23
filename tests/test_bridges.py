"""Tests for citation-bridge scoring (Phase 2 bybridge: co-citation + betweenness)."""

from __future__ import annotations

from typing import List, Optional

from src.core.models import Work
from src.pipeline.bridges import (
    annotate_bridge_signals,
    bridge_field_diversity,
    bridge_rank_key,
    rank_bridge_candidates,
    shared_bridge_count,
)


def _w(wid: str, refs: List[str], field: Optional[str] = None, cited: int = 0) -> Work:
    return Work(
        id=wid, title=wid, year=2021, venue="", doi=None, cited_by_count=cited,
        abstract="a", referenced_works=refs,
        source_meta=({"primary_topic_field_id": field} if field else {}),
    )


def test_shared_bridge_count_counts_distinct_bridges():
    bridges = {"B1", "B2", "B3"}
    assert shared_bridge_count(_w("W", ["B1", "B2", "X"]), bridges) == 2
    assert shared_bridge_count(_w("W", ["B1", "B1"]), bridges) == 1   # distinct only
    assert shared_bridge_count(_w("W", []), bridges) == 0


def test_bridge_field_diversity_counts_distinct_fields_per_bridge():
    cands = [
        _w("W1", ["B1"], field="17"),
        _w("W2", ["B1"], field="13"),
        _w("W3", ["B1"], field="13"),   # duplicate field -> still 2 distinct for B1
        _w("W4", ["B2"], field="31"),
    ]
    div = bridge_field_diversity(cands, {"B1", "B2"})
    assert div["B1"] == 2
    assert div["B2"] == 1


def test_annotate_sets_count_and_betweenness():
    cands = [
        _w("W1", ["B1", "B2"], field="17"),
        _w("W2", ["B1"], field="13"),
        _w("W3", ["B2"], field="31"),
    ]
    annotate_bridge_signals(cands, {"B1", "B2"})
    w1 = cands[0].source_meta
    assert w1["shared_bridge_count"] == 2
    # B1 spans {17,13}=2, B2 spans {17,31}=2 -> max = 2
    assert w1["bridge_betweenness"] == 2


def test_bridge_rank_key_orders_betweenness_then_coupling():
    a = _w("A", [], cited=5)
    a.source_meta = {"bridge_betweenness": 1, "shared_bridge_count": 3}
    b = _w("B", [], cited=5)
    b.source_meta = {"bridge_betweenness": 2, "shared_bridge_count": 1}
    # B wins on betweenness despite lower co-citation strength.
    assert sorted([a, b], key=bridge_rank_key, reverse=True)[0].id == "B"


def test_rank_bridge_candidates_annotates_and_sorts():
    cands = [_w("LOW", ["B1"], field="17"), _w("HIGH", ["B1", "B2"], field="13")]
    ranked = rank_bridge_candidates(cands, {"B1", "B2"})
    assert ranked[0].id == "HIGH"   # shared 2 + betweenness 2 (B1 spans 17,13)
    assert cands[0].source_meta["shared_bridge_count"] >= 1   # annotated in place
