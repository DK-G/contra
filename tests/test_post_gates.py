"""Tests for the deterministic post-gates (delegation stage b, no LLM)."""

from __future__ import annotations

from src.core.models import Concept, Work
from src.pipeline.classify import apply_post_gates
from src.pipeline.concept_distance import ThemeProfile


def _work(wid: str, l01_names=()) -> Work:
    return Work(
        id=wid,
        title=f"paper {wid}",
        year=2024,
        venue="Journal",
        doi=None,
        cited_by_count=1,
        abstract="abstract",
        concept_tags=[Concept(name=n, level=1, score=0.5) for n in l01_names],
    )


def _row(purpose_sim, mechanism_dist, *, structural_depth=0.8, has_causal_pm=True, label="接続"):
    return {
        "purpose_sim": purpose_sim,
        "mechanism_dist": mechanism_dist,
        "structural_depth": structural_depth,
        "has_causal_pm": has_causal_pm,
        "connection_label": label,
        "serendipity_rationale": "rationale",
    }


def test_strong_candidate_passes():
    works = {"W": _work("W")}
    scores = {"W": _row(0.7, 0.8)}  # serendipity = 0.56 >= output_floor 0.35
    diag = {}
    out = apply_post_gates(scores, works, count=1, diag=diag)
    assert len(out) == 1
    assert out[0].serendipity_score == 0.56
    assert out[0].distance_score == 0.8
    assert out[0].structure_score == 0.7
    assert diag["status"] == "ok"


def test_anomaly_rejected():
    works = {"W": _work("W")}
    scores = {"W": _row(0.1, 0.9)}  # purpose_sim < 0.20 -> anomaly
    diag = {}
    out = apply_post_gates(scores, works, diag=diag)
    assert out == []
    assert diag["reason"] == "all_anomaly"
    assert diag["anomaly"] == 1


def test_hollow_rejected():
    works = {"W": _work("W")}
    scores = {"W": _row(0.7, 0.8, structural_depth=0.2)}  # below struct_depth_gate 0.50
    diag = {}
    out = apply_post_gates(scores, works, diag=diag)
    assert out == []
    assert diag["reason"] == "all_hollow"
    assert diag["hollow"] == 1


def test_near_domain_caps_mechanism_distance():
    # Work shares the theme's broad domain -> mechanism_dist capped at 0.5.
    profile = ThemeProfile(l01={"X"})
    works = {"W": _work("W", l01_names=["X"])}
    scores = {"W": _row(0.7, 0.9)}  # uncapped ser=0.63; capped ser=0.7*0.5=0.35
    out = apply_post_gates(scores, works, theme_profile=profile, count=1)
    assert len(out) == 1
    assert out[0].distance_score == 0.5
    assert out[0].serendipity_score == 0.35


def test_fallback_vs_saturation_below_output_floor():
    works = {"W": _work("W")}
    scores = {"W": _row(0.5, 0.4)}  # ser=0.20 < output_floor 0.35 but >= fallback floor 0.10
    # emit_fallback on -> single best with (fallback) marker
    out = apply_post_gates(scores, works, emit_fallback=True)
    assert len(out) == 1
    assert "fallback" in out[0].label
    # emit_fallback off -> saturated, nothing emitted (M3)
    diag = {}
    out2 = apply_post_gates(scores, works, emit_fallback=False, diag=diag)
    assert out2 == []
    assert diag["reason"] == "no_qualified"


def test_loose_causal_link_surfaced_not_rejected():
    works = {"W": _work("W")}
    scores = {"W": _row(0.7, 0.8, has_causal_pm=False)}  # kept, flagged as thought-seed
    out = apply_post_gates(scores, works, count=1)
    assert len(out) == 1
    assert "ゆるめ" in out[0].label


# --- F-22: a rejection row must say WHICH factor was binding -----------------------------
# Observed 6 times. serendipity = purpose_sim x mechanism_dist, so a candidate that is useful
# BECAUSE it is close cannot clear the gate at any threshold; the caller could not tell that
# from the product alone. Calibrated on the 2026-09-12 seihai batch: the three papers the
# caller called "this week's most practical" are exactly the high-purpose / low-distance ones.

def _rejections(diag, wid):
    return [r for r in diag.get("rejections", []) if r["id"] == wid]


def test_rejection_rows_carry_both_factors_and_the_binding_one():
    works = {w: _work(w) for w in ("NEAR", "FAR", "PASS")}
    scores = {
        "NEAR": _row(0.89, 0.50),   # 0.445 — the 2026-09-12 "Quantifying the bias" case
        "FAR": _row(0.64, 0.881),   # 0.564 — far but shallow purpose
        "PASS": _row(0.71, 0.86),   # 0.61  — the one that passed that day
    }
    diag = {}
    apply_post_gates(scores, works, count=1, diag=diag)
    near = _rejections(diag, "NEAR")[0]
    assert near["purpose_sim"] == 0.89 and near["mechanism_dist"] == 0.5
    assert near["binding"] == "mechanism_dist" and near.get("near_but_useful") is True
    far = _rejections(diag, "FAR")[0]
    assert far["binding"] == "purpose_sim" and "near_but_useful" not in far


def test_near_but_useful_is_not_claimed_for_low_purpose_candidates():
    """The label means "useful but close", so it must not fire on a weak-purpose candidate
    that merely happens to be closer than it is aligned."""
    from src.pipeline.classify import _serendipity_cause
    assert _serendipity_cause(0.69, 0.40).get("near_but_useful") is None
    assert _serendipity_cause(0.70, 0.40).get("near_but_useful") is True
    assert _serendipity_cause(0.83, 0.505).get("near_but_useful") is True   # 9/12 W1
    assert _serendipity_cause(0.66, 0.827).get("binding") == "purpose_sim"  # 9/12 W4
    assert _serendipity_cause(None, 0.5) == {}


def test_delegate_finalize_names_near_but_useful_rejects():
    from src.mcp_server import StdinMcpServer
    cands = [
        {"id": "W1", "title": "Futility stopping in clinical trials", "abstract": "a" * 40,
         "year": 2012, "venue": "V", "cited_by_count": 10,
         "purpose_sim": 0.83, "mechanism_dist": 0.505, "structural_depth": 0.7,
         "has_causal_pm": True, "connection_label": "逐次打ち切り",
         "serendipity_rationale": "打ち切り規則の構造"},
        {"id": "W6", "title": "Overharvesting in human patch foraging", "abstract": "b" * 40,
         "year": 2023, "venue": "V", "cited_by_count": 10,
         "purpose_sim": 0.71, "mechanism_dist": 0.86, "structural_depth": 0.7,
         "has_causal_pm": True, "connection_label": "採餌", "serendipity_rationale": "離脱規則"},
    ]
    res = StdinMcpServer().handle_tool_call("delegate_finalize", {
        "theme_overview": "探索の打ち切り規則を設計する。" * 20,
        "goal": "決着しない側の打ち切り規則", "why_problem": "枠が有限であるため",
        "approach_type": "application", "assumptions": ["打ち切りは推定量を歪める", "一律は最適でない"],
        "scope_field": "statistics", "scope_scale": "small", "scope_time_range": "no_limit",
        "count": 1, "no_history": True, "grounded_only": False, "candidates": cands,
    })
    text = res["content"][0]["text"]
    assert "近いが有用" in text and "W1" in text
    assert "律速は距離(mechanism_dist)" in text


# --- F-15: the bar is a quantile of the submitted batch, and must say so ------------------
# Measured three times: 7 submitted -> 0.474, 4 submitted -> 0.554 for the same kind of
# material. The behaviour is deliberate; what was missing is that the caller could not see it.

def test_diag_reports_both_bars_and_both_pass_counts():
    works = {w: _work(w) for w in ("A", "B", "C", "D")}
    scores = {"A": _row(0.9, 0.9), "B": _row(0.8, 0.8), "C": _row(0.7, 0.7), "D": _row(0.6, 0.6)}
    diag = {}
    apply_post_gates(scores, works, count=4, diag=diag, gate=0.2)
    assert diag["gate_percentile"] > diag["gate_absolute_floor"] == 0.2
    assert diag["gate_is_batch_relative"] is True
    assert diag["batch_size"] == 4
    # every candidate clears the fixed floor; the percentile bar admits only the strongest
    assert diag["passed_at_absolute_floor"] == 4 and diag["passed"] < 4


def test_same_candidate_passes_in_a_weak_batch_and_fails_in_a_strong_one():
    """The F-15 shape itself, pinned: identical scoring, different company, different verdict."""
    target = _row(0.7, 0.7)          # serendipity 0.49
    weak = {"T": target, "W1": _row(0.4, 0.4), "W2": _row(0.3, 0.3), "W3": _row(0.3, 0.4)}
    strong = {"T": target, "S1": _row(0.9, 0.9), "S2": _row(0.9, 0.8), "S3": _row(0.85, 0.9)}
    ids = ("T", "W1", "W2", "W3", "S1", "S2", "S3")
    works = {w: _work(w) for w in ids}
    out_weak = apply_post_gates(weak, works, count=4, gate=0.2, output_floor=0.2)
    out_strong = apply_post_gates(strong, works, count=4, gate=0.2, output_floor=0.2)
    assert "T" in [e.work.id for e in out_weak]
    assert "T" not in [e.work.id for e in out_strong]
