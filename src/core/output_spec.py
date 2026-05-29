"""Output markdown builder (Phase 1 minimal)."""

from __future__ import annotations

from typing import List

from src.core.models import OutputDocument, OutputEntry, OutputSection, ThemeInput, Work  # noqa: F401


def _auto_tag(section_idx: int, entry_idx: int, label: str, edge: str) -> str:
    return f"<!-- AUTO_SECTION:S{section_idx:02d}-E{entry_idx:03d}:{label}:{edge} -->"


def _lines_for_theme(theme: ThemeInput) -> List[str]:
    lines = []
    lines.append(f"# {theme.scope.field} ブレインストーミング出力")
    lines.append("")
    lines.append("## 入力サマリ")
    lines.append("")
    lines.append(f"- テーマ概要: {theme.theme_overview}")
    lines.append(f"- 目的: {theme.goal}")
    lines.append(f"- 問題意識: {theme.why_problem}")
    lines.append(f"- アプローチ: {theme.approach_type}")
    lines.append("- 前提・仮説:")
    for assumption in theme.assumptions:
        lines.append(f"  - {assumption}")
    lines.append("- スコープ:")
    lines.append(f"  - 分野: {theme.scope.field}")
    lines.append(f"  - スケール: {theme.scope.scale}")
    lines.append(f"  - 時代: {theme.scope.time_range}")
    if theme.keywords.include:
        lines.append(f"- include: {', '.join(theme.keywords.include)}")
    if theme.keywords.exclude:
        lines.append(f"- exclude: {', '.join(theme.keywords.exclude)}")
    if theme.concern:
        lines.append(f"- 不安点: {theme.concern}")
    lines.append("")
    return lines


def _mock_entry() -> OutputEntry:
    work = Work(
        id="mock-0001",
        title="(モック) 施設間ドメインシフトが診断性能に与える影響",
        year=2022,
        venue="Mock Conference",
        doi=None,
        cited_by_count=0,
        abstract="(モック) 施設間の分布差が性能劣化に与える影響を検証する。",
    )
    return OutputEntry(
        work=work,
        relationship="テーマの中心課題である分布差の影響を直接扱う仮想例。",
        abstract_summary="施設間での性能差を比較し、主な劣化要因を抽出する。",
        caution="評価指標の設計に依存する可能性がある。",
    )


def build_minimal_document(theme: ThemeInput, include_mock: bool = True) -> OutputDocument:
    sections = [
        OutputSection(title="関連度が高い論文（100本）"),
        OutputSection(title="広域探索（200本）"),
        OutputSection(title="無関係論文（200本）"),
        OutputSection(title="無関係論文：反証・対立仮説（50本）"),
        OutputSection(title="無関係論文：測定・評価の地雷（50本）"),
        OutputSection(title="無関係論文：手法転用（50本）"),
        OutputSection(title="無関係論文：制約条件が真逆（50本）"),
    ]

    if include_mock and sections:
        sections[0].entries.append(_mock_entry())

    return OutputDocument(theme=theme, sections=sections)


def _link_for_work(work: Work) -> str:
    if work.doi:
        return work.doi
    if work.id:
        return work.id
    return "TBD"


def _render_track_a_entry(section_idx: int, entry_idx: int, entry: OutputEntry) -> List[str]:
    lines = []
    lines.append(f"### {entry_idx + 1}. {entry.work.title}")
    lines.append("")
    lines.append(f"- **関係度**: {entry.relationship_level or '—'}")
    lines.append(f"- **関係軸**: {entry.label or '—'}")
    lines.append(f"- 年: {entry.work.year}  |  掲載: {entry.work.venue}  |  被引用: {entry.work.cited_by_count}")
    lines.append(f"- リンク: {_link_for_work(entry.work)}")
    lines.append("")
    lines.append(_auto_tag(section_idx, entry_idx, "RELATIONSHIP", "START"))
    lines.append(f"1) 関係性: {entry.relationship}")
    lines.append(_auto_tag(section_idx, entry_idx, "RELATIONSHIP", "END"))
    lines.append(_auto_tag(section_idx, entry_idx, "SUMMARY", "START"))
    lines.append(f"2) 要約: {entry.abstract_summary}")
    lines.append(_auto_tag(section_idx, entry_idx, "SUMMARY", "END"))
    lines.append(_auto_tag(section_idx, entry_idx, "CAUTION", "START"))
    lines.append(f"3) 注意点: {entry.caution}")
    lines.append(_auto_tag(section_idx, entry_idx, "CAUTION", "END"))
    lines.append("")
    return lines


def _render_track_b_entry(section_idx: int, entry_idx: int, entry: OutputEntry) -> List[str]:
    lines = []
    lines.append(f"### {entry_idx + 1}. {entry.work.title}")
    lines.append("")
    lines.append(f"- **接続点**: {entry.label or '—'}")
    lines.append(f"- 年: {entry.work.year}  |  掲載: {entry.work.venue}  |  被引用: {entry.work.cited_by_count}")
    lines.append(f"- リンク: {_link_for_work(entry.work)}")
    lines.append("")
    lines.append(_auto_tag(section_idx, entry_idx, "RELATIONSHIP", "START"))
    lines.append(f"1) 関係性: {entry.relationship}")
    lines.append(_auto_tag(section_idx, entry_idx, "RELATIONSHIP", "END"))
    lines.append(_auto_tag(section_idx, entry_idx, "SUMMARY", "START"))
    lines.append(f"2) 要約: {entry.abstract_summary}")
    lines.append(_auto_tag(section_idx, entry_idx, "SUMMARY", "END"))
    lines.append(_auto_tag(section_idx, entry_idx, "CAUTION", "START"))
    lines.append(f"3) 注意点: {entry.caution}")
    lines.append(_auto_tag(section_idx, entry_idx, "CAUTION", "END"))
    lines.append("")
    return lines


def render_markdown(doc: OutputDocument) -> str:
    lines = _lines_for_theme(doc.theme)

    has_track_sections = any(s.track in ("A", "B") for s in doc.sections)

    if has_track_sections:
        lines.append("## 目次")
        lines.append("")
        for section in doc.sections:
            lines.append(f"- {section.title}")
        lines.append("")

        for section_idx, section in enumerate(doc.sections):
            lines.append(f"## {section.title}")
            lines.append("")
            if not section.entries:
                lines.append("- （未収集）")
                lines.append("")
                continue
            for entry_idx, entry in enumerate(section.entries):
                if section.track == "B":
                    lines.extend(_render_track_b_entry(section_idx, entry_idx, entry))
                else:
                    lines.extend(_render_track_a_entry(section_idx, entry_idx, entry))
    else:
        # Legacy format
        lines.append("## 目次")
        lines.append("")
        for section in doc.sections:
            lines.append(f"- {section.title}")
        lines.append("")
        for section_idx, section in enumerate(doc.sections):
            lines.append(f"## {section.title}")
            lines.append("")
            if not section.entries:
                lines.append("- （未収集）")
                lines.append("")
                continue
            for entry_idx, entry in enumerate(section.entries):
                lines.append(f"- タイトル: {entry.work.title}")
                lines.append(f"- 年: {entry.work.year}")
                lines.append(f"- 掲載: {entry.work.venue}")
                lines.append(f"- 被引用: {entry.work.cited_by_count}")
                lines.append(f"- リンク: {_link_for_work(entry.work)}")
                lines.append("")
                lines.append(_auto_tag(section_idx, entry_idx, "RELATIONSHIP", "START"))
                lines.append("1) 関係性: ")
                lines.append(_auto_tag(section_idx, entry_idx, "RELATIONSHIP", "END"))
                lines.append(_auto_tag(section_idx, entry_idx, "SUMMARY", "START"))
                lines.append("2) 要約: ")
                lines.append(_auto_tag(section_idx, entry_idx, "SUMMARY", "END"))
                lines.append(_auto_tag(section_idx, entry_idx, "CAUTION", "START"))
                lines.append("3) 注意点: ")
                lines.append(_auto_tag(section_idx, entry_idx, "CAUTION", "END"))
                lines.append("")

    lines.append("## 付録")
    lines.append("")
    lines.append(f"- 取得日: {doc.collected_at or 'TBD'}")
    lines.append(f"- 検索条件: {doc.query or 'TBD'}")
    lines.append(f"- フィルタ条件: {doc.filter_policy or 'TBD'}")
    lines.append("")

    return "\n".join(lines)
