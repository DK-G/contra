"""F-10: the judge's has_causal_pm verdict must be reflected in the numeric grade.

Observed 2026-08-21 (field_observations_seihai.md F-10): a candidate labelled
"構造対応ゆるめ" (has_causal_pm=False) still carried purpose_sim 0.70 = the "strong"
level — the prose caveat and the numeric grade contradicted each other. The cap
lowers such candidates to the "partial" level (0.45) and rescales serendipity by
the same factor so score and rank stay mutually consistent.
"""

from __future__ import annotations

from src.pipeline.classify import _PURPOSE_LEVELS, _apply_causal_cap


def _row(ser: float, wid: str, purpose: float, causal) -> tuple:
    s = {"purpose_sim": purpose, "mechanism_dist": ser / purpose if purpose else 0.0}
    if causal is not None:
        s["has_causal_pm"] = causal
    return (ser, wid, s)


def test_loose_causal_strong_grade_is_capped_to_partial():
    # The exact observed shape: 0.56 = 0.80 (dist) x 0.70 (strong) with the loose label.
    out = _apply_causal_cap([_row(0.56, "W1", 0.70, False)])
    ser, _wid, s = out[0]
    assert s["purpose_sim"] == _PURPOSE_LEVELS["partial"]          # 0.70 -> 0.45
    assert s["purpose_sim_uncapped"] == 0.70                       # kept for diagnostics
    assert abs(ser - 0.80 * 0.45) < 1e-9                           # product rescaled consistently


def test_causal_true_is_untouched():
    out = _apply_causal_cap([_row(0.56, "W1", 0.70, True)])
    ser, _wid, s = out[0]
    assert s["purpose_sim"] == 0.70 and ser == 0.56
    assert "purpose_sim_uncapped" not in s


def test_unjudged_is_untouched():
    # Fail-open: no judge verdict -> no cap (same spirit as the hollow filter).
    out = _apply_causal_cap([_row(0.56, "W1", 0.70, None)])
    assert out[0][0] == 0.56 and out[0][2]["purpose_sim"] == 0.70


def test_loose_causal_at_or_below_partial_is_untouched():
    out = _apply_causal_cap([_row(0.36, "W1", 0.45, False)])
    assert out[0][0] == 0.36 and out[0][2]["purpose_sim"] == 0.45


def test_capped_candidate_ranks_below_tight_candidate():
    # The point of F-10: a loose analogy must no longer tie with a tight one.
    loose = _row(0.56, "LOOSE", 0.70, False)
    tight = _row(0.56, "TIGHT", 0.70, True)
    out = sorted(_apply_causal_cap([loose, tight]), reverse=True)
    assert [wid for _s, wid, _d in out] == ["TIGHT", "LOOSE"]


# --- F-31: the cap must be SHOWN, not only applied ----------------------------------------
# Observed 2026-09-22 (seihai r02): the caller sent purpose_sim 0.58 with has_causal_pm=false
# for W2804218996 and the rejection breakdown printed 0.45 with no rule named — the caller's
# own score changed silently (the F-09 "silent degradation" family).

def test_cap_is_recorded_in_diag():
    diag = {}
    _apply_causal_cap([_row(0.58 * 0.6, "W2804218996", 0.58, False),
                       _row(0.5, "W_OK", 0.70, True)], diag)
    assert diag["purpose_caps"] == [{
        "id": "W2804218996", "submitted": 0.58, "capped": 0.45,
        "rule": "has_causal_pm=false -> partial (F-10)",
    }]


def test_no_cap_leaves_diag_without_the_key():
    diag = {}
    _apply_causal_cap([_row(0.5, "W_OK", 0.70, True)], diag)
    assert "purpose_caps" not in diag


def test_rejection_cause_carries_the_submitted_value():
    from src.pipeline.classify import _serendipity_cause
    assert _serendipity_cause(0.45, 0.6, 0.58)["purpose_sim_submitted"] == 0.58
    assert "purpose_sim_submitted" not in _serendipity_cause(0.45, 0.6, None)
    assert "purpose_sim_submitted" not in _serendipity_cause(0.45, 0.6, 0.45)


def test_delegate_finalize_names_the_rewrite_end_to_end():
    """The 9/22 shape through the MCP handler: 6 candidates, one loose one sent at 0.58."""
    from src.mcp_server import StdinMcpServer

    def cand(wid, purpose, mech, causal=True):
        return {"id": wid, "title": f"Paper {wid}", "abstract": "a" * 40, "year": 2018,
                "venue": "V", "cited_by_count": 10, "purpose_sim": purpose,
                "mechanism_dist": mech, "structural_depth": 0.55 if not causal else 0.7,
                "has_causal_pm": causal, "connection_label": "閾値", "serendipity_rationale": "r"}

    cands = [cand("W2804218996", 0.58, 0.80, causal=False),
             cand("A", 0.80, 0.85), cand("B", 0.75, 0.80), cand("C", 0.70, 0.60),
             cand("D", 0.60, 0.70), cand("E", 0.65, 0.75)]
    res = StdinMcpServer().handle_tool_call("delegate_finalize", {
        "theme_overview": "再点火 churn を遷移条件で避ける規則を設計する。" * 20,
        "goal": "churn の抑制", "why_problem": "回転課金が大きいため",
        "approach_type": "application", "assumptions": ["水準述語は再点火する", "課金は線形"],
        "scope_field": "finance", "scope_scale": "small", "scope_time_range": "no_limit",
        "count": 1, "no_history": True, "grounded_only": False, "candidates": cands,
    })
    text = res["content"][0]["text"]
    assert "採点の書き換え (F-10 上限・F-31)" in text
    assert "W2804218996「Paper W2804218996」: purpose_sim 0.58 → 0.45" in text
    # the rejection row for the capped candidate says what was sent before the cap
    assert "purpose_sim 0.45［送信値 0.58 を F-10 上限で抑制］" in text
    # untouched candidates are not listed as rewritten
    assert "- A「Paper A」: purpose_sim" not in text
