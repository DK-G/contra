"""F-72 (survey 10-15 hAIbit, 10-24 salon-sites, 10-26 metagmo): Figshare files each supplement of a
paper as its own work with publication_type article, so "Additional file 3: of Visualizing sound…"
took a candidate slot. The title names the paper it belongs to, so the breakdown says which."""

from __future__ import annotations

import pytest
from test_same_abstract_dedup import _abstract, _raw, _run

from src.mcp_server import _facet_breakdown_line
from src.pipeline.collect import CollectConfig, is_supplement_title


@pytest.mark.parametrize("title", [
    "Additional file 1 of Impact of adaptive filtering on power and false discovery rate",
    "Additional file 3: of Visualizing sound: counting wolves by using a spectral view",
    "Figure S1 from Pausing to swarm: locust intermittent motion",
    "Table S1 from Noisy communities and signal detection",
    "Supplementary Material for A study of signals",
    "Supplementary Table 2 of A study of signals",
    "Movie S2 of A study of signals",
    "MOESM5 of Testing the Coulomb stress triggering hypothesis for three recent megathrust earthquakes",
    "13059_2017_1234_MOESM1_ESM of A study of signals",
])
def test_supplement_titles_match(title):
    assert is_supplement_title(title)


@pytest.mark.parametrize("title", [
    "Tables of critical values for two group interim analyses",
    "Data from: Do aggressive signals evolve toward higher reliability",
    "Supplementary motor area of the brain",
    "Figure 8 knots from braids",
    "Figure-ground segregation of objects",
    "Video games from the 80s",
    "MOESM of signals",
    "",
    None,
])
def test_other_titles_do_not_match(title):
    assert not is_supplement_title(title)


def _page():
    return [_raw("W1", "Additional file 3: of Visualizing sound: counting wolves", _abstract(1)),
            _raw("W2", "Visualizing sound: counting wolves", _abstract(2)),
            _raw("W3", "Table S1 from Noisy communities", _abstract(3))]


def test_supplements_take_no_slot_and_are_named(monkeypatch):
    out, stats = _run(monkeypatch, [_page()])
    assert [w.id for w in out] == ["W2"]
    assert stats[0]["supplement_excluded"] == 2
    assert stats[0]["kept"] == 1
    line = _facet_breakdown_line(stats)
    assert "補足資料のレコード 2 件を除外: W1「Additional file 3: of Visualizing sound" in line
    assert "W3「Table S1 from Noisy communities」" in line


def test_flag_keeps_them(monkeypatch):
    out, stats = _run(monkeypatch, [_page()], CollectConfig(supplement_title_exclusion=False))
    assert [w.id for w in out] == ["W1", "W2", "W3"]
    assert "補足資料" not in _facet_breakdown_line(stats)
