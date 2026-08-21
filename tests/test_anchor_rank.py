"""F-03: theme relevance must actually move the Track A ranking.

Every source computed theme_fit_score (keyword hits in name/description/topics/readme)
but ranking used reliability (quality) alone — on GitHub the fit score was an orphaned
"backwards compatibility metric". Six weeks of field observations show well-built but
off-topic repos outranking on-topic ones. The fix multiplies:
rank = reliability * (0.35 + 0.65 * relevance). Both calibration cases below are the
REAL observed bugs (audit lesson: calibrate detectors on the real bug, not round numbers).
"""

from __future__ import annotations

from src.core.models import Work
from src.pipeline.track_a import (
    _RANK_RELEVANCE_FLOOR,
    anchor_rank_key,
    annotate_anchor_rank,
)


def _anchor(wid: str, reliability: int, fit: int, ptype: str = "github_repository") -> Work:
    return Work(
        id=wid, title=wid, year=2026, venue="GitHub", doi=None, cited_by_count=100,
        abstract="", publication_type=ptype,
        source_meta={"reliability_score": reliability, "theme_fit_score": fit},
    )


def _ranked(works):
    annotate_anchor_rank(works)
    return sorted(works, key=anchor_rank_key, reverse=True)


def test_observed_bug_2026_08_20_flips():
    # katgpt-rs: 86, irrelevant (fit 0) beat openevolve: 83, relevant. Must flip even
    # when the relevant repo's lexical match is weak (a single keyword hit = 10/30).
    irrelevant = _anchor("katgpt-rs", 86, 0)
    relevant = _anchor("openevolve", 83, 10)
    order = [w.id for w in _ranked([irrelevant, relevant])]
    assert order == ["openevolve", "katgpt-rs"]


def test_observed_bug_2026_08_17_flips():
    # aligntune: 84, irrelevant topped; the only on-topic candidate sat below at 79.
    irrelevant = _anchor("aligntune", 84, 0)
    relevant = _anchor("ab-test-research-designer", 79, 10)
    order = [w.id for w in _ranked([irrelevant, relevant])]
    assert order == ["ab-test-research-designer", "aligntune"]


def test_equal_relevance_preserves_quality_order():
    # The multiplier reweights BETWEEN relevance levels, never scrambles within one.
    a = _anchor("better", 90, 20)
    b = _anchor("worse", 60, 20)
    order = [w.id for w in _ranked([a, b])]
    assert order == ["better", "worse"]


def test_zero_relevance_floor_keeps_anchors_rankable():
    # Crude lexical matching must not zero everything on a thin theme.
    a = _anchor("only-candidate", 80, 0)
    annotate_anchor_rank([a])
    assert a.source_meta["anchor_rank_score"] == round(80 * _RANK_RELEVANCE_FLOOR, 1)
    assert a.source_meta["anchor_rank_score"] > 0


def test_fit_scale_is_normalised_per_source():
    # GitHub fit caps at 30, HF/Kaggle at 20 — full marks mean relevance 1.0 on both.
    gh = _anchor("gh", 80, 30, ptype="github_repository")
    kg = _anchor("kg", 80, 20, ptype="kaggle_dataset")
    annotate_anchor_rank([gh, kg])
    assert gh.source_meta["relevance"] == 1.0
    assert kg.source_meta["relevance"] == 1.0
    assert gh.source_meta["anchor_rank_score"] == kg.source_meta["anchor_rank_score"] == 80.0


def test_unannotated_work_falls_back_to_reliability():
    w = _anchor("legacy", 70, 0)
    assert anchor_rank_key(w) == 70.0   # no anchor_rank_score stamped yet


# --- density-normalised readme fit (calibrated on live probes, 2026-08-21) ----

from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.git_collect import _theme_fit_score
from src.core.models import GitRepository


def _theme_with_keywords(*include: str) -> ThemeInput:
    return ThemeInput(
        theme_overview="o", goal="g", why_problem="w", approach_type="application",
        assumptions=[], scope=Scope(field="statistics", scale="small", time_range="last_10_years"),
        keywords=Keywords(include=list(include), exclude=[]),
    )


def test_focused_readme_single_mention_earns_full_credit():
    # confseq shape: one genuine mention in a 7.6KB readme (below any prefix cut).
    readme = ("x" * 5700) + " two-sided sequential test of the hypothesis " + ("y" * 1900)
    repo = GitRepository(full_name="gostevehoward/confseq", html_url="",
                        description="Confidence sequences and uniform boundaries", readme_text=readme)
    assert _theme_fit_score(_theme_with_keywords("sequential test"), repo) == 10


def test_mega_readme_scattered_mentions_earn_only_partial_credit():
    # frankensqlite shape: 3+2+1 incidental hits spread over ~180KB must NOT read as
    # a perfect fit (naive full-text presence gave it relevance 1.0 in the live probe).
    chunk = "z" * 29_000
    readme = chunk + " e-value " + chunk + " e-value " + chunk + " e-value " + \
             chunk + " anytime-valid " + chunk + " anytime-valid " + chunk + " sequential test "
    repo = GitRepository(full_name="d/frankensqlite", html_url="", description="SQLite rewritten in Rust",
                        readme_text=readme)
    fit = _theme_fit_score(_theme_with_keywords("sequential test", "e-value", "anytime-valid"), repo)
    assert 0 < fit <= 5    # ~0.33 credit total -> 3, nowhere near the 30 of a real match


def test_description_hit_is_full_credit_regardless_of_readme_size():
    repo = GitRepository(full_name="a/b", html_url="",
                        description="anytime-valid confidence sequences toolkit",
                        readme_text="q" * 200_000)
    assert _theme_fit_score(_theme_with_keywords("anytime-valid"), repo) == 10


def test_tiny_readme_is_not_inflated():
    # A 50-char readme with a hit must not multiply credit via a tiny denominator.
    repo = GitRepository(full_name="a/b", html_url="", description="",
                        readme_text="the SPRT implementation")
    assert _theme_fit_score(_theme_with_keywords("SPRT"), repo) == 10  # capped at 1.0 credit
