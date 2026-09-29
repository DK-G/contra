"""F-38 (2026-09-27): the raw outputs must be readable by the agent that has to score them.

Observed in the 2026-09-27 hindsight test (4 runs):
(a) byserendipity's raw candidates carried no facet label — the caller inferred the distance band
    from the order of the list;
(b) bybridge raw_only said "交差候補 60 件" in its diagnostics and listed 10;
(c) byserendipity returned its materials as ONE line of 190k-307k characters. The harness saved it
    to a file that Read could not page, so the caller cut it apart with Grep. 32% of it
    (91,517 of 289,330 chars in run M) was `referenced_works`, which nothing downstream of the
    byserendipity path reads.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import pytest

import src.mcp_server as mcp_mod
import src.pipeline.collect as collect_mod
from src.core.models import Work


def _long_raw(wid: str, n_words: int = 300, n_refs: int = 80) -> Dict[str, Any]:
    words = {f"word{i:03d}x": [i] for i in range(n_words)}
    return {"id": wid, "display_name": f"title {wid}", "publication_year": 2021,
            "abstract_inverted_index": words,
            "referenced_works": [f"https://openalex.org/W9{i:08d}" for i in range(n_refs)],
            "primary_topic": {"field": {"id": "https://openalex.org/fields/13",
                                        "display_name": "F13"}}}


class _FacetPages:
    """One 50-work page per facet, in call order."""

    def __init__(self, prefixes: List[str]) -> None:
        self.prefixes = prefixes
        self.calls = 0

    def get(self, params):
        pre = self.prefixes[min(self.calls, len(self.prefixes) - 1)]
        self.calls += 1
        return {"results": [_long_raw(f"{pre}{i}") for i in range(50)]}


def _serendipity_args(**over) -> Dict[str, Any]:
    args = {
        "theme_overview": "Forecast a degrading unit's health at several horizons. " * 5,
        "goal": "g", "why_problem": "w", "approach_type": "application",
        "assumptions": ["a" * 5, "b" * 5], "scope_field": "computer science",
        "scope_scale": "small", "scope_time_range": "no_limit",
        "raw_only": True, "no_history": True,
        "structure": "a latent trajectory observed through sparse biased measurements",
        "facets": [
            {"domain": "turbofan prognostics", "pseudo_abstract": "health index forecasting"},
            {"domain": "education", "pseudo_abstract": "student mastery trajectories"},
            {"domain": "sports science", "pseudo_abstract": "athlete load and injury risk"},
        ],
    }
    args.update(over)
    return args


@pytest.fixture
def facet_pages(monkeypatch):
    client = _FacetPages(["N", "F", "V"])

    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = client
    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)
    return client


def _materials(text: str) -> List[Dict[str, Any]]:
    return json.loads(text[text.index("\n[") + 1:])


def test_each_raw_candidate_names_its_facet(facet_pages):
    res = mcp_mod.StdinMcpServer().handle_tool_call("byserendipity_discover", _serendipity_args())
    mats = _materials(res["content"][0]["text"])
    assert len(mats) == 60
    by_prefix = {"N": "[1] turbofan prognostics", "F": "[2] education", "V": "[3] sports science"}
    for m in mats:
        assert m["facet"] == by_prefix[m["id"][0]], m["id"]


def test_raw_materials_are_pageable_and_drop_unused_references(facet_pages):
    res = mcp_mod.StdinMcpServer().handle_tool_call("byserendipity_discover", _serendipity_args())
    text = res["content"][0]["text"]
    mats = _materials(text)
    assert all("referenced_works" not in m for m in mats)
    assert all(m["abstract"] and m["title"] for m in mats)   # what grounding needs is intact
    longest_abstract = max(len(json.dumps(m["abstract"], ensure_ascii=False)) for m in mats)
    assert max(len(line) for line in text.splitlines()) <= longest_abstract + 40
    assert text.count("\n") > 60 * 5


def test_materials_still_round_trip_through_finalize_without_references(facet_pages):
    from src.pipeline.delegate import work_from_material
    res = mcp_mod.StdinMcpServer().handle_tool_call("byserendipity_discover", _serendipity_args())
    w = work_from_material(_materials(res["content"][0]["text"])[0])
    assert w.id == "N0" and w.referenced_works == [] and w.abstract


# --- (b) bybridge raw_only lists every candidate it reports -----------------------------

@pytest.fixture
def bridge_offline(monkeypatch):
    monkeypatch.setattr(mcp_mod, "resolve_work_labels", lambda *a, **k: {})
    monkeypatch.setattr(mcp_mod, "filter_live_bridges", lambda b, *a, **k: (set(b), []))
    monkeypatch.setattr(mcp_mod, "collect_seeds_semantic_report", lambda *a, **k: ([], None))
    from src.openalex import client as _client
    _client.reset_run_stats()


def test_bybridge_raw_only_lists_every_reported_candidate(monkeypatch, bridge_offline):
    seed = Work(id="S1", title="s", year=2024, venue="v", doi=None, cited_by_count=0,
                abstract="a", referenced_works=["B1"])
    cands = [Work(id=f"C{i:02d}", title=f"cand {i}", year=2024, venue="v", doi=None,
                  cited_by_count=i, abstract="a", referenced_works=["B1"]) for i in range(25)]
    monkeypatch.setattr(mcp_mod, "collect_and_filter", lambda *a, **k: [seed])
    monkeypatch.setattr(mcp_mod, "collect_citation_candidates", lambda *a, **k: cands)
    res = mcp_mod.StdinMcpServer().handle_tool_call("bybridge_collect", {
        "theme_overview": "t" * 200, "goal": "g", "why_problem": "w",
        "approach_type": "application", "assumptions": ["a", "b"], "scope_field": "medicine",
        "raw_only": True, "no_history": True, "min_seeds": 0, "seed_count": 2, "bridge_count": 3,
    })
    text = "\n".join(b.get("text", "") for b in res["content"])
    listed = [l for l in text.splitlines() if re.match(r"^\d+\. cand ", l)]
    assert len(listed) == 25
    assert "全 25 件" in text


def test_bybridge_materials_returns_every_reported_candidate(monkeypatch, bridge_offline):
    """F-38(b) again, materials path (seihai 2026-09-28): diagnostics said "交差候補 60 件",
    the materials JSON held 30 — ranks 31+ were cut without a word."""
    seed = Work(id="S1", title="s", year=2024, venue="v", doi=None, cited_by_count=0,
                abstract="a", referenced_works=["B1"])
    cands = [Work(id=f"C{i:02d}", title=f"cand {i}", year=2024, venue="v", doi=None,
                  cited_by_count=i, abstract="a", referenced_works=["B1"]) for i in range(45)]
    monkeypatch.setattr(mcp_mod, "collect_and_filter", lambda *a, **k: [seed])
    monkeypatch.setattr(mcp_mod, "collect_citation_candidates", lambda *a, **k: cands)
    res = mcp_mod.StdinMcpServer().handle_tool_call("bybridge_collect", {
        "theme_overview": "t" * 200, "goal": "g", "why_problem": "w",
        "approach_type": "application", "assumptions": ["a", "b"], "scope_field": "medicine",
        "materials": True, "no_history": True, "min_seeds": 0, "seed_count": 2, "bridge_count": 3,
    })
    text = res["content"][0]["text"]
    mats = _materials(text)
    assert len(mats) == 45
    assert "交差候補 45 件" in text
    assert all("bridge_signals" in m for m in mats)
