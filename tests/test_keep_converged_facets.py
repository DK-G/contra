"""F-92 (llm-evolve 2026-11-20): a facet aimed at random matrix theory under a Computer Science
home came back 26/38 CS (Signal Processing) and was rejected as home_converged, taking its 12
Mathematics records with it. Opt-in keep_converged_facets keeps the non-home records; with it
off the rejection line counts what was thrown away."""

from __future__ import annotations

from test_same_abstract_dedup import _abstract, _raw, _run

from src.mcp_server import StdinMcpServer, _facet_breakdown_line
from src.pipeline.collect import CollectConfig


def _field(rec, fid, name):
    rec["primary_topic"] = {"field": {"id": f"https://openalex.org/fields/{fid}", "display_name": name}}
    return rec


def _converged_page():
    page = [_field(_raw(f"W{i}", f"Signal processing paper {i}", _abstract(i)), 17, "Computer Science")
            for i in range(7)]                                                   # 7/10 home > 0.6
    page += [_field(_raw(f"W{100 + i}", f"Random matrix paper {i}", _abstract(100 + i)), 26, "Mathematics")
             for i in range(3)]
    return page


def test_default_rejects_and_counts_the_non_home_records(monkeypatch):
    out, stats = _run(monkeypatch, [_converged_page()])
    assert out == []
    assert stats[0]["status"] == "棄却 (home_converged)"
    assert stats[0]["converged_distant"] == 3
    line = _facet_breakdown_line(stats)
    assert "ホーム Field の外のレコードがありました（[1] 3 件）" in line
    assert "keep_converged_facets:true" in line


def test_opt_in_keeps_only_the_non_home_records(monkeypatch):
    out, stats = _run(monkeypatch, [_converged_page()], CollectConfig(keep_converged_facets=True))
    assert [w.id for w in out] == ["W100", "W101", "W102"]
    assert stats[0]["status"].startswith("ok（home_converged＝返却 10 件のうちホーム Field 7 件")
    line = _facet_breakdown_line(stats)
    assert "提出 3" in line and "棄却" not in line


def test_opt_in_does_not_rescue_a_facet_with_nothing_outside_home(monkeypatch):
    page = [_field(_raw(f"W{i}", f"Signal processing paper {i}", _abstract(i)), 17, "Computer Science")
            for i in range(5)]
    out, stats = _run(monkeypatch, [page], CollectConfig(keep_converged_facets=True))
    assert out == [] and stats[0]["status"] == "棄却 (home_converged)"
    assert "ホーム Field の外" not in _facet_breakdown_line(stats)


def test_schema_declares_keep_converged_facets_off_by_default():
    tools = {t["name"]: t for t in StdinMcpServer().list_tools()}
    props = tools["byserendipity_discover"]["inputSchema"]["properties"]
    assert props["keep_converged_facets"]["default"] is False
