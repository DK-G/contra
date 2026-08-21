"""F-09: delegate_finalize must not degrade silently.

(1) Missing echoed material fields produce explicit warnings instead of blank renders.
(2) Every rejected candidate is named with the floor it hit, the measured value, and the
    threshold — the caller scores candidates itself, so this calibrates its next run.
"""

from __future__ import annotations

from src.core.models import ThemeInput, Scope, Keywords
from src.pipeline.classify import apply_post_gates
from src.pipeline.delegate import (
    echo_completeness_warnings,
    material_from_work,
    normalize_agent_scores,
    work_from_material,
)


def _material(wid: str, purpose: float, mech: float, **extra) -> dict:
    m = {
        "id": wid, "title": f"Paper {wid}", "abstract": "abstract text", "year": 2020,
        "venue": "Journal", "doi": None, "cited_by_count": 10,
        "purpose_sim": purpose, "mechanism_dist": mech,
    }
    m.update(extra)
    return m


# --- (1) echo completeness ---------------------------------------------------

def test_full_echo_produces_no_warnings():
    assert echo_completeness_warnings([_material("W1", 0.5, 0.8)]) == []


def test_id_and_scores_only_is_named_with_missing_fields():
    # The observed F-09 shape: the caller sent id + scores and got "### 1." / "年: 0".
    bare = {"id": "W9", "purpose_sim": 0.5, "mechanism_dist": 0.8}
    warnings = echo_completeness_warnings([bare])
    assert len(warnings) == 1
    for field in ("title", "abstract", "year", "venue", "cited_by_count"):
        assert field in warnings[0]
    assert "W9" in warnings[0]


def test_cited_by_zero_is_a_value_not_a_gap():
    m = _material("W1", 0.5, 0.8, cited_by_count=0)
    assert echo_completeness_warnings([m]) == []


# --- (2) per-rejection diagnostics -------------------------------------------

def _run_postgate(materials, **kw):
    works, scores, _ = normalize_agent_scores(materials)
    diag: dict = {}
    entries = apply_post_gates(scores, works, theme_profile=None, diag=diag, **kw)
    return entries, diag


def test_anomaly_rejection_is_named_with_value_and_threshold():
    _entries, diag = _run_postgate([
        _material("KEEP", 0.70, 0.80),
        _material("ANOM", 0.10, 0.90),     # below _PURPOSE_SIM_MIN=0.20
    ], count=1)
    rows = {r["id"]: r for r in diag["rejections"]}
    assert rows["ANOM"]["floor"].startswith("anomaly")
    assert rows["ANOM"]["value"] == 0.10 and rows["ANOM"]["threshold"] == 0.20


def test_hollow_rejection_is_named():
    _entries, diag = _run_postgate([
        _material("KEEP", 0.70, 0.80, structural_depth=0.9),
        _material("HOLLOW", 0.70, 0.80, structural_depth=0.30),   # below gate 0.50
    ], count=1)
    rows = {r["id"]: r for r in diag["rejections"]}
    assert rows["HOLLOW"]["floor"].startswith("hollow")
    assert rows["HOLLOW"]["value"] == 0.30 and rows["HOLLOW"]["threshold"] == 0.50


def test_output_floor_rejection_is_named():
    # ser: KEEP=0.56, WEAK=0.24 -> WEAK passes anomaly but dies on a serendipity floor,
    # and the diagnostics must say which one with the measured product.
    _entries, diag = _run_postgate([
        _material("KEEP", 0.70, 0.80),
        _material("WEAK", 0.30, 0.80),
    ], count=2)
    rows = {r["id"]: r for r in diag["rejections"]}
    assert "WEAK" in rows
    assert "serendipity" in rows["WEAK"]["floor"]
    assert abs(rows["WEAK"]["value"] - 0.24) < 1e-6


def test_every_dropped_candidate_appears_exactly_once():
    materials = [
        _material("KEEP", 0.70, 0.80, structural_depth=0.9),
        _material("ANOM", 0.10, 0.90),
        _material("HOLLOW", 0.70, 0.80, structural_depth=0.30),
        _material("WEAK", 0.30, 0.80, structural_depth=0.9),
    ]
    entries, diag = _run_postgate(materials, count=4)
    kept_ids = {e.work.id for e in entries}
    rejected_ids = [r["id"] for r in diag["rejections"]]
    assert kept_ids == {"KEEP"}
    assert sorted(rejected_ids) == ["ANOM", "HOLLOW", "WEAK"]      # no dupes, none silent


def test_material_roundtrip_still_holds():
    # guard: the new warning path must not disturb the existing echo contract
    w = work_from_material(_material("W1", 0.5, 0.8))
    assert material_from_work(w)["title"] == "Paper W1"
