"""F-85 instrument (2026-11-13): each bybridge candidate carries the citation size of the
smallest and largest bridge it routes through, and the diagnostics count candidates by the
smallest one. Sizes ride on the liveness call (select=id,cited_by_count) — no extra request."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.models import Work
from src.pipeline.bridge_diagnostics import (
    candidate_bridge_sizes,
    filter_live_bridges,
    render_bridge_size_tiers,
)

FULL = "https://openalex.org/{}"


class SizedClient:
    def __init__(self, sizes):
        self.sizes = sizes
        self.calls = []

    def get(self, params):
        self.calls.append(params)
        asked = params["filter"].split(":", 1)[1].split("|")
        return {"results": [{"id": FULL.format(i), "cited_by_count": self.sizes[i]}
                            for i in asked if i in self.sizes]}


def _w(wid, refs):
    return Work(id=FULL.format(wid), title=wid, year=2000, venue="", doi=None, cited_by_count=0,
                abstract="", referenced_works=[FULL.format(r) for r in refs])


def test_liveness_call_also_returns_sizes_in_one_request():
    # sizes measured 2026-11-13 (seihai r05 bridge table): Sharpe 1964 20,270 / Jensen 1968 5,523
    client = SizedClient({"W2029056003": 20270, "W3122187992": 5523})
    cited = {}
    live, dead = filter_live_bridges(
        [FULL.format("W2029056003"), FULL.format("W3122187992"), FULL.format("W9")],
        client, cited_out=cited)
    assert len(client.calls) == 1
    assert client.calls[0]["select"] == "id,cited_by_count"
    assert cited == {"W2029056003": 20270, "W3122187992": 5523}
    assert dead == ["W9"]


def test_without_cited_out_the_call_is_unchanged():
    client = SizedClient({"W1": 10})
    filter_live_bridges([FULL.format("W1")], client)
    assert client.calls[0]["select"] == "id"


def test_candidate_sizes_and_tiers():
    bridges = [FULL.format(b) for b in ("W1", "W2", "W3")]
    cited = {"W1": 20270, "W2": 5523, "W3": 300}
    only_giant = _w("WA", ["W1", "W99"])          # W99 is not a pool bridge
    giant_and_small = _w("WB", ["W1", "W3"])
    unknown = _w("WC", ["W77"])
    assert candidate_bridge_sizes(only_giant, bridges, cited) == (20270, 20270)
    assert candidate_bridge_sizes(giant_and_small, bridges, cited) == (300, 20270)
    assert candidate_bridge_sizes(unknown, bridges, cited) is None
    line = render_bridge_size_tiers([only_giant, giant_and_small, unknown], bridges, cited)
    assert "2万以上 1 件" in line and "千未満 1 件" in line and "不明 1 件" in line
    assert render_bridge_size_tiers([only_giant], bridges, {}) == ""
