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
