"""Tests for output_spec.render_markdown."""

from src.core.models import (
    Keywords, OutputDocument, OutputEntry, OutputSection,
    Scope, ThemeInput, Work,
)
from src.core.output_spec import render_markdown


def _theme():
    return ThemeInput(
        theme_overview="テーマ概要",
        goal="目的",
        why_problem="問題意識",
        approach_type="experiment",
        assumptions=["仮説1"],
        scope=Scope(field="CS", scale="small", time_range="last_10_years"),
        keywords=Keywords(include=["kw1"]),
    )


def _work(doi="10.1234/test"):
    return Work(
        id="W1", title="Test Paper", year=2024, venue="ICML",
        doi=doi, cited_by_count=10, abstract="test abstract",
    )


def test_render_contains_theme_overview():
    doc = OutputDocument(theme=_theme(), sections=[])
    assert "テーマ概要" in render_markdown(doc)


def test_render_track_b_entry():
    entry = OutputEntry(
        work=_work(), relationship="関連性", abstract_summary="概要",
        caution="注意点", usefulness_hypothesis="仮説テキスト",
        track="B", label="【接続点: テスト】",
        distance_score=0.8, structure_score=0.6, serendipity_score=0.48,
    )
    section = OutputSection(title="Track B: 接続点フィーチャー（1本）", track="B", entries=[entry])
    doc = OutputDocument(theme=_theme(), sections=[section], collected_at="2024-01-01")
    md = render_markdown(doc)
    assert "Test Paper" in md
    assert "接続点: テスト" in md
    assert "役に立つ可能性の仮説" in md
    assert "仮説テキスト" in md
    assert "注意点" in md


def test_render_track_a_entry():
    entry = OutputEntry(
        work=_work(), relationship="関連性", abstract_summary="概要",
        caution="注意点", usefulness_hypothesis="仮説テキスト",
        track="A", label="手法の参照", relationship_level="高",
    )
    section = OutputSection(title="Track A: アンカー（1本）", track="A", entries=[entry])
    doc = OutputDocument(theme=_theme(), sections=[section])
    md = render_markdown(doc)
    assert "Test Paper" in md
    assert "手法の参照" in md
    assert "関係度" in md


def test_render_empty_section_shows_placeholder():
    section = OutputSection(title="Track B: 接続点フィーチャー（0本）", track="B", entries=[])
    doc = OutputDocument(theme=_theme(), sections=[section])
    assert "未収集" in render_markdown(doc)


def test_render_appendix_contains_date():
    doc = OutputDocument(theme=_theme(), sections=[], collected_at="2024-06-01")
    assert "2024-06-01" in render_markdown(doc)


def test_render_doi_used_as_link():
    entry = OutputEntry(
        work=_work(doi="10.1234/test"), relationship="r", abstract_summary="s",
        caution="c", track="B", label="【接続点: X】",
    )
    section = OutputSection(title="T", track="B", entries=[entry])
    doc = OutputDocument(theme=_theme(), sections=[section])
    assert "10.1234/test" in render_markdown(doc)


def test_render_openalex_id_fallback_when_no_doi():
    entry = OutputEntry(
        work=_work(doi=None), relationship="r", abstract_summary="s",
        caution="c", track="B", label="【接続点: X】",
    )
    section = OutputSection(title="T", track="B", entries=[entry])
    doc = OutputDocument(theme=_theme(), sections=[section])
    assert "W1" in render_markdown(doc)
