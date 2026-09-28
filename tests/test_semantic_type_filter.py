"""F-39: the semantic route filters by type client-side, never on the endpoint.

Measured 2026-09-28: with ``filter=type:article`` the ``search.semantic`` endpoint answered 504 at
its 9.1 s gateway limit for a terrain-navigation facet on every attempt (4/4 runs of the retest,
then 5/5 probes, and with ``type:article|conference-paper`` too), while the same text passed in
1.8-3.9 s without a type filter and in 2.7 s with a year-only filter. ``type:article`` also threw
away OpenAlex's ``conference-paper`` type, ~40% of the nearest works in both probed queries.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import src.pipeline.collect as collect_mod
from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.collect import CollectConfig, collect_track_b_from_spec
from src.pipeline.query import keep_semantic_types
from src.pipeline.serendipity_query import SerendipityFacet, SerendipitySpec


def _w(t: Optional[str]):
    return SimpleNamespace(publication_type=t)


def test_article_keeps_conference_papers_and_unlabelled_works():
    works = [_w("article"), _w("conference-paper"), _w(None), _w("preprint"),
             _w("paratext"), _w("dissertation"), _w("peer-review")]
    kept = keep_semantic_types(works, "article")
    assert [w.publication_type for w in kept] == ["article", "conference-paper", None]


def test_no_work_type_means_no_filter():
    works = [_w("preprint"), _w("paratext")]
    assert keep_semantic_types(works, None) == works


# --- the facet collection path ----------------------------------------------------------

def _theme() -> ThemeInput:
    return ThemeInput(
        theme_overview="o" * 50, goal="g", why_problem="w", approach_type="design",
        assumptions=[], scope=Scope(field="computer science", scale="micro", time_range="no_limit"),
        keywords=Keywords(include=["alpha"], exclude=[]),
    )


_TYPES = ["article", "conference-paper", "preprint", "paratext", None]


def _raw(wid: str, wtype: Optional[str]) -> Dict[str, Any]:
    rec = {"id": wid, "display_name": wid, "publication_year": 2021,
           "abstract_inverted_index": {"foo": [0]},
           "primary_topic": {"field": {"id": "https://openalex.org/fields/13",
                                       "display_name": "F13"}}}
    if wtype:
        rec["type"] = wtype
    return rec


class _MixedTypeClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append(params)
        return {"results": [_raw(f"W{len(self.calls)}_{i}", _TYPES[i % len(_TYPES)])
                            for i in range(50)]}


def test_facet_request_carries_no_type_filter_and_results_are_filtered_here(monkeypatch):
    client = _MixedTypeClient()

    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = client

    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)
    stats: List[Dict[str, Any]] = []
    spec = SerendipitySpec("struct", [SerendipityFacet("navigation", "a" * 40)])
    out = collect_track_b_from_spec(_theme(), spec, CollectConfig(), max_count=60,
                                    home_field_ids=["17"], stats_out=stats)
    assert client.calls and all("type:" not in str(p.get("filter", "")) for p in client.calls)
    assert {w.publication_type for w in out} <= {"article", "conference-paper", None}
    assert stats[0]["returned"] == 30          # 50 minus 10 preprints and 10 paratext
