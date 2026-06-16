"""Output markdown builder (Phase 1 minimal)."""

from __future__ import annotations

from typing import List

from src.core.models import OutputDocument, OutputEntry, OutputSection, ThemeInput, Work  # noqa: F401


def _auto_tag(section_idx: int, entry_idx: int, label: str, edge: str) -> str:
    return f"<!-- AUTO_SECTION:S{section_idx:02d}-E{entry_idx:03d}:{label}:{edge} -->"


def _lines_for_theme(theme: ThemeInput) -> List[str]:
    lines = []
    lines.append(f"# {theme.scope.field} contra 視座拡張レポート")
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



def _link_for_work(work: Work) -> str:
    if work.doi:
        return work.doi
    if work.id:
        return work.id
    return "TBD"


def _is_github_work(work: Work) -> bool:
    return work.publication_type == "github_repository"


def _is_hf_work(work: Work) -> bool:
    return (work.publication_type or "").startswith("huggingface_")


def _render_4part_body(section_idx: int, entry_idx: int, entry: OutputEntry) -> List[str]:
    """Render the shared 4-part body: 概要 / 関連性 / 役に立つ可能性の仮説 / 注意点."""
    lines = []
    lines.append(_auto_tag(section_idx, entry_idx, "SUMMARY", "START"))
    lines.append(f"1) 概要: {entry.abstract_summary}")
    lines.append(_auto_tag(section_idx, entry_idx, "SUMMARY", "END"))
    lines.append(_auto_tag(section_idx, entry_idx, "RELATIONSHIP", "START"))
    lines.append(f"2) テーマとの関連性: {entry.relationship}")
    lines.append(_auto_tag(section_idx, entry_idx, "RELATIONSHIP", "END"))
    lines.append(_auto_tag(section_idx, entry_idx, "HYPOTHESIS", "START"))
    lines.append(f"3) 役に立つ可能性の仮説: {entry.usefulness_hypothesis}")
    lines.append(_auto_tag(section_idx, entry_idx, "HYPOTHESIS", "END"))
    lines.append(_auto_tag(section_idx, entry_idx, "CAUTION", "START"))
    lines.append(f"4) 注意点: {entry.caution}")
    lines.append(_auto_tag(section_idx, entry_idx, "CAUTION", "END"))
    lines.append("")
    return lines


def _render_track_a_entry(section_idx: int, entry_idx: int, entry: OutputEntry) -> List[str]:
    lines = []
    lines.append(f"### {entry_idx + 1}. {entry.work.title}")
    lines.append("")
    lines.append(f"- **関係度**: {entry.relationship_level or '—'}")
    lines.append(f"- **関係軸**: {entry.label or '—'}")
    if _is_github_work(entry.work):
        score = entry.work.source_meta.get("reliability_score", "—")
        issue_signal = entry.work.source_meta.get("issue_signal_summary", "—")
        license_name = entry.work.source_meta.get("license_name", "—")
        impl_doc = entry.work.source_meta.get("impl_doc_score")
        lma = entry.work.source_meta.get("lma_score")
        comm = entry.work.source_meta.get("community_score")
        sec = entry.work.source_meta.get("security_score")
        has_rich = entry.work.source_meta.get("has_rich_signals")
        # Scoring mode tells the reader how Pillar 1 was computed: scores are
        # only comparable within the same mode (rich mode migrates README weight
        # onto verified time/people signals). See DECISION_LOG 2026-06-12 (A-RS2).
        mode = "rich: time+people" if has_rich else "README-only"
        lines.append(f"- 更新年: {entry.work.year or '—'}  |  種別: {entry.work.venue}  |  stars: {entry.work.cited_by_count}")
        if impl_doc is not None and lma is not None and comm is not None and sec is not None:
            lines.append(
                f"- Reliability Score: {score}/100 [{mode}] "
                f"(Impl/Doc: {impl_doc}/30, LMA: {lma}/25, Comm: {comm}/20, Sec: {sec}/25)  |  License: {license_name}"
            )
        else:
            lines.append(f"- Reliability Score: {score}/100 [{mode}]  |  License: {license_name}")
        if has_rich:
            verified = entry.work.source_meta.get("verified_maturity_score", "—")
            releases = entry.work.source_meta.get("release_count", "—")
            ci_sampled = entry.work.source_meta.get("ci_runs_sampled", "—")
            ci_ok = entry.work.source_meta.get("ci_recent_success", "—")
            lines.append(
                f"- Verified Maturity: {verified}/12 (releases: {releases}, CI: {ci_ok}/{ci_sampled} passing)"
            )
            third_party = entry.work.source_meta.get("third_party_score", "—")
            contributors = entry.work.source_meta.get("external_contributor_count", "—")
            reporters = entry.work.source_meta.get("non_owner_issue_reporters", "—")
            lines.append(
                f"- Third-Party Signal: {third_party}/6 (ext. contributors: {contributors}, non-owner reporters: {reporters})"
            )
        lines.append(f"- Issue Signal: {issue_signal}")
    elif _is_hf_work(entry.work):
        score = entry.work.source_meta.get("reliability_score", "—")
        license_name = entry.work.source_meta.get("license_name") or "—"
        downloads = entry.work.source_meta.get("downloads", "—")
        likes = entry.work.source_meta.get("likes", "—")
        kind = entry.work.source_meta.get("hf_kind", "—")
        pipeline_tag = entry.work.source_meta.get("pipeline_tag") or "—"
        adoption = entry.work.source_meta.get("adoption_score")
        activity = entry.work.source_meta.get("activity_score")
        license_pts = entry.work.source_meta.get("license_score")
        theme_fit = entry.work.source_meta.get("theme_fit_score")
        lines.append(
            f"- 更新年: {entry.work.year or '—'}  |  種別: {entry.work.venue}/{kind}  |  "
            f"DL: {downloads}  |  likes: {likes}"
        )
        if (
            adoption is not None
            and activity is not None
            and license_pts is not None
            and theme_fit is not None
        ):
            lines.append(
                f"- Reliability Score: {score}/100 "
                f"(Adoption: {adoption}/40, Activity: {activity}/25, "
                f"License: {license_pts}/15, Theme-fit: {theme_fit}/20)  |  License: {license_name}"
            )
        else:
            lines.append(f"- Reliability Score: {score}/100  |  License: {license_name}")
        lines.append(f"- Task/Pipeline: {pipeline_tag}")
    else:
        lines.append(f"- 年: {entry.work.year}  |  掲載: {entry.work.venue}  |  被引用: {entry.work.cited_by_count}")
    lines.append(f"- リンク: {_link_for_work(entry.work)}")
    lines.append("")
    lines.extend(_render_4part_body(section_idx, entry_idx, entry))
    return lines


def _render_track_b_entry(section_idx: int, entry_idx: int, entry: OutputEntry) -> List[str]:
    lines = []
    lines.append(f"### {entry_idx + 1}. {entry.work.title}")
    lines.append("")
    lines.append(f"- **接続点**: {entry.label or '—'}")
    lines.append(
        f"- **セレンディピティ・スコア**: {entry.serendipity_score} "
        f"（距離 {entry.distance_score} × 構造 {entry.structure_score}）"
    )
    lines.append(f"- 年: {entry.work.year}  |  掲載: {entry.work.venue}  |  被引用: {entry.work.cited_by_count}")
    lines.append(f"- リンク: {_link_for_work(entry.work)}")
    lines.append("")
    lines.extend(_render_4part_body(section_idx, entry_idx, entry))
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
