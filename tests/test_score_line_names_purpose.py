"""F-70: the serendipity score line names its second factor as purpose_sim, not "構造".

Survey 2026-10-24 (salon-sites) and 2026-10-26 (metagmo): "セレンディピティ・スコア: 0.5（距離 0.86 ×
構造 0.58）" — the 0.58 was the submitted purpose_sim, while the candidate's structural_depth (the
judge's Gentner score, which the playbook calls "構造") was 0.66. Readers took one for the other.
"""

from __future__ import annotations

from src.mcp_server import StdinMcpServer


def _cand(wid: str, purpose: float, depth) -> dict:
    c = {
        "id": wid, "title": f"Paper {wid}", "abstract": "abstract text " * 4, "year": 2006,
        "venue": "Journal", "cited_by_count": 10,
        "purpose_sim": purpose, "mechanism_dist": 0.86,
        "has_causal_pm": True, "connection_label": "label",
    }
    if depth is not None:
        c["structural_depth"] = depth
    return c


def _finalize(depth) -> str:
    res = StdinMcpServer().handle_tool_call("delegate_finalize", {
        "theme_overview": "探索の打ち切り規則を設計する。" * 20,
        "goal": "決着しない側の打ち切り規則", "why_problem": "枠が有限であるため",
        "approach_type": "application", "assumptions": ["打ち切りは推定量を歪める", "一律は最適でない"],
        "scope_field": "Computer Science", "scope_scale": "small", "scope_time_range": "no_limit",
        "count": 1, "no_history": True, "grounded_only": False,
        "candidates": [_cand("W1", 0.58, depth)] + [_cand(f"W{i}", 0.4, depth) for i in range(2, 9)],
    })
    return res["content"][0]["text"]


def test_second_factor_is_named_purpose_sim_and_depth_is_shown_apart():
    text = _finalize(0.66)
    assert "× 目的の一致 0.58＝purpose_sim）" in text
    assert "／構造の深さ 0.66（structural_depth・hollow ゲートにだけ使い、点数には入らない）" in text
    assert "× 構造 0.58" not in text


def test_depth_is_omitted_when_the_judge_did_not_score_it():
    text = _finalize(None)
    assert "× 目的の一致 0.58＝purpose_sim）" in text
    assert "構造の深さ" not in text


if __name__ == "__main__":
    test_second_factor_is_named_purpose_sim_and_depth_is_shown_apart()
    test_depth_is_omitted_when_the_judge_did_not_score_it()
    print("ok")
