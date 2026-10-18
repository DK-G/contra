"""F-52 (2026-10-11): one paper under two OpenAlex ids takes one candidate slot.

Observed by the field survey on 2026-10-10 (byserendipity raw_only, theme salon-sites):
W2918009030 (the journal record) and W6926718243 ("Constructing TB Care Cascades.pdf",
a deposit DOI) carried the same abstract. The id / title / DOI checks see three different
values. Found again in the saved 2026-10-09 replay: 3 pairs among 60 candidates, each a
journal record plus a copy titled "SUMMARY" or "DISPATCHES …" with no DOI.

The shapes below are those pairs: same abstract, different id, different title, and the
copy has no DOI (or a different one).
"""

from __future__ import annotations

from typing import Any, Dict, List

import src.pipeline.collect as collect_mod
from src.core.models import Keywords, Scope, ThemeInput
from src.mcp_server import _facet_breakdown_line
from src.pipeline.collect import CollectConfig, _abstract_key, collect_track_b_from_spec
from src.pipeline.serendipity_query import SerendipityFacet, SerendipitySpec

_ABS = ("Syndromic surveillance systems monitor disease indicators to detect outbreaks early. "
        "We compared aberration detection methods using simulated outbreaks added to baseline "
        "counts and measured sensitivity, specificity and timeliness across the methods under "
        "a range of outbreak sizes and durations in several data streams.")


def _raw(wid: str, title: str, abstract: str, *, doi: str | None = None, cited: int = 0) -> Dict[str, Any]:
    words = {w: [i] for i, w in enumerate(abstract.split())}   # one position per distinct word
    return {"id": wid, "display_name": title, "publication_year": 2008, "doi": doi,
            "cited_by_count": cited, "abstract_inverted_index": words,
            "primary_topic": {"field": {"id": "https://openalex.org/fields/27",
                                        "display_name": "Medicine"}}}


def _abstract(n: int) -> str:
    return " ".join(f"paper{n}term{i}" for i in range(60))


class _Pages:
    def __init__(self, pages: List[List[Dict[str, Any]]]) -> None:
        self.pages, self.calls = pages, 0

    def get(self, params):
        page = self.pages[self.calls] if self.calls < len(self.pages) else []
        self.calls += 1
        return {"results": page}


def _run(monkeypatch, pages, cfg=None):
    client = _Pages(pages)

    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = client
    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)
    theme = ThemeInput(
        theme_overview="o" * 50, goal="g", why_problem="w", approach_type="design",
        assumptions=[], scope=Scope(field="computer science", scale="micro", time_range="no_limit"),
        keywords=Keywords(include=["alpha"], exclude=[]))
    spec = SerendipitySpec("struct", [SerendipityFacet(f"facet{i}", "a" * 40)
                                      for i in range(len(pages))])
    stats: List[Dict[str, Any]] = []
    out = collect_track_b_from_spec(theme, spec, cfg or CollectConfig(), max_count=60,
                                    home_field_ids=["17"], stats_out=stats)
    return out, stats


def _distinct_abstract_text() -> str:
    return " ".join(dict.fromkeys(_ABS.split()))     # the fixture stores one position per word


def _pad(prefix: str, n: int = 3) -> List[Dict[str, Any]]:
    """Unrelated works: a facet with fewer than a handful of results is rejected as too_few."""
    return [_raw(f"{prefix}{i}", f"pad {prefix}{i}", _abstract(900 + ord(prefix[0]) * 10 + i))
            for i in range(n)]


def test_copy_without_doi_is_merged_into_the_journal_record(monkeypatch):
    text = _distinct_abstract_text()
    page = [
        _raw("W2138199368", "Comparing syndromic surveillance detection methods", text,
             doi="https://doi.org/10.1002/sim.3197", cited=120),
        _raw("W1", "another paper", _abstract(1)),
        _raw("W7100698379", "SUMMARY", text),
    ]
    out, stats = _run(monkeypatch, [page])
    assert [w.id for w in out] == ["W2138199368", "W1"]
    assert stats[0]["same_abstract"] == 1 and stats[0]["kept"] == 2
    assert "抄録が同文の別レコード 1 件を統合" in _facet_breakdown_line(stats)


def test_better_record_takes_the_slot_when_the_copy_ranks_first(monkeypatch):
    """The copy can outrank the journal record in the semantic results. The slot keeps its
    position and goes to the record with a DOI and citations."""
    text = _distinct_abstract_text()
    page = [
        _raw("W6926718243", "Constructing TB Care Cascades.pdf", text),
        _raw("W1", "another paper", _abstract(1)),
        _raw("W2918009030", "Constructing care cascades", text,
             doi="https://doi.org/10.1371/journal.pmed.1002754", cited=300),
    ]
    out, _ = _run(monkeypatch, [page])
    assert [w.id for w in out] == ["W2918009030", "W1"]
    assert out[0].source_meta["serendipity_facet"] == "[1] facet0"


def test_merge_reaches_across_facets_and_keeps_the_first_facet(monkeypatch):
    text = _distinct_abstract_text()
    near = [_raw("W10", "journal record", text, doi="https://doi.org/10.1/x", cited=5)] + _pad("N")
    far = [_raw("W20", "DISPATCHES journal record", text),
           _raw("W21", "other", _abstract(2))] + _pad("F")
    out, stats = _run(monkeypatch, [near, far])
    assert sorted(w.id for w in out if w.id.startswith("W")) == ["W10", "W21"]
    assert next(w for w in out if w.id == "W10").source_meta["serendipity_facet"] == "[1] facet0"
    assert [r["same_abstract"] for r in stats] == [0, 1]


def test_distinct_and_short_abstracts_are_never_merged(monkeypatch):
    shared_opening = " ".join(f"common{i}" for i in range(12))       # ~100 chars, below the key
    page = [
        _raw("W1", "paper one", shared_opening + " " + _abstract(1)),
        _raw("W2", "paper two", shared_opening + " " + _abstract(2)),
        _raw("W3", "short a", "a short abstract"),
        _raw("W4", "short b", "a short abstract"),
    ]
    out, stats = _run(monkeypatch, [page])
    assert [w.id for w in out] == ["W1", "W2", "W3", "W4"]
    assert stats[0]["same_abstract"] == 0
    assert _abstract_key("a short abstract") == ""
    assert "統合" not in _facet_breakdown_line(stats)


def test_flag_restores_the_old_behaviour(monkeypatch):
    text = _distinct_abstract_text()
    page = [_raw("W1", "journal record", text, doi="https://doi.org/10.1/x"),
            _raw("W2", "SUMMARY", text)] + _pad("P")
    out, _ = _run(monkeypatch, [page], CollectConfig(same_abstract_dedup=False))
    assert [w.id for w in out][:2] == ["W1", "W2"]
    out, _ = _run(monkeypatch, [page])
    assert [w.id for w in out][:2] == ["W1", "P0"]


def test_leading_abstract_label_does_not_split_the_key():
    """F-63 (survey 2026-10-15 hAIbit): W7100622646 opens "Abstract: Under healthy conditions…"
    with "tech-niques"; the journal record W1824152488 opens "Under healthy conditions…"."""
    body = ("Under healthy conditions, the normal cardiac (sinus) interbeat interval fluctuates in a "
            "complex manner. Quantitative analysis using {t} adapted from statistical physics reveals "
            "the presence of long-range power-law correlations extending over thousands of heartbeats.")
    journal = body.format(t="techniques")
    for label in ("Abstract: ", "ABSTRACT ", "Abstract—", "Summary. "):
        assert _abstract_key(label + body.format(t="tech-niques")) == _abstract_key(journal)
    # a word that merely starts with the label is not a label
    assert _abstract_key("Abstraction " + journal) != _abstract_key(journal)
