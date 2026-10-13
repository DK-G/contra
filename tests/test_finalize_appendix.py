"""F-54 (rest): the delegated report's heading and appendix say what finalize actually knows.

Survey 2026-10-10 and 2026-10-12: the appendix read "取得日: TBD / 検索条件: TBD / フィルタ条件: TBD",
the heading was the home field's name ("# Computer Science contra 視座拡張レポート"), and the summary
said "時代: last_10_years" above three papers from 2006, 2015 and 1990 (F-51).
"""

from __future__ import annotations

from datetime import date

from src.mcp_server import StdinMcpServer


def _cand(wid: str, purpose: float, mech: float) -> dict:
    return {
        "id": wid, "title": f"Paper {wid}", "abstract": "abstract text " * 4, "year": 2006,
        "venue": "Journal", "cited_by_count": 10,
        "purpose_sim": purpose, "mechanism_dist": mech, "structural_depth": 0.7,
        "has_causal_pm": True, "connection_label": "label",
    }


def _finalize(time_range: str) -> str:
    res = StdinMcpServer().handle_tool_call("delegate_finalize", {
        "theme_overview": "探索の打ち切り規則を設計する。" * 20,
        "goal": "決着しない側の打ち切り規則", "why_problem": "枠が有限であるため",
        "approach_type": "application", "assumptions": ["打ち切りは推定量を歪める", "一律は最適でない"],
        "scope_field": "Computer Science", "scope_scale": "small", "scope_time_range": time_range,
        "count": 2, "no_history": True, "grounded_only": False,
        "candidates": [_cand(f"W{i}", 0.5 + i / 50, 0.8) for i in range(12)],
    })
    return res["content"][0]["text"]


def test_appendix_states_the_run_date_the_gates_and_that_finalize_did_not_search():
    text = _finalize("no_limit")
    assert "TBD" not in text
    assert f"- 取得日: {date.today().isoformat()}（delegate_finalize の実行日" in text
    assert "- 検索条件: delegate_finalize は検索しない" in text
    assert "- フィルタ条件: 決定論 post-gate（LLM なし）: 提出 12 件" in text
    assert "output_floor 0.35" in text and "出力 2 件（count 2・接地契約 なし" in text


def test_heading_names_the_field_as_the_home_field_not_as_the_subject():
    text = _finalize("no_limit")
    assert "# contra 視座拡張レポート（ホーム分野: Computer Science）" in text
    assert "# Computer Science contra 視座拡張レポート" not in text


def test_time_range_line_says_it_is_recorded_only_unless_no_limit():
    assert "時代: last_10_years（記録のみ。by* は出版年で絞らない" in _finalize("last_10_years")
    assert "  - 時代: no_limit\n" in _finalize("no_limit").replace("\r\n", "\n")
