"""F-85-D (2026-11-16): each bridge's share is filled with citers outside the seeds' home Domain
first. Same-Domain citers (the home's sibling Fields) are deferred, not dropped.

Measured before the change on 1,680 caller-scored bybridge candidates (28 runs): same-Domain
sibling Fields 81% anomaly (Business/Accounting under a Finance roster 96%, none useful) vs
other Domains 65% (Mathematics 29%).
"""

from __future__ import annotations

from typing import Dict, List

from src.core.models import Work
from src.pipeline.collect import CollectConfig, collect_citation_candidates, work_domain_id


def _seed(wid: str, refs: List[str], field: str) -> Work:
    return Work(id=wid, title=wid, year=2020, venue="", doi=None, cited_by_count=0,
                abstract="a", referenced_works=refs,
                source_meta={"primary_topic_field_id": field})


class _Client:
    """Each bridge answers with 8 Business (same Domain as Finance) citers, then 4 Mathematics."""

    def __init__(self) -> None:
        self.calls: List[Dict] = []

    @staticmethod
    def _work(wid: str, ref: str, field: str) -> Dict:
        return {"id": wid, "display_name": wid, "publication_year": 2021,
                "abstract_inverted_index": {"x": [0]}, "referenced_works": [ref],
                "primary_topic": {"id": "https://openalex.org/T1", "display_name": "t",
                                  "field": {"id": f"https://openalex.org/fields/{field}",
                                            "display_name": "f"}}}

    def get(self, params: Dict) -> Dict:
        self.calls.append(params)
        cites = params.get("filter", "").split("cites:", 1)[1].split(",", 1)[0].split("|")
        if len(cites) > 1:
            return {"results": []}           # no backfill from the OR scan
        b = cites[0]
        per_page = int(params.get("per-page", 50))
        rows = ([self._work(f"{b}biz{i}", b, "14") for i in range(8)]
                + [self._work(f"{b}math{i}", b, "26") for i in range(4)])
        return {"results": rows[:per_page]}


def _patch(monkeypatch, client):
    import src.pipeline.collect as collect_mod

    class _C:
        def __init__(self, cfg=None):
            self.client = client

    monkeypatch.setattr(collect_mod, "Collector", _C)


def _seeds():
    return [_seed("S1", ["B0"], "20"), _seed("S2", ["B0"], "20")]   # Finance home -> Social Sciences


def test_other_domain_citers_take_the_share_first(monkeypatch):
    _patch(monkeypatch, _Client())
    stats: Dict = {}
    out = collect_citation_candidates(_seeds(), CollectConfig(), max_count=60,
                                      bridges=[f"B{i}" for i in range(10)], stats=stats)
    assert len(out) == 60
    per_bridge = {}
    for w in out:
        per_bridge.setdefault(w.referenced_works[0], []).append(work_domain_id(w))
    # 6 slots per bridge: all 4 Mathematics citers, then 2 Business ones (deferred, not dropped)
    assert all(v.count("3") == 4 and v.count("2") == 2 for v in per_bridge.values())
    assert stats["home_domains"] == ["2"]
    assert stats["deferred"] == 40           # page order would have taken 6 Business; 2 were


def test_unfiled_records_go_after_same_domain(monkeypatch):
    class _Unfiled(_Client):
        def get(self, params):
            res = super().get(params)["results"]
            b = res[0]["referenced_works"][0]
            junk = [{"id": f"{b}idx{i}", "display_name": "Volume 23 Index", "publication_year": 2021,
                     "referenced_works": [b]} for i in range(3)]
            return {"results": junk + res}

    _patch(monkeypatch, _Unfiled())
    out = collect_citation_candidates(_seeds(), CollectConfig(), max_count=60,
                                      bridges=[f"B{i}" for i in range(10)])
    assert not any("idx" in w.id for w in out)


def test_off_switch_keeps_page_order(monkeypatch):
    _patch(monkeypatch, _Client())
    stats: Dict = {}
    out = collect_citation_candidates(_seeds(), CollectConfig(home_domain_preference=False),
                                      max_count=60, bridges=[f"B{i}" for i in range(10)], stats=stats)
    assert all(work_domain_id(w) == "2" for w in out)
    assert stats["home_domains"] == [] and stats["deferred"] == 0


def test_bybridge_reports_the_preference(monkeypatch):
    import src.mcp_server as mcp_mod
    from src.openalex import client as _client
    monkeypatch.setattr(mcp_mod, "resolve_work_labels", lambda *a, **k: {})
    monkeypatch.setattr(mcp_mod, "filter_live_bridges", lambda b, *a, **k: (set(b), []))
    monkeypatch.setattr(mcp_mod, "collect_seeds_semantic_report", lambda *a, **k: ([], None))
    _client.reset_run_stats()
    monkeypatch.setattr(mcp_mod, "collect_and_filter", lambda *a, **k: _seeds())
    seen = {}

    def _fake(seeds, cfg, **kw):
        seen["pref"] = cfg.home_domain_preference
        kw["stats"].update(home_domains=["2"], deferred=7)
        w = Work(id="C1", title="c", year=2024, venue="v", doi=None, cited_by_count=1,
                 abstract="a", referenced_works=["B0"],
                 source_meta={"primary_topic_field_id": "14"})
        return [w]

    monkeypatch.setattr(mcp_mod, "collect_citation_candidates", _fake)
    args = {"theme_overview": "t" * 200, "goal": "g", "why_problem": "w",
            "approach_type": "application", "assumptions": ["a", "b"], "scope_field": "finance",
            "materials": True, "no_history": True, "min_seeds": 0, "seed_count": 2}
    text = mcp_mod.StdinMcpServer().handle_tool_call("bybridge_collect", args)["content"][0]["text"]
    assert seen["pref"] is True
    assert "ホーム領域の後回し (F-85-D)" in text and "Social Sciences" in text and "7 件" in text
    assert "ホーム領域内 1 件" in text
    mcp_mod.StdinMcpServer().handle_tool_call("bybridge_collect", {**args, "home_domain_preference": False})
    assert seen["pref"] is False
