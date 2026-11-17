"""F-89 (seihai 2026-11-17 BACI facet; callers' scores over 51 byserendipity runs): within a
facet, records in another language than the preferred one go behind that facet's own-language
records (opt-in). They are deferred, not dropped. The facet breakdown names them either way."""

from __future__ import annotations

from test_same_abstract_dedup import _abstract, _raw, _run

from src.mcp_server import StdinMcpServer, _facet_breakdown_line
from src.pipeline.collect import CollectConfig


def _lang(rec, code):
    rec["language"] = code
    return rec


def _page(n_en: int, start: int = 0):
    page = [_lang(_raw("W90", "Evaluacion de impacto ambiental", _abstract(90)), "es"),
            _lang(_raw("W91", "환경영향평가 제도", _abstract(91)), "ko")]
    page += [_lang(_raw(f"W{start + i}", f"English paper {start + i}", _abstract(start + i)), "en")
             for i in range(n_en)]
    page.append(_raw("W99", "No language code", _abstract(99)))   # no code = preferred
    return page


_ON = CollectConfig(facet_language_preference="en")


def test_other_language_goes_behind_and_is_named(monkeypatch):
    out, stats = _run(monkeypatch, [_page(3)], _ON)
    assert [w.id for w in out] == ["W0", "W1", "W2", "W99", "W90", "W91"]   # deferred, kept
    assert stats[0]["off_language"] == 2
    assert stats[0]["off_language_selected"] == 2
    line = _facet_breakdown_line(stats)
    assert "英語以外 2 件〔es 1・ko 1〕は後回し・うち提出 2 件" in line


def test_deferred_records_lose_their_slot_when_the_facet_has_enough(monkeypatch):
    # three facets share 6 slots -> 2 each; facet 1's two slots go to its English records
    out, stats = _run(monkeypatch, [_page(3), _page(3, 10), _page(3, 20)],
                      CollectConfig(facet_language_preference="en"))
    import src.pipeline.collect as collect_mod
    out = collect_mod._interleave_facet_buckets(
        [[w for w in out if (w.source_meta or {}).get("serendipity_facet", "").startswith(f"[{k}]")]
         for k in (1, 2, 3)], 6)
    assert all((w.language or "en") == "en" for w in out)


def test_default_keeps_endpoint_order_and_still_counts(monkeypatch):
    out, stats = _run(monkeypatch, [_page(2)])
    assert [w.id for w in out] == ["W90", "W91", "W0", "W1", "W99"]
    line = _facet_breakdown_line(stats)
    assert "英語以外 2 件〔es 1・ko 1〕・うち提出 2 件" in line
    assert "後回し" not in line


def test_count_can_be_switched_off(monkeypatch):
    _out, stats = _run(monkeypatch, [_page(2)], CollectConfig(facet_language_count=None))
    assert "英語以外" not in _facet_breakdown_line(stats)


def test_dedup_index_follows_the_reorder(monkeypatch):
    # facet 2 brings a better record (DOI) of facet 1's English W1: it must replace W1 in place,
    # not whichever record now sits at W1's old position
    page2 = [_raw("W51", "English paper 1", _abstract(51), doi="https://doi.org/10.1/x")]
    page2 += [_raw(f"W{60 + i}", f"Other paper {i}", _abstract(60 + i)) for i in range(6)]
    out, _stats = _run(monkeypatch, [_page(2), page2], _ON)
    ids = [w.id for w in out]
    assert "W51" in ids and "W1" not in ids
    assert "W90" in ids and "W91" in ids


def test_schema_declares_facet_language():
    tools = {t["name"]: t for t in StdinMcpServer().list_tools()}
    props = tools["byserendipity_discover"]["inputSchema"]["properties"]
    assert props["facet_language"]["default"] is None
