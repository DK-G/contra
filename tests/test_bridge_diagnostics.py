"""Tests for the bybridge run diagnostics (F-02: seeds + bridge traffic must be visible)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:   # so `python tests/test_bridge_diagnostics.py` works too
    sys.path.insert(0, str(_REPO_ROOT))

from src.core.models import Work  # noqa: E402
from src.pipeline.bridge_diagnostics import (
    bridge_concentration,
    bridge_usage,
    render_diagnostics,
    resolve_work_labels,
    seed_rows,
    short_id,
)


def _w(wid: str, refs: List[str], title: str = "", cited: int = 0, doi: Optional[str] = None) -> Work:
    return Work(
        id=wid, title=title or wid, year=2021, venue="J", doi=doi, cited_by_count=cited,
        abstract="a", referenced_works=refs,
    )


def test_short_id_strips_the_openalex_url():
    assert short_id("https://openalex.org/W123") == "W123"
    assert short_id("W123") == "W123"
    assert short_id("") == ""
    assert short_id("nonsense") == "nonsense"


def test_seed_rows_expose_the_fields_needed_to_judge_the_seed_search():
    seeds = [_w("S1", ["B1", "B2", "X"], title="Seed one", cited=42, doi="10.1/abc")]
    rows = seed_rows(seeds, {"B1", "B2"})
    assert len(rows) == 1
    r = rows[0]
    assert (r.title, r.cited_by_count, r.doi, r.year, r.venue) == ("Seed one", 42, "10.1/abc", 2021, "J")
    assert r.bridge_contribution == 2   # B1/B2 are in the pool, X is not


def test_bridge_usage_counts_seed_and_candidate_traffic_and_sorts_busiest_first():
    bridges = {"B1", "B2", "B3"}
    seeds = [_w("S1", ["B1", "B2"]), _w("S2", ["B1"])]
    cands = [_w("C1", ["B1"]), _w("C2", ["B1"]), _w("C3", ["B2"])]
    usage = {u.id: u for u in bridge_usage(seeds, cands, bridges)}
    assert (usage["B1"].seed_citers, usage["B1"].candidate_citers) == (2, 2)
    assert (usage["B2"].seed_citers, usage["B2"].candidate_citers) == (1, 1)
    # B3 was in the pool but carried no traffic — still reported, so unused pool size is visible.
    assert (usage["B3"].seed_citers, usage["B3"].candidate_citers) == (0, 0)
    assert [u.id for u in bridge_usage(seeds, cands, bridges)][0] == "B1"


def test_bridge_concentration_measures_collapse_onto_one_hub():
    bridges = {"HUB", "B2"}
    cands = [_w(f"C{i}", ["HUB"]) for i in range(9)] + [_w("C9", ["B2"])]
    conc = bridge_concentration(cands, bridges, top_n=10)
    assert conc.candidates == 10
    assert conc.top_bridge_id == "HUB"
    assert conc.top_bridge_share == 0.9
    assert conc.single_bridge_candidates == 10     # every candidate hangs off exactly one bridge
    assert conc.mean_shared_bridges == 1.0
    assert conc.distinct_bridges_used == 2


def test_bridge_concentration_top_n_uses_the_displayed_order():
    bridges = {"HUB", "B2"}
    hub = [_w(f"H{i}", ["HUB"]) for i in range(5)]
    other = [_w(f"O{i}", ["B2"]) for i in range(5)]
    # Ranked head is all-hub even though the overall split is 50/50 — the head is what the
    # caller sees, and that is the number F-01 kept reporting by hand.
    conc = bridge_concentration(hub + other, bridges, top_n=5, ranked=hub + other)
    assert conc.top_n_share == 1.0
    assert conc.top_bridge_share == 0.5


def test_bridge_concentration_is_safe_on_empty_input():
    assert bridge_concentration([], {"B1"}).candidates == 0
    assert bridge_concentration([_w("C1", [])], set()).top_bridge_id == ""
    assert bridge_concentration([_w("C1", ["X"])], {"B1"}).distinct_bridges_used == 0


class _FakeClient:
    def __init__(self, results, boom=False):
        self.results = results
        self.boom = boom
        self.calls = []

    def get(self, params):
        self.calls.append(params)
        if self.boom:
            raise RuntimeError("network down")
        return {"results": self.results}


def test_resolve_work_labels_batches_into_one_call_and_keys_on_short_ids():
    client = _FakeClient([
        {"id": "https://openalex.org/W1", "display_name": "Hub paper", "cited_by_count": 43317},
    ])
    labels = resolve_work_labels(["https://openalex.org/W1", "W1", "W2"], client)
    assert len(client.calls) == 1                       # one call for the whole batch
    assert client.calls[0]["filter"] == "ids.openalex:W1|W2"   # deduped
    assert labels["W1"]["title"] == "Hub paper"
    assert labels["W1"]["cited_by_count"] == 43317


def test_resolve_work_labels_fails_soft():
    assert resolve_work_labels(["W1"], _FakeClient([], boom=True)) == {}
    assert resolve_work_labels([], _FakeClient([])) == {}


def test_render_diagnostics_shows_every_seed_and_the_busiest_bridge():
    bridges = {"HUB", "B2"}
    seeds = [_w("S1", ["HUB", "B2"], title="Seed one", cited=7, doi="10.1/s1"),
             _w("S2", ["HUB"], title="Seed two", cited=3)]
    cands = [_w("C1", ["HUB"], title="Cand one"), _w("C2", ["HUB"], title="Cand two")]
    out = render_diagnostics(
        seeds, cands, bridges, ranked=cands,
        labels={"HUB": {"title": "A universally cited hub", "cited_by_count": 43317}},
    )
    assert "シード 2 件" in out and "交差候補 2 件" in out
    assert "Seed one" in out and "Seed two" in out     # F-02: the seeds are in the output
    assert "10.1/s1" in out                            # DOI when present
    assert "S2" in out                                 # falls back to the work id without a DOI
    assert "A universally cited hub" in out            # the hub is named, not just id'd
    assert "43,317" in out                             # ...and its citation count is visible
    assert "100%" in out                               # concentration meter fired


def test_render_diagnostics_truncates_long_seed_lists_but_says_so():
    seeds = [_w(f"S{i}", ["B1"], title=f"Seed {i}") for i in range(35)]
    out = render_diagnostics(seeds, [_w("C1", ["B1"])], {"B1"}, seed_limit=30)
    assert "…他 5 件" in out
    assert "Seed 29" in out and "Seed 30" not in out


def test_render_diagnostics_survives_zero_candidates():
    seeds = [_w("S1", ["B1"], title="Seed one")]
    out = render_diagnostics(seeds, [], {"B1"})
    assert "Seed one" in out                           # seeds still visible on an empty result
    assert "交差候補 0 件" in out


def _run() -> None:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    _run()
