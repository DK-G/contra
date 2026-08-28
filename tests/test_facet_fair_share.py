"""F-18: every facet is queried, and every facet gets a share of the candidate cap.

The observed failure (2026-08-27 / 2026-08-28, byserendipity raw_only): the calling agent supplied
three A2 facets (Near / Far / Very Far) and the Very Far one returned 0 candidates twice, while the
same pseudo-abstract sent alone returned 42. The mechanism was contra's own collection loop, not
OpenAlex: facets were appended in order and the loop broke as soon as ``max_count`` was reached, so
facets 1+2 filled the cap and facet 3 was never requested at all (which is why the fetch diagnostic
reported 2 requests for 3 facets and still called the run clean).

These tests pin (a) the old signature as a regression, (b) fair-share allocation, (c) the per-facet
stats that make a starving facet visible to the caller.
"""

from __future__ import annotations

from typing import Any, Dict, List

import src.pipeline.collect as collect_mod
from src.core.models import Keywords, Scope, ThemeInput
from src.mcp_server import _facet_breakdown_line
from src.openalex.client import OpenAlexError
from src.pipeline.collect import CollectConfig, collect_track_b_from_spec
from src.pipeline.serendipity_query import SerendipityFacet, SerendipitySpec


def _theme(field: str = "computer science") -> ThemeInput:
    return ThemeInput(
        theme_overview="o" * 50, goal="g", why_problem="w", approach_type="design",
        assumptions=[], scope=Scope(field=field, scale="micro", time_range="no_limit"),
        keywords=Keywords(include=["alpha"], exclude=[]),
    )


def _raw(wid: str, fid: str = "13") -> Dict[str, Any]:
    return {"id": wid, "display_name": wid, "publication_year": 2021,
            "abstract_inverted_index": {"foo": [0]},
            "primary_topic": {"field": {"id": f"https://openalex.org/fields/{fid}",
                                        "display_name": f"F{fid}"}}}


class _PerFacetClient:
    """Returns a distinct 50-work page per facet, in call order (the live endpoint's page size)."""

    def __init__(self, prefixes: List[str], per_facet: int = 50) -> None:
        self.prefixes = prefixes
        self.per_facet = per_facet
        self.calls: List[Dict[str, Any]] = []

    def get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        idx = len(self.calls)
        self.calls.append(params)
        if idx >= len(self.prefixes):
            return {"results": []}
        pre = self.prefixes[idx]
        return {"results": [_raw(f"{pre}{i}") for i in range(self.per_facet)]}


def _patch_collector(monkeypatch, client) -> None:
    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = client
    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)


def _spec() -> SerendipitySpec:
    return SerendipitySpec("struct", [
        SerendipityFacet("near", "a" * 40),
        SerendipityFacet("far", "b" * 40),
        SerendipityFacet("very far", "c" * 40),
    ])


# --- (a) the old behaviour, pinned so the regression is legible -------------------------

def test_legacy_flag_reproduces_the_starved_far_facet(monkeypatch):
    client = _PerFacetClient(["N", "F", "V"])
    _patch_collector(monkeypatch, client)
    stats: List[Dict[str, Any]] = []
    out = collect_track_b_from_spec(
        _theme(), _spec(), CollectConfig(facet_fair_share=False),
        max_count=60, home_field_ids=["17"], stats_out=stats,
    )
    assert len(client.calls) == 2                     # facet 3 never requested
    assert len(out) == 60
    assert {w.id[0] for w in out} == {"N", "F"}       # Very Far contributes nothing
    assert stats[2]["status"].startswith("未取得")
    assert [r["selected"] for r in stats] == [50, 10, 0]


# --- (b) the fix ------------------------------------------------------------------------

def test_fair_share_queries_every_facet_and_gives_each_a_share(monkeypatch):
    client = _PerFacetClient(["N", "F", "V"])
    _patch_collector(monkeypatch, client)
    stats: List[Dict[str, Any]] = []
    out = collect_track_b_from_spec(
        _theme(), _spec(), CollectConfig(),          # fair share is the default
        max_count=60, home_field_ids=["17"], stats_out=stats,
    )
    assert len(client.calls) == 3                     # every facet requested
    assert len(out) == 60                             # same yield as before
    assert [r["selected"] for r in stats] == [20, 20, 20]
    assert [r["returned"] for r in stats] == [50, 50, 50]
    assert {w.id[0] for w in out} == {"N", "F", "V"}


def test_fair_share_donates_unused_slots_and_never_yields_less(monkeypatch):
    # A thin facet must not cost the run candidates: its unused slots go to the others.
    client = _PerFacetClient(["N", "F", "V"])
    client.per_facet = 50

    class _Mixed(_PerFacetClient):
        def get(self, params):
            idx = len(self.calls)
            self.calls.append(params)
            sizes = [50, 50, 3]
            pre = ["N", "F", "V"][idx] if idx < 3 else "X"
            return {"results": [_raw(f"{pre}{i}") for i in range(sizes[idx] if idx < 3 else 0)]}

    mixed = _Mixed([], per_facet=0)
    _patch_collector(monkeypatch, mixed)
    stats: List[Dict[str, Any]] = []
    out = collect_track_b_from_spec(
        _theme(), _spec(), CollectConfig(), max_count=60, home_field_ids=["17"], stats_out=stats,
    )
    assert len(out) == 60                              # cap still filled
    assert [r["selected"] for r in stats] == [29, 28, 3]


def test_single_facet_is_unchanged_by_fair_share(monkeypatch):
    client = _PerFacetClient(["N"])
    _patch_collector(monkeypatch, client)
    spec = SerendipitySpec("struct", [SerendipityFacet("near", "a" * 40)])
    out = collect_track_b_from_spec(
        _theme(), spec, CollectConfig(), max_count=60, home_field_ids=["17"],
    )
    assert [w.id for w in out] == [f"N{i}" for i in range(50)]


def test_failed_facet_is_recorded_not_silently_dropped(monkeypatch):
    class _Flaky(_PerFacetClient):
        def get(self, params):
            idx = len(self.calls)
            self.calls.append(params)
            if idx == 2:
                raise OpenAlexError("request failed: HTTP Error 500: Internal Server Error")
            return {"results": [_raw(f"{['N', 'F'][idx]}{i}") for i in range(5)]}

    _patch_collector(monkeypatch, _Flaky([], per_facet=0))
    stats: List[Dict[str, Any]] = []
    out = collect_track_b_from_spec(
        _theme(), _spec(), CollectConfig(), max_count=60, home_field_ids=["17"], stats_out=stats,
    )
    assert len(out) == 10
    assert stats[2]["status"].startswith("取得失敗")
    assert stats[2]["selected"] == 0


# --- (c) the instrument -----------------------------------------------------------------

def test_breakdown_line_names_the_empty_facet():
    line = _facet_breakdown_line([
        {"domain": "clinical trials", "status": "ok", "returned": 50, "kept": 44, "selected": 44},
        {"domain": "community ecology", "status": "ok", "returned": 50, "kept": 16, "selected": 16},
        {"domain": "software testing", "status": "ok", "returned": 0, "kept": 0, "selected": 0},
    ])
    assert "clinical trials" in line and "提出 44" in line
    assert "収穫0の facet: software testing" in line


def test_breakdown_line_is_silent_when_every_facet_contributed():
    line = _facet_breakdown_line([
        {"domain": "a", "status": "ok", "returned": 50, "kept": 20, "selected": 20},
        {"domain": "b", "status": "ok", "returned": 50, "kept": 20, "selected": 20},
    ])
    assert "収穫0" not in line and "★facet 別内訳" in line


def test_breakdown_line_flags_a_rejected_facet():
    line = _facet_breakdown_line([
        {"domain": "a", "status": "棄却 (home convergence)", "returned": 50, "kept": 0, "selected": 0},
    ])
    assert "棄却" in line and "収穫0の facet: a" in line
