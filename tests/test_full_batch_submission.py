"""F-15-U: the percentile gate needs the full scored pool, so make full submission cheap to read.

(1) In a thin batch the bar is the k-th best score (k=1 up to 6 candidates), and finalize says so.
(2) Candidates sent as id + scores only, and not rendered, are one summary line instead of one
    warning each; they still count in the percentile pool. One that does render keeps its
    F-09 warning, because it renders blank.
"""

from __future__ import annotations

from src.pipeline.classify import _percentile_rank, apply_post_gates
from src.pipeline.delegate import (
    echo_completeness_warnings,
    normalize_agent_scores,
    score_only_ids,
    score_only_summary,
)


def _full(wid: str, purpose: float, mech: float) -> dict:
    return {
        "id": wid, "title": f"Paper {wid}", "abstract": "abstract text " * 4, "year": 2020,
        "venue": "Journal", "cited_by_count": 10,
        "purpose_sim": purpose, "mechanism_dist": mech, "structural_depth": 0.7,
        "has_causal_pm": True, "connection_label": "label", "serendipity_rationale": "why",
    }


def _bare(wid: str, purpose: float, mech: float) -> dict:
    return {"id": wid, "purpose_sim": purpose, "mechanism_dist": mech, "structural_depth": 0.7}


def _finalize(cands, count=3):
    from src.mcp_server import StdinMcpServer
    res = StdinMcpServer().handle_tool_call("delegate_finalize", {
        "theme_overview": "探索の打ち切り規則を設計する。" * 20,
        "goal": "決着しない側の打ち切り規則", "why_problem": "枠が有限であるため",
        "approach_type": "application", "assumptions": ["打ち切りは推定量を歪める", "一律は最適でない"],
        "scope_field": "statistics", "scope_scale": "small", "scope_time_range": "no_limit",
        "count": count, "no_history": True, "grounded_only": False, "candidates": cands,
    })
    return res["content"][0]["text"]


# --- (1) thin batch --------------------------------------------------------------------

def test_percentile_rank_is_the_best_score_up_to_six_candidates():
    assert [_percentile_rank(n) for n in (1, 3, 6, 7, 9, 10, 40)] == [1, 1, 1, 2, 2, 3, 12]


def test_diag_carries_the_rank_behind_the_bar():
    def run(n):
        mats = [_full(f"W{i}", 0.5 + i / 100, 0.8) for i in range(n)]
        works, scores, _ = normalize_agent_scores(mats)
        diag: dict = {}
        apply_post_gates(scores, works, count=n, diag=diag, gate=0.2)
        return diag
    assert run(5)["percentile_rank"] == 1
    assert run(12)["percentile_rank"] == 3


def test_finalize_names_a_thin_batch_and_the_remedy():
    text = _finalize([_full(f"W{i}", 0.6 + i / 100, 0.8) for i in range(5)])
    assert "分位の母数が 5 件" in text and "上位 1 件を通すだけ" in text
    assert "全件提出" in text


def test_finalize_is_quiet_about_a_full_batch():
    text = _finalize([_full(f"W{i}", 0.5 + i / 100, 0.8) for i in range(12)])
    assert "分位の母数が" not in text


# --- (2) score-only candidates ---------------------------------------------------------

def test_score_only_means_neither_title_nor_abstract_was_echoed():
    assert score_only_ids([_bare("B1", 0.5, 0.8)]) == {"B1"}
    assert score_only_ids([_full("F1", 0.5, 0.8)]) == set()
    blank = _bare("B2", 0.5, 0.8)
    blank["title"] = ""                  # echoed present-but-blank: a faithful empty source
    assert score_only_ids([blank]) == set()
    marked = dict(_bare("B3", 0.5, 0.8), upstream_empty=["title", "abstract"])
    assert score_only_ids([marked]) == set()


def test_unrendered_score_only_is_summarised_not_warned_one_by_one():
    mats = [_full("F1", 0.8, 0.8), _bare("B1", 0.5, 0.8), _bare("B2", 0.4, 0.8)]
    assert echo_completeness_warnings(mats, rendered_ids={"F1"}) == []
    assert "2 件" in (score_only_summary(mats, {"F1"}) or "")
    # without rendered_ids the F-09 behaviour is unchanged: every omission is named
    assert len(echo_completeness_warnings(mats)) == 2


def test_finalize_counts_score_only_in_the_pool_and_summarises_them():
    cands = [_full("F1", 0.85, 0.85), _full("F2", 0.8, 0.85)]
    cands += [_bare(f"B{i}", 0.4 + i / 100, 0.8) for i in range(8)]
    text = _finalize(cands, count=2)
    assert "提出 10 件の上位30%点" in text                 # the bare ones are in the pool
    assert "材料欄が欠けたまま" not in text
    assert "点数だけで送られた候補 8 件" in text
    assert "点数だけの候補: " in text and "B3" not in text   # counted per floor, not listed
    # B7 (0.376) is the 3rd best of 10 = the bar itself, so it clears every gate and only
    # loses to count=2: that one is named, because it is worth re-sending with material.
    assert "B7" in text and "not_selected(count=2)" in text


def test_score_only_that_reaches_the_output_keeps_its_warning():
    cands = [_bare("TOP", 0.9, 0.9), _full("F1", 0.5, 0.8), _full("F2", 0.45, 0.8)]
    text = _finalize(cands, count=3)
    assert "TOP" in text and "材料欄が欠けたまま" in text
