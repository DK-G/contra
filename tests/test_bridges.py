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


# --- C(i)/C(ii) 2026-08-22 ruling: hybrid rank + head-window diversification ---

from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.bridges import (
    annotate_bridge_signals,
    annotate_hybrid_rank,
    candidate_theme_fit,
    diversify_head_by_bridge,
    hybrid_bridge_rank_key,
)


def _theme(*include):
    return ThemeInput(
        theme_overview="o", goal="g", why_problem="w", approach_type="application",
        assumptions=[], scope=Scope(field="f", scale="small", time_range="last_10_years"),
        keywords=Keywords(include=list(include), exclude=[]),
    )


def _cand(wid, title, abstract, cites, refs):
    return Work(id=wid, title=title, year=2020, venue="v", doi=None,
                cited_by_count=cites, abstract=abstract, referenced_works=refs)


def test_on_topic_low_cite_beats_off_topic_mega_cite():
    # The observed residue (F-01/P7): mega-cited off-field papers topped the list.
    # w=0.15 demotes citations to a tie-breaker.
    on_topic = _cand("W_ON", "Momentum strategies in trading", "momentum trading rules", 50, ["B1"])
    off_topic = _cand("W_OFF", "Rarefying microbiome data", "unrelated biology text", 3119, ["B1"])
    pool = [on_topic, off_topic]
    annotate_bridge_signals(pool, {"B1"})
    annotate_hybrid_rank(pool, _theme("momentum", "trading"))
    ranked = sorted(pool, key=hybrid_bridge_rank_key, reverse=True)
    assert ranked[0].id == "W_ON"


def test_unannotated_or_keywordless_pool_keeps_legacy_order():
    a = _cand("A", "t", "a", 100, ["B1", "B2"])
    b = _cand("B", "t", "a", 999, ["B1"])
    pool = [a, b]
    annotate_bridge_signals(pool, {"B1", "B2"})
    annotate_hybrid_rank(pool, _theme())         # no keywords -> hybrid all 0.0
    ranked = sorted(pool, key=hybrid_bridge_rank_key, reverse=True)
    assert ranked[0].id == "A"                   # shared-bridge count still wins


def test_head_window_capped_at_two_per_bridge():
    # The 2026-08-22 measurement: top-10 window 100% occupied by one bridge.
    hub = [_cand(f"H{i}", "t", "a", 100 - i, ["HUB"]) for i in range(10)]
    other = [_cand(f"O{i}", "t", "a", 10 - i, [f"B{i}"]) for i in range(8)]
    ranked = hub + other                          # hub candidates rank first
    out = diversify_head_by_bridge(ranked, {"HUB", *{f"B{i}" for i in range(8)}}, window=10)
    head = out[:10]
    assert sum(1 for w in head if w.id.startswith("H")) == 2   # 100% -> 20%
    assert len({next(iter(w.referenced_works)) for w in head}) == 9  # 9 distinct bridges shown


def test_diversify_preserves_order_within_and_after_window():
    a = [_cand(f"H{i}", "t", "a", 0, ["HUB"]) for i in range(4)]
    out = diversify_head_by_bridge(a, {"HUB"}, window=3)
    # cap=2: H0,H1 enter the window; H2,H3 are deferred past it in their original order.
    assert [w.id for w in out] == ["H0", "H1", "H2", "H3"]


def test_structural_bridge_strength_beats_citations_when_lexical_fit_is_dark():
    # Live 2026-08-22: fit>0 for 0/60 cross-domain candidates (they live in other
    # domains' vocabulary BY DESIGN), so lexical relevance is dark and the hybrid
    # degenerated to citation order. The structural channel — how many seeds cite the
    # bridge a candidate routes through — must carry relevance instead.
    seeds = [_cand(f"S{i}", "seed", "s", 0, ["NSGA2"]) for i in range(5)]
    seeds += [_cand("S5", "seed", "s", 0, ["JUNK"])]
    via_central = _cand("W_CENTRAL", "off-vocab paper", "other domain text", 180, ["NSGA2"])
    via_junk = _cand("W_JUNK", "off-vocab mega", "other domain text", 3155, ["JUNK"])
    pool = [via_central, via_junk]
    annotate_bridge_signals(pool, {"NSGA2", "JUNK"})
    annotate_hybrid_rank(pool, _theme("quality diversity"), seeds=seeds, bridges={"NSGA2", "JUNK"})
    ranked = sorted(pool, key=hybrid_bridge_rank_key, reverse=True)
    assert ranked[0].id == "W_CENTRAL"          # 5-seed bridge beats 17x citations
    assert ranked[0].source_meta["bridge_strength"] == 5


def test_no_relevance_channel_never_degenerates_to_citations_only():
    # All-zero fit AND no seed info -> hybrid must be 0.0 everywhere (legacy fallback),
    # not 0.15 * Z(citations) which would silently re-crown the mega-cited candidate.
    a = _cand("A", "t", "a", 100, ["B1", "B2"])
    b = _cand("B", "t", "a", 9999, ["B1"])
    pool = [a, b]
    annotate_bridge_signals(pool, {"B1", "B2"})
    annotate_hybrid_rank(pool, _theme("nomatch"))
    assert all((w.source_meta["bridge_hybrid_score"] == 0.0) for w in pool)
    ranked = sorted(pool, key=hybrid_bridge_rank_key, reverse=True)
    assert ranked[0].id == "A"
