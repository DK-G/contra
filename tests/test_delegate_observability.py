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


def test_echo_warning_names_the_grounding_consequence_f19():
    # F-19: the warning used to read as a cosmetic/rendering problem, so callers skipped it
    # and then read the grounding failure as "my quote was wrong".
    bare = _material("W1", 0.5, 0.8)
    bare.pop("title"); bare.pop("abstract")
    line = echo_completeness_warnings([bare])[0]
    assert "接地検証も不能にします" in line


def test_echo_warning_without_text_fields_omits_grounding_note():
    m = _material("W1", 0.5, 0.8)
    m.pop("year")                      # not part of the source_quote haystack
    line = echo_completeness_warnings([m])[0]
    assert "year" in line and "接地検証" not in line


# --- F-19-R residue: an empty field upstream is not the caller's echo omission ------------

def _openalex_work_without_venue():
    from src.core.models import Work
    # 2026-09-14 W4290991335 / 2026-09-17 (seismology): OpenAlex had no venue; contra emitted "".
    return Work(id="W4290991335", title="Paper", year=2022, venue="", doi=None,
                cited_by_count=3, abstract="abstract text")


def test_faithful_echo_of_an_upstream_empty_venue_is_not_blamed_on_the_caller():
    m = material_from_work(_openalex_work_without_venue())
    assert m["upstream_empty"] == ["venue"]
    m.update(purpose_sim=0.5, mechanism_dist=0.8)          # the caller echoes everything
    lines = echo_completeness_warnings([m])
    assert len(lines) == 1
    assert lines[0].startswith("ℹ") and "contra の取得材料の時点で空" in lines[0]
    assert "echo してください" not in lines[0]


def test_blank_but_present_field_without_mark_is_attributed_upstream():
    # Older materials (before the mark) echoed faithfully: key present, value "".
    lines = echo_completeness_warnings([_material("W1", 0.5, 0.8, venue="")])
    assert len(lines) == 1 and lines[0].startswith("ℹ")


def test_dropped_key_is_still_named_as_the_callers_omission():
    # 2026-09-15: hand transcription dropped venue — that IS the caller's echo omission.
    m = _material("W1", 0.5, 0.8)
    m.pop("venue")
    lines = echo_completeness_warnings([m])
    assert len(lines) == 1 and lines[0].startswith("⚠") and "venue" in lines[0]


def test_mixed_upstream_gap_and_caller_drop_get_one_line_each():
    m = material_from_work(_openalex_work_without_venue())
    m.update(purpose_sim=0.5, mechanism_dist=0.8)
    m.pop("year")
    lines = echo_completeness_warnings([m])
    assert [l[0] for l in lines] == ["ℹ", "⚠"]
    assert "venue" in lines[0] and "year" in lines[1] and "venue" not in lines[1]


def test_complete_material_carries_no_upstream_mark():
    from src.core.models import Work
    w = Work(id="W2", title="T", year=2020, venue="J", doi=None, cited_by_count=1, abstract="a")
    assert "upstream_empty" not in material_from_work(w)
