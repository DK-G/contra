"""F-77 (survey 2026-10-31): a caution saying "general participants, not students" reached the output
though the abstract says only "256 participants". Grounding does not check summary or caution, so the
output says so, and only on text the caller wrote."""

from __future__ import annotations

from src.core.models import ThemeInput
from src.pipeline.delegate import UNCHECKED_PROSE_MARK, finalize_delegated_document

THEME_TEXT = "警報の妥当性を見せると反応が変わるかを知りたい。" * 10


def _theme() -> ThemeInput:
    from src.mcp_server import _build_theme_input
    return _build_theme_input({"theme_overview": THEME_TEXT, "goal": "g", "why_problem": "w", "approach_type": "experiment",
                               "assumptions": ["a", "b"], "scope_field": "Psychology", "scope_scale": "small",
                               "scope_time_range": "last_10_years", "keywords_include": ["alarm"],
                               "keywords_exclude": [], "concern": "c"})


def _material(**prose) -> dict:
    return {"id": "W1", "title": "Alarm study", "abstract": "We tested 256 participants on alarm validity information.",
            "year": 2020, "venue": "J", "doi": None, "cited_by_count": 5, "purpose_sim": 0.8, "mechanism_dist": 0.8,
            "structural_depth": 0.8, "has_causal_pm": True, "connection_label": "x", **prose}


def _entry(material: dict, **kw):
    doc = finalize_delegated_document([material], _theme(), count=1, **kw)
    return doc.sections[0].entries[0]


def test_written_summary_and_caution_say_they_were_not_checked():
    entry = _entry(_material(summary="概要の文", caution="一般の参加者 256 人"))
    assert entry.abstract_summary == UNCHECKED_PROSE_MARK + "概要の文"
    assert entry.caution == UNCHECKED_PROSE_MARK + "一般の参加者 256 人"


def test_the_fill_for_unwritten_fields_gets_no_mark():
    entry = _entry(_material())
    assert UNCHECKED_PROSE_MARK not in entry.abstract_summary
    assert UNCHECKED_PROSE_MARK not in entry.caution


def test_grounded_relationship_gets_no_mark():
    entry = _entry(_material(relationship="対応の文", caution="c", theme_quote=THEME_TEXT[:12],
                             source_quote="256 participants on alarm"))
    assert entry.relationship == "対応の文"
    assert entry.caution == UNCHECKED_PROSE_MARK + "c"
