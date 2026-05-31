"""Tests for R5 self-consistency (vote-K) aggregation in classify.py."""

from __future__ import annotations

from typing import List

from src.core.models import ThemeInput, Scope, Keywords, Work
import src.pipeline.classify as classify


def _theme() -> ThemeInput:
    return ThemeInput(
        theme_overview="t", goal="g", why_problem="w", approach_type="design",
        assumptions=[], scope=Scope(field="f", scale="", time_range=""),
        keywords=Keywords(include=[], exclude=[]),
    )


def _work(wid: str) -> Work:
    return Work(id=wid, title=wid, year=2020, venue="", doi=None,
                cited_by_count=0, abstract="abstract")


# --- PM scoring vote-K -------------------------------------------------------

def test_pm_scoring_medians_numeric_fields(monkeypatch):
    # Three passes return purpose_sim 0.2 / 0.4 / 0.9 -> median 0.4 expected.
    seq = iter([0.2, 0.4, 0.9])

    def fake_chunk(papers_input, theme_schema, theme, model, retry_feedback=""):
        ps = next(seq)
        return [{
            "id": "WX", "paper_purpose": "p", "paper_mechanism": "m",
            "paper_finding": "f", "purpose_sim": ps, "mechanism_dist": 0.8,
            "connection_label": "L", "serendipity_rationale": "R",
        }]

    monkeypatch.setattr(classify, "_score_b_chunk_pm", fake_chunk)
    scores = classify._score_b_candidates_pm([_work("WX")], {"purpose": "p", "mechanism": "m"},
                                             _theme(), "m", vote_k=3)
    assert abs(scores["WX"]["purpose_sim"] - 0.4) < 1e-9
    assert abs(scores["WX"]["mechanism_dist"] - 0.8) < 1e-9


def test_pm_scoring_k1_is_single_pass(monkeypatch):
    calls = {"n": 0}

    def fake_chunk(papers_input, theme_schema, theme, model, retry_feedback=""):
        calls["n"] += 1
        return [{
            "id": "WX", "purpose_sim": 0.5, "mechanism_dist": 0.5,
            "connection_label": "L", "serendipity_rationale": "R",
            "paper_purpose": "p", "paper_mechanism": "m", "paper_finding": "f",
        }]

    monkeypatch.setattr(classify, "_score_b_chunk_pm", fake_chunk)
    classify._score_b_candidates_pm([_work("WX")], {"purpose": "p", "mechanism": "m"},
                                    _theme(), "m", vote_k=1)
    assert calls["n"] == 1  # no extra votes when k=1


# --- Judge vote-K ------------------------------------------------------------

def test_judge_medians_and_majority(monkeypatch):
    # structural_depth across 3 passes: 0.2 / 0.6 / 0.7 -> median 0.6.
    # has_causal_pm: True / True / False -> majority True.
    passes = iter([
        {"WX": {"structural_depth": 0.2, "applicability": 0.5, "has_causal_pm": True, "judge_reason": "a"}},
        {"WX": {"structural_depth": 0.6, "applicability": 0.5, "has_causal_pm": True, "judge_reason": "b"}},
        {"WX": {"structural_depth": 0.7, "applicability": 0.5, "has_causal_pm": False, "judge_reason": "c"}},
    ])
    monkeypatch.setattr(classify, "_judge_one_pass", lambda *a, **k: next(passes))
    survivors: List = [(_work("WX"), {"paper_purpose": "p"})]
    out = classify._judge_b_candidates(survivors, {"purpose": "p", "mechanism": "m"}, _theme(), "m", vote_k=3)
    assert abs(out["WX"]["structural_depth"] - 0.6) < 1e-9
    assert out["WX"]["has_causal_pm"] is True


def test_judge_majority_false(monkeypatch):
    passes = iter([
        {"WX": {"structural_depth": 0.5, "applicability": 0.5, "has_causal_pm": False, "judge_reason": "a"}},
        {"WX": {"structural_depth": 0.5, "applicability": 0.5, "has_causal_pm": False, "judge_reason": "b"}},
        {"WX": {"structural_depth": 0.5, "applicability": 0.5, "has_causal_pm": True, "judge_reason": "c"}},
    ])
    monkeypatch.setattr(classify, "_judge_one_pass", lambda *a, **k: next(passes))
    out = classify._judge_b_candidates([(_work("WX"), {})], {"purpose": "p", "mechanism": "m"},
                                       _theme(), "m", vote_k=3)
    assert out["WX"]["has_causal_pm"] is False  # 1/3 True -> minority -> False


def test_judge_k1_single_call(monkeypatch):
    calls = {"n": 0}

    def one(*a, **k):
        calls["n"] += 1
        return {"WX": {"structural_depth": 0.5, "applicability": 0.5, "has_causal_pm": True, "judge_reason": "r"}}

    monkeypatch.setattr(classify, "_judge_one_pass", one)
    classify._judge_b_candidates([(_work("WX"), {})], {"purpose": "p", "mechanism": "m"},
                                 _theme(), "m", vote_k=1)
    assert calls["n"] == 1
