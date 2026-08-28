"""F-13: three-layer seed stage — home-Field scoping, semantic seed leg, alignment instrument.

The recorded failure (docs/field_observations_seihai.md F-13, 7+ reproductions): the bybridge
seed search matches a handful of keywords by surface form with no field scope and no view of the
theme's prose, so a homograph ('trade', 'admission', 'sequential') pulls the whole roster into an
unrelated discipline — and the run's diagnostics still look healthy because every downstream
stage runs correctly on the wrong roster. These tests pin the three additive layers:

(B) every lexical seed query — ladder rungs, PRF expansions, and the generic-search fallback —
    carries ``primary_topic.field.id`` when the caller declares home fields;
(C) ``collect_seeds_semantic`` queries the theme's own prose via ``search.semantic`` (no LLM),
    keeps the home field client-side, and fails open; ``merge_seed_pools`` fair-shares the legs;
(A) ``seed_domain_alignment`` / ``render_seed_alignment`` name where the roster actually landed.
"""

from __future__ import annotations

from typing import Any, Dict, List

import src.pipeline.collect as collect_mod
from src.core.models import Keywords, Scope, ThemeInput, Work
from src.openalex.client import OpenAlexError
from src.pipeline.bridge_diagnostics import (
    SEED_ALIGNMENT_WARN_BELOW,
    render_seed_alignment,
    seed_domain_alignment,
)
from src.pipeline.collect import (
    CollectConfig,
    collect_and_filter,
    collect_seeds_semantic,
    merge_seed_pools,
)
from src.pipeline.query import ROUTE_FILTER, ROUTE_SEARCH, StructuredQuery


def _theme(keywords: List[str] = None) -> ThemeInput:
    return ThemeInput(
        theme_overview="o" * 60, goal="detect equivalence", why_problem="w",
        approach_type="design", assumptions=[],
        scope=Scope(field="economics", scale="micro", time_range="no_limit"),
        keywords=Keywords(include=keywords if keywords is not None else ["trade"], exclude=[]),
    )


def _raw(wid: str, fid: str = "20", fname: str = "Economics", refs: List[str] = None) -> Dict[str, Any]:
    return {"id": wid, "display_name": wid, "publication_year": 2021,
            "abstract_inverted_index": {"foo": [0]},
            "referenced_works": refs or ["R1"],
            "primary_topic": {"field": {"id": f"https://openalex.org/fields/{fid}",
                                        "display_name": fname}}}


class _CaptureClient:
    def __init__(self, results: List[Dict[str, Any]]) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._r = results

    def get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append(params)
        return {"results": self._r}


def _patch_collector(monkeypatch, client) -> None:
    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = client
    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)


# --- (B) lexical field scoping ----------------------------------------------------------

def test_home_field_ids_scope_every_lexical_query(monkeypatch):
    client = _CaptureClient([_raw("W1")])
    _patch_collector(monkeypatch, client)
    monkeypatch.setattr(collect_mod, "generate_assumption_queries", lambda *a, **k: [])
    collect_and_filter(_theme(), CollectConfig(max_pages=1), max_count=1,
                       use_prf=False, home_field_ids=["20"])
    assert client.calls, "no query issued"
    for params in client.calls:
        assert "primary_topic.field.id:20" in params.get("filter", ""), params


def test_no_home_field_ids_keeps_legacy_unscoped_queries(monkeypatch):
    client = _CaptureClient([_raw("W1")])
    _patch_collector(monkeypatch, client)
    monkeypatch.setattr(collect_mod, "generate_assumption_queries", lambda *a, **k: [])
    collect_and_filter(_theme(), CollectConfig(max_pages=1), max_count=1, use_prf=False)
    for params in client.calls:
        assert "primary_topic.field.id" not in params.get("filter", ""), params


def test_generic_search_fallback_keeps_the_field_scope(monkeypatch):
    # The precise filter query misses; the recall fallback must NOT roam every discipline.
    class _EmptyThenHit(_CaptureClient):
        def get(self, params):
            self.calls.append(params)
            if "search" in params:                 # the fallback (generic search) route
                return {"results": [_raw("W1")]}
            return {"results": []}                 # every filter-route query misses

    client = _EmptyThenHit([])
    _patch_collector(monkeypatch, client)
    monkeypatch.setattr(collect_mod, "generate_assumption_queries", lambda *a, **k: [])
    out = collect_and_filter(_theme(["nonexistent-term"]), CollectConfig(max_pages=1),
                             max_count=5, use_prf=False, home_field_ids=["20"])
    assert [w.id for w in out] == ["W1"]
    search_calls = [p for p in client.calls if "search" in p]
    assert search_calls, "fallback never ran"
    for params in search_calls:
        assert params.get("filter") == "primary_topic.field.id:20", params


# --- (C) semantic seed leg --------------------------------------------------------------

def test_semantic_seeds_query_theme_prose_and_keep_home_field(monkeypatch):
    client = _CaptureClient([
        _raw("W_ECON", "20", "Economics"),
        _raw("W_MED", "27", "Medicine"),
        _raw("W_NOFIELD", "", ""),   # unclassified: kept (fail-open)
    ])
    _patch_collector(monkeypatch, client)
    out = collect_seeds_semantic(_theme(), CollectConfig(), home_field_ids=["20"])
    params = client.calls[0]
    assert "search.semantic" in params
    assert "o" * 60 in params["search.semantic"]           # theme prose, not keywords
    assert "detect equivalence" in params["search.semantic"]
    ids = [w.id for w in out]
    assert "W_ECON" in ids and "W_NOFIELD" in ids and "W_MED" not in ids


def test_semantic_seeds_fail_open_on_endpoint_error(monkeypatch):
    class _Down:
        calls = 0
        def get(self, params):
            raise OpenAlexError("HTTP Error 500")
    _patch_collector(monkeypatch, _Down())
    assert collect_seeds_semantic(_theme(), CollectConfig(), home_field_ids=["20"]) == []


def test_semantic_seeds_never_call_the_llm(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("collect_seeds_semantic must not call the LLM")
    monkeypatch.setattr(collect_mod, "generate_serendipity_facets", _boom)
    monkeypatch.setattr(collect_mod, "generate_assumption_queries", _boom)
    client = _CaptureClient([_raw("W1")])
    _patch_collector(monkeypatch, client)
    out = collect_seeds_semantic(_theme(), CollectConfig(), home_field_ids=["20"])
    assert [w.id for w in out] == ["W1"]


def _w(wid: str) -> Work:
    return Work(id=wid, title=wid, year=2021, venue="V", doi=None, cited_by_count=0, abstract="a")


def test_merge_seed_pools_fair_shares_and_dedups():
    lex = [_w(f"L{i}") for i in range(4)] + [_w("SHARED")]
    sem = [_w("SHARED")] + [_w(f"S{i}") for i in range(4)]
    out = merge_seed_pools(lex, sem, max_count=6)
    ids = [w.id for w in out]
    assert len(ids) == len(set(ids)) == 6                      # capped, no duplicates
    assert sum(i.startswith("L") for i in ids) == 3            # fair share: 3 lexical...
    assert sum(i.startswith("S") for i in ids) == 3            # ...3 semantic
    # With the cap lifted, the work both legs returned appears exactly once (id dedup).
    full = [w.id for w in merge_seed_pools(lex, sem, max_count=20)]
    assert full.count("SHARED") == 1 and len(full) == 9


def test_merge_seed_pools_with_empty_semantic_leg_is_lexical_passthrough():
    lex = [_w(f"L{i}") for i in range(3)]
    assert [w.id for w in merge_seed_pools(lex, [], 10)] == ["L0", "L1", "L2"]


# --- (A) alignment instrument -----------------------------------------------------------

def _seed(fid: str, fname: str) -> Work:
    w = _w(f"W_{fid}_{fname}")
    if fid:
        w.source_meta = {"primary_topic_field_id": fid, "primary_topic_field_name": fname}
    return w


def test_alignment_stats_fraction_and_top_fields():
    seeds = [_seed("20", "Economics")] * 3 + [_seed("27", "Medicine")] * 2 + [_seed("", "")]
    stats = seed_domain_alignment(seeds, ["20"])
    assert stats["total"] == 6 and stats["unknown"] == 1
    assert stats["home"] == 3 and abs(stats["fraction"] - 0.6) < 1e-9
    assert stats["top_fields"][0] == ("Economics", 3)


def test_alignment_render_warns_on_drifted_roster():
    # The 2026-08-27 shape: economics theme, roster of agriculture/medicine records.
    seeds = [_seed("11", "Agricultural and Biological Sciences")] * 4 + [_seed("27", "Medicine")]
    stats = seed_domain_alignment(seeds, ["20"])
    assert stats["fraction"] == 0.0 < SEED_ALIGNMENT_WARN_BELOW
    line = render_seed_alignment(stats, home_label="economics")
    assert "Agricultural and Biological Sciences 4" in line
    assert "⚠" in line and "F-13" in line


def test_alignment_render_is_calm_on_home_roster():
    seeds = [_seed("20", "Economics")] * 5
    line = render_seed_alignment(seed_domain_alignment(seeds, ["20"]))
    assert "100%" in line and "⚠" not in line


def test_alignment_within_field_drift_is_not_flagged_but_names_are_shown():
    # The 2026-08-24 'trade' -> trade-policy case stays inside Economics: the fraction cannot
    # catch it, so the instrument's value there is the printed field names (and the caller's
    # reading of the seed titles). Pin that the line stays calm — this is a documented limit.
    seeds = [_seed("20", "Economics")] * 5
    stats = seed_domain_alignment(seeds, ["20"])
    assert stats["fraction"] == 1.0
    assert "⚠" not in render_seed_alignment(stats)


def test_alignment_unresolved_home_field_reports_not_a_zero():
    # S-68: "no information" must not be encoded as a bad value — when scope.field resolves to
    # nothing, the line says "判定不能", it does not claim 0% alignment.
    seeds = [_seed("20", "Economics")]
    stats = seed_domain_alignment(seeds, [])
    assert stats["fraction"] is None
    line = render_seed_alignment(stats)
    assert "判定不能" in line and "⚠" not in line
