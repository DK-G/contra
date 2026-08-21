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
