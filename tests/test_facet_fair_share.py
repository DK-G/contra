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


# --- F-16: one shortened retry on a 400, and no "saturated" verdict for an outage --------

def test_facet_400_is_retried_once_with_a_shorter_query(monkeypatch):
    """2026-08-31 and 2026-09-04: the caller's own fix was always 'same domain words, shorter'.
    Doing it automatically is what turns a lost distance band into a normal harvest."""
    import src.pipeline.collect as collect_mod
    from src.pipeline.collect import CollectConfig, collect_track_b_from_spec
    from src.pipeline.serendipity_query import SerendipityFacet, SerendipitySpec
    from src.openalex.client import OpenAlexError

    sent = []

    class _Client:
        def get(self, params):
            q = params["search.semantic"]
            sent.append(q)
            if len(q) > 600:
                raise OpenAlexError("request failed: HTTP Error 400: Bad Request")
            return {"results": [{"id": f"W{i}", "display_name": f"hit{i}",
                                 "publication_year": 2020,
                                 "abstract_inverted_index": {"a": [0]},
                                 "primary_topic": {"field": {
                                     "id": "https://openalex.org/fields/27",
                                     "display_name": "Medicine"}}} for i in range(12)]}

    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = _Client()

    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)
    spec = SerendipitySpec(structure="s" * 700,
                           facets=[SerendipityFacet(domain="far domain", pseudo_abstract="p" * 200)])
    stats = []
    out = collect_track_b_from_spec(_theme(), spec, CollectConfig(), home_field_ids=["20"],
                                    stats_out=stats)
    assert len(sent) == 2 and len(sent[1]) < len(sent[0])   # retried, shorter
    assert len(out) == 12 and out[0].id == "W0"
    assert "短縮" in stats[0]["status"]


def test_zero_harvest_message_names_the_transport_causes_before_saturation(monkeypatch):
    """F-16 (2026-09-04): the 0-candidate message offered only 'too close' and 'saturated',
    and the caller nearly retired a live theme on it. Transport causes must come first."""
    import src.mcp_server as mcp_mod

    def _no_works(*a, **k):
        stats = k.get("stats_out")
        if stats is not None:
            stats.append({"domain": "far domain", "status": "取得失敗 (HTTP Error 400: Bad Request)",
                          "returned": 0, "kept": 0, "selected": 0})
        return []

    monkeypatch.setattr(mcp_mod, "collect_track_b_from_spec", _no_works)
    res = mcp_mod.StdinMcpServer().handle_tool_call("byserendipity_discover", {
        "theme_overview": "Patch departure under a marginal value rule. " * 6,
        "goal": "find a stopping rule", "why_problem": "budget is finite",
        "approach_type": "application", "assumptions": ["a" * 5, "b" * 5],
        "scope_field": "economics", "scope_scale": "small", "scope_time_range": "no_limit",
        "raw_only": True, "no_history": True,
        "facets": [{"domain": "behavioural ecology", "pseudo_abstract": "foraging patch leaving"}],
        "structure": "a threshold that fires on a level rather than an edge",
    })
    text = res["content"][0]["text"]
    assert "0件" in text
    assert "400" in text and "429" in text and "504" in text
    assert text.index("400") < text.index("飽和")
