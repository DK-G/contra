"""Tests for pseudo-relevance feedback (PRF) in near-field seed collection (collect_and_filter)."""

from __future__ import annotations

from typing import Dict, List

import src.pipeline.collect as collect_mod
from src.core.models import Keywords, Scope, ThemeInput, Work
from src.pipeline.collect import CollectConfig, _salient_terms, collect_and_filter


def _theme(include: List[str], field: str = "computer science", goal: str = "improve retention") -> ThemeInput:
    return ThemeInput(
        theme_overview="o" * 50,
        goal=goal,
        why_problem="w",
        approach_type="design",
        assumptions=[],
        scope=Scope(field=field, scale="micro", time_range="no_limit"),
        keywords=Keywords(include=include, exclude=[]),
    )


def _work(wid: str, abstract: str, title: str = "paper") -> Work:
    return Work(id=wid, title=title, year=2021, venue="", doi=None,
                cited_by_count=0, abstract=abstract)


# --- _salient_terms ---------------------------------------------------------

def test_salient_terms_ranks_by_seed_df_and_drops_noise():
    seeds = [
        _work("1", "cascade influence network model"),   # 'model' is boilerplate
        _work("2", "cascade influence diffusion study"),  # 'study' is boilerplate
        _work("3", "cascade spreading"),
        _work("4", "influence cascade"),
    ]
    # 'diffusion' is already a query term -> excluded even though it appears.
    salient = _salient_terms(seeds, existing_terms=["diffusion"], top_k=5, min_seed_df=2)
    assert salient == ["cascade", "influence"]   # df 4 then 3; rest are singletons/stopwords
    assert "model" not in salient and "study" not in salient   # boilerplate dropped
    assert "network" not in salient and "spreading" not in salient  # seed_df==1 dropped
    assert "diffusion" not in salient   # already-known query term dropped


def test_salient_terms_respects_top_k():
    seeds = [_work(str(i), "alpha beta gamma delta epsilon") for i in range(3)]
    assert len(_salient_terms(seeds, [], top_k=2)) == 2


def test_salient_terms_empty_when_no_repeated_terms():
    seeds = [_work("1", "alpha"), _work("2", "beta")]   # nothing recurs across seeds
    assert _salient_terms(seeds, []) == []


# --- collect_and_filter PRF wiring ------------------------------------------

class _PrfClient:
    """Base query 'alpha' returns N cascade-laden seeds; the PRF expansion 'alpha cascade'
    returns one fresh paper; everything else is empty."""

    def __init__(self, n_seeds: int) -> None:
        self.calls: List[Dict] = []
        self._seeds = [
            {"id": f"S{i}", "display_name": "paper",
             "abstract_inverted_index": {"cascade": [0], f"uniq{i}": [1]}}
            for i in range(n_seeds)
        ]

    def get(self, params: Dict) -> Dict:
        self.calls.append(params)
        flt = params.get("filter", "")
        if "cascade" in flt:   # the PRF expansion query (anchor + salient term)
            return {"results": [{"id": "WPRF", "display_name": "prf hit",
                                 "abstract_inverted_index": {"cascade": [0]}}]}
        if "title_and_abstract.search:alpha" in flt:
            return {"results": self._seeds}
        return {"results": []}


def _patch(monkeypatch, client):
    monkeypatch.setattr(collect_mod, "generate_assumption_queries", lambda *a, **k: [])

    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = client
    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)


def test_prf_expands_when_seed_pool_is_thin(monkeypatch):
    client = _PrfClient(n_seeds=6)   # >= _PRF_MIN_SEEDS and < max_count
    _patch(monkeypatch, client)
    out = collect_and_filter(_theme(["alpha"]), CollectConfig(max_pages=1), max_count=500)
    ids = [w.id for w in out]
    assert "WPRF" in ids   # PRF surfaced a paper the base keyword query missed
    assert any("title_and_abstract.search:alpha cascade" in c.get("filter", "") for c in client.calls)


def test_prf_does_not_fire_when_too_few_seeds(monkeypatch):
    client = _PrfClient(n_seeds=3)   # below _PRF_MIN_SEEDS
    _patch(monkeypatch, client)
    out = collect_and_filter(_theme(["alpha"]), CollectConfig(max_pages=1), max_count=500)
    assert [w.id for w in out] == ["S0", "S1", "S2"]
    assert not any("cascade" in c.get("filter", "") for c in client.calls)


def test_prf_does_not_fire_when_pool_already_full(monkeypatch):
    client = _PrfClient(n_seeds=6)
    _patch(monkeypatch, client)
    out = collect_and_filter(_theme(["alpha"]), CollectConfig(max_pages=1), max_count=3)
    assert len(out) == 3
    assert not any("cascade" in c.get("filter", "") for c in client.calls)


def test_prf_can_be_disabled(monkeypatch):
    client = _PrfClient(n_seeds=6)
    _patch(monkeypatch, client)
    out = collect_and_filter(_theme(["alpha"]), CollectConfig(max_pages=1), max_count=500, use_prf=False)
    assert "WPRF" not in [w.id for w in out]
    assert not any("cascade" in c.get("filter", "") for c in client.calls)
