"""Package B (2026-08-22 ruling): fine within-band tie-breaking for F-10's residue.

The 3-level anchors still drive every gate (R3's anti-jitter decision stands); the new
purpose_pct only orders candidates the anchors cannot separate — the observed failure
was every hit tying at 0.80 x 0.70 = 0.56 and the ranking becoming arbitrary.
"""

from __future__ import annotations

from src.core.models import Work
from src.pipeline.classify import _apply_causal_cap, _parse_pm_items, apply_post_gates
from src.pipeline.delegate import normalize_agent_scores


def _work(wid):
    return Work(id=wid, title=wid, year=2020, venue="v", doi=None, cited_by_count=10,
                abstract="a", concept_tags=[])


def test_parse_reads_purpose_pct_and_builds_fine_rank():
    items = [{"id": "W1", "purpose_level": "strong", "purpose_pct": 88,
              "mechanism_dist": 0.80, "connection_label": "c", "serendipity_rationale": "r"}]
    (wid, row, complete), = _parse_pm_items(items)
    assert row["purpose_sim"] == 0.70          # anchor unchanged (gates still see levels)
    assert row["purpose_pct"] == 88
    assert abs(row["fine_rank"] - 0.88 * 0.80) < 1e-9


def test_parse_tolerates_missing_or_garbage_pct():
    items = [{"id": "W1", "purpose_level": "strong", "mechanism_dist": 0.8,
              "connection_label": "c", "serendipity_rationale": "r", "purpose_pct": "??"}]
    (_, row, _), = _parse_pm_items(items)
    assert row["purpose_pct"] == 0 and row["fine_rank"] == 0.0


def test_tied_anchor_products_order_by_fine_rank():
    # The exact observed shape: two hits both 0.80 x 0.70 = 0.56.
    mats = []
    for wid, pct in (("W_LOW", 55), ("W_HIGH", 90)):
        mats.append({"id": wid, "title": wid, "abstract": "a", "year": 2020, "venue": "v",
                     "doi": None, "cited_by_count": 5, "purpose_sim": 0.70,
                     "mechanism_dist": 0.80, "purpose_pct": pct, "structural_depth": 0.9})
    works, scores, _ = normalize_agent_scores(mats)
    diag: dict = {}
    entries = apply_post_gates(scores, works, theme_profile=None, count=1, diag=diag)
    assert len(entries) == 1
    assert entries[0].work.id == "W_HIGH"      # 0.90x0.80 beats 0.55x0.80 at equal 0.56


def test_causal_cap_rescales_fine_rank_consistently():
    s = {"purpose_sim": 0.70, "mechanism_dist": 0.80, "purpose_pct": 90,
         "fine_rank": 0.72, "has_causal_pm": False}
    out = _apply_causal_cap([(0.56, "W1", s)])
    ser, _, row = out[0]
    assert row["purpose_sim"] == 0.45
    assert abs(ser - 0.56 * (0.45 / 0.70)) < 1e-9
    assert abs(row["fine_rank"] - round(0.72 * (0.45 / 0.70), 4)) < 1e-9
