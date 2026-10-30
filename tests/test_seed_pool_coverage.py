"""F-73 (seihai 2026-10-29): the seeds at the centre of the question cited 0-1 pooled bridges while two
reference-heavy seeds off to the side cited 18 and 16. Replayed: "Risk inflation of sequential tests"
has 10 references and none in the pool. The line names such seeds; the pool itself is unchanged."""

from __future__ import annotations

from test_bridge_seed_routes import _run, _work

from src.pipeline.bridge_diagnostics import render_seed_pool_coverage, seed_pool_coverage


def test_counts_shared_top_two_and_absent_seeds():
    seeds = [_work("S1", ["A", "B", "C"], "Heavy one"), _work("S2", ["A", "B"], "Heavy two"),
             _work("S3", ["D"], "Light"), _work("S4", ["X", "Y"], "Central"), _work("S5", [], "No refs")]
    cov = seed_pool_coverage(seeds, ["A", "B", "C", "D"])
    assert cov["pool"] == 4 and cov["shared"] == 2
    assert round(cov["top2_share"], 2) == round(5 / 6, 2)
    assert cov["absent"] == [{"title": "Central", "refs": 2}]       # S5 has no references to offer
    line = render_seed_pool_coverage(cov)
    assert "プール 4 本のうち複数シードが共有 2 本・上位 2 シードの寄与 83%" in line
    assert "参照を持つのにプールに 0 本のシード 1 件: 「Central」（参照 2 本）" in line


def test_no_absent_clause_when_every_seed_reaches_the_pool():
    line = render_seed_pool_coverage(seed_pool_coverage([_work("S1", ["A"], "One")], ["A"]))
    assert "シード別の bridge 枠 (F-73)" in line and "0 本のシード" not in line


def test_empty_pool_does_not_divide_by_zero():
    assert seed_pool_coverage([], [])["top2_share"] == 0.0


def test_the_line_reaches_the_output_and_follows_the_diagnostics_switch(monkeypatch):
    assert "シード別の bridge 枠 (F-73)" in _run(monkeypatch, semantic=True)
    assert "シード別の bridge 枠 (F-73)" not in _run(monkeypatch, semantic=True, diagnostics=False)
