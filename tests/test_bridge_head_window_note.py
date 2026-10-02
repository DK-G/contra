"""F-25-L: the bybridge head-window label states what was measured.

The materials path printed "上位窓多様化済み" and the raw path "bridge ごとの偏りを抑えて並べ替え
済み" on every run. seihai 2026-10-02: that label sat beside "最頻 bridge が上位 10 件の 70%"
(3.47 bridges per candidate). The shares below are the ones seihai recorded: 09-29 20%,
10-01 30%, 10-02 70%.
"""

from __future__ import annotations

import pytest

import src.mcp_server as mcp_mod
from src.core.models import Work
from src.pipeline.bridge_diagnostics import BridgeConcentration, bridge_concentration, head_window_note
from src.pipeline.bridges import diversify_head_by_bridge


def _conc(head_share: float, mean: float) -> BridgeConcentration:
    return BridgeConcentration(candidates=60, top_bridge_id="B", top_bridge_share=0.4, top_n=10,
                               top_n_share=head_share, mean_shared_bridges=mean)


def test_observed_2026_10_02_is_not_called_diversified():
    note = head_window_note(_conc(0.70, 3.47))
    assert "上位 10 件の 70% を占める＝上位窓は多様化していない" in note
    assert "平均 3.47 本" in note and "F-25" in note
    assert "並べ替え済み" not in note


def test_observed_2026_10_01_thirty_percent_exceeds_the_quota():
    assert "多様化していない" in head_window_note(_conc(0.30, 2.27))


def test_share_within_the_quota_is_reported_as_done_with_its_number():
    # 09-29: 20% = exactly the 2-of-10 quota.
    note = head_window_note(_conc(0.20, 1.9))
    assert note == "上位 10 件を 1 bridge あたり 2 件までの枠で並べ替え済み・最頻 bridge の占有 20%"


def test_no_candidates_makes_no_claim():
    assert head_window_note(BridgeConcentration()) == "上位窓の並べ替えは対象なし"


def _work(wid: str, refs) -> Work:
    return Work(id=wid, title=wid, year=2024, venue="v", doi=None, cited_by_count=0,
                abstract="a", referenced_works=list(refs))


def test_multi_bridge_candidates_defeat_the_quota_and_the_note_says_so():
    # F-25's mechanism through the real functions: every candidate cites the hub AND a small
    # bridge of its own, so some cited bridge always has room and the hub is never capped.
    bridges = ["HUB"] + [f"X{i}" for i in range(12)]
    ranked = [_work(f"C{i}", ["HUB", f"X{i}"]) for i in range(12)]
    ordered = diversify_head_by_bridge(ranked, bridges)
    note = head_window_note(bridge_concentration(ranked, bridges, ranked=ordered))
    assert "100% を占める＝上位窓は多様化していない" in note and "平均 2.00 本" in note


def test_single_bridge_pool_is_explained_as_backfill_not_as_f25():
    bridges = ["B1"]
    ranked = [_work(f"C{i}", ["B1"]) for i in range(12)]
    ordered = diversify_head_by_bridge(ranked, bridges)
    note = head_window_note(bridge_concentration(ranked, bridges, ranked=ordered))
    assert "100%" in note and "埋め戻した" in note and "F-25" not in note


# --- MCP wiring ---------------------------------------------------------------------------

@pytest.fixture
def bridge_offline(monkeypatch):
    monkeypatch.setattr(mcp_mod, "resolve_work_labels", lambda *a, **k: {})
    monkeypatch.setattr(mcp_mod, "filter_live_bridges", lambda b, *a, **k: (set(b), []))
    monkeypatch.setattr(mcp_mod, "collect_seeds_semantic_report", lambda *a, **k: ([], None))
    from src.openalex import client as _client
    _client.reset_run_stats()


def _run(monkeypatch, **extra) -> str:
    seeds = [_work("S1", ["HUB"] + [f"X{i}" for i in range(12)]),
             _work("S2", ["HUB"] + [f"X{i}" for i in range(12)])]
    cands = [_work(f"C{i:02d}", ["HUB", f"X{i}"]) for i in range(12)]
    monkeypatch.setattr(mcp_mod, "collect_and_filter", lambda *a, **k: seeds)
    monkeypatch.setattr(mcp_mod, "collect_citation_candidates", lambda *a, **k: cands)
    res = mcp_mod.StdinMcpServer().handle_tool_call("bybridge_collect", {
        "theme_overview": "t" * 200, "goal": "g", "why_problem": "w",
        "approach_type": "application", "assumptions": ["a", "b"], "scope_field": "medicine",
        "no_history": True, "min_seeds": 0, "seed_count": 2, "bridge_count": 3, **extra,
    })
    return res["content"][0]["text"]


def test_materials_instruction_carries_the_measured_note(monkeypatch, bridge_offline):
    text = _run(monkeypatch, materials=True)
    assert "上位窓多様化済み" not in text
    assert "100% を占める＝上位窓は多様化していない" in text.split("\n", 1)[0]


def test_raw_header_carries_the_measured_note(monkeypatch, bridge_offline):
    text = _run(monkeypatch, raw_only=True)
    assert "偏りを抑えて並べ替え済み" not in text
    assert "100% を占める＝上位窓は多様化していない" in text
