"""F-40 (2026-09-29): a failed lexical seed leg must not end a bybridge run the semantic leg can carry.

At 21:03 JST OpenAlex answered every anonymous `search=` / `title_and_abstract.search` request
with 503 ("Anonymous search is paused ...") while `search.semantic` kept answering 200. The
lexical seed leg raised, and the whole run ended in a traceback before the semantic leg was asked.
"""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest

import src.mcp_server as mcp_mod
from src.core.models import Work
from src.openalex.client import OpenAlexError

_PAUSED = "OpenAlex が匿名の全文検索を一時停止しています（503）"


def _work(wid: str, refs=("B1",)) -> Work:
    return Work(id=wid, title=f"t {wid}", year=2024, venue="v", doi=None, cited_by_count=1,
                abstract="a", referenced_works=list(refs))


def _paused(*a, **k):
    raise OpenAlexError(_PAUSED)


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(mcp_mod, "resolve_work_labels", lambda *a, **k: {})
    monkeypatch.setattr(mcp_mod, "filter_live_bridges", lambda b, *a, **k: (set(b), []))
    monkeypatch.setattr(mcp_mod, "collect_and_filter", _paused)
    monkeypatch.setattr(mcp_mod, "collect_citation_candidates",
                        lambda *a, **k: [_work(f"C{i}") for i in range(5)])
    from src.openalex import client as _client
    _client.reset_run_stats()


def _args(**over) -> Dict[str, Any]:
    args = {
        "theme_overview": "t" * 200, "goal": "g", "why_problem": "w",
        "approach_type": "application", "assumptions": ["a", "b"], "scope_field": "medicine",
        "materials": True, "no_history": True, "min_seeds": 2, "seed_count": 3, "bridge_count": 3,
    }
    args.update(over)
    return args


def _call(args):
    return mcp_mod.StdinMcpServer().handle_tool_call("bybridge_collect", args)


def test_semantic_leg_carries_the_roster_and_the_output_says_why(monkeypatch, offline):
    sem = [_work("S1"), _work("S2"), _work("S3")]
    monkeypatch.setattr(mcp_mod, "collect_seeds_semantic_report", lambda *a, **k: (sem, None))
    res = _call(_args(diagnostics=False))  # named even with diagnostics off
    text = res["content"][0]["text"]
    assert not res.get("isError")
    assert "F-40" in text and "semantic レッグだけ" in text and "一時停止" in text
    mats = json.loads(text[text.index("\n[") + 1:])
    assert len(mats) == 5


def test_thin_semantic_roster_is_still_refused_and_names_the_lexical_failure(monkeypatch, offline):
    monkeypatch.setattr(mcp_mod, "collect_seeds_semantic_report", lambda *a, **k: ([_work("S1")], None))
    text = _call(_args())["content"][0]["text"]
    assert "F-26" in text and "F-40" in text


def test_without_the_semantic_leg_the_failure_still_surfaces(monkeypatch, offline):
    monkeypatch.setattr(mcp_mod, "collect_seeds_semantic_report", lambda *a, **k: ([_work("S1")], None))
    res = _call(_args(seed_semantic=False))
    text = res["content"][0]["text"]
    assert res.get("isError") and "一時停止" in text
