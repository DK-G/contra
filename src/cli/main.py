"""CLI entrypoint for Phase 1."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from src.core.input_schema import InputValidationError, validate_and_normalize
from src.core.models import OutputDocument, OutputSection
from src.openalex.client import OpenAlexClient, OpenAlexConfig, OpenAlexError
from src.openalex.parser import OpenAlexParseError, normalize_results
from src.pipeline.classify import classify_stub
from src.pipeline.collect import CollectConfig, Collector, collect_and_filter
from src.pipeline.export import export_markdown
from src.pipeline.generate import GenerationConfig, generate_entries


def _load_json(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise InputValidationError(f"input file not found: {path}") from exc
    except OSError as exc:
        raise InputValidationError(f"failed to read input file: {path}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputValidationError(f"invalid json: {exc}") from exc

    if not isinstance(data, dict):
        raise InputValidationError("input json must be an object")
    return data


def _run_openalex_test(query: str, per_page: int, mailto: str | None) -> int:
    config = OpenAlexConfig(mailto=mailto)
    client = OpenAlexClient(config)
    try:
        payload = client.get({"search": query, "per-page": per_page})
        works = normalize_results(payload)
    except (OpenAlexError, OpenAlexParseError) as exc:
        print(f"[error] openalex: {exc}", file=sys.stderr)
        return 1

    print(f"[ok] openalex results: {len(works)}")
    for work in works[: min(3, len(works))]:
        print(f"- {work.title} ({work.year}) | {work.venue}")
    return 0


def _run_collect_test(input_path: Path, per_page: int, max_pages: int, mailto: str | None) -> int:
    try:
        payload = _load_json(input_path)
        theme = validate_and_normalize(payload)
    except InputValidationError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    collector = Collector(CollectConfig(per_page=per_page, max_pages=max_pages, mailto=mailto))
    try:
        works = collector.collect(theme)
    except (OpenAlexError, OpenAlexParseError) as exc:
        print(f"[error] openalex: {exc}", file=sys.stderr)
        return 1

    print(f"[ok] collected: {len(works)}")
    for work in works[: min(5, len(works))]:
        print(f"- {work.title} ({work.year}) | {work.venue}")
    return 0


def _build_query(theme) -> str:
    tokens = []
    tokens.extend(theme.keywords.include)
    if not tokens:
        if theme.scope.field:
            tokens.append(theme.scope.field)
        if theme.goal:
            tokens.append(theme.goal)
    return " ".join(t for t in tokens if t)


def _build_theme_summary(theme) -> str:
    parts = [theme.theme_overview, theme.goal, theme.why_problem]
    if theme.concern:
        parts.append(f"懸念: {theme.concern}")
    return " / ".join(part for part in parts if part)


def _category_role(category: str) -> str:
    if "反証・対立仮説" in category:
        return (
            "この論文の結論が正しいと仮定した場合、"
            "ユーザーの仮説のどこが間違っていることになるかを指摘する。"
        )
    if "測定・評価の地雷" in category:
        return (
            "この論文が警告している実験の失敗パターンを特定し、"
            "同じ罠にハマらないための警告を書く。"
        )
    if "手法転用" in category:
        return (
            "対象ドメインは異なっても、どのアルゴリズムの考え方が"
            "本テーマに盗めるかを具体的に提案する。"
        )
    if "制約条件が真逆" in category:
        return (
            "前提条件が真逆である点を明示し、"
            "そのまま転用できない理由を具体的に示す。"
        )
    return "与えられたテーマに対する影響を意識して書く。"


def _material_instruction(category: str, concern: str | None) -> str:
    base = (
        "plan.mdの仕様に基づき、関係性・要約・注意点を各1文で整理する。"
        "関係性は観点や条件を明示し、要約は言い換えで作る。"
        "3要素で語彙の重複を避け、注意点は曖昧な表現を避けて具体的に書く。"
        "被引用数が多い場合は定説、少ないが新しい場合は新説・兆候として扱う。"
        "後続研究で否定された点や限界があれば注意点に含める。"
    )
    role = _category_role(category)
    if concern:
        return f"{base}{role}特に「{concern}」にどう影響するかを意識する。"
    return f"{base}{role}"


def _write_gemini_materials(
    out_dir: Path,
    theme,
    classified,
) -> Path:
    theme_summary = _build_theme_summary(theme)
    materials: list[tuple[str, list]] = [
        ("関連度が高い論文（100本）", classified.related),
        ("広域探索（200本）", classified.broad),
        ("無関係論文（200本）", classified.unrelated),
    ]
    for key, works in classified.unrelated_chapters.items():
        materials.append((f"無関係論文：{key}（50本）", works))

    lines: list[str] = []
    for category, works in materials:
        instruction = _material_instruction(category, theme.concern)
        for work in works:
            payload = {
                "id": work.id,
                "category": category,
                "input_theme_summary": theme_summary,
                "paper_metadata": {
                    "title": work.title,
                    "abstract": work.abstract,
                    "url": work.id,
                    "doi": work.doi,
                    "year": work.year,
                    "venue": work.venue,
                    "concepts": work.concepts,
                    "author_affiliations": work.author_affiliations,
                    "publication_type": work.publication_type,
                    "cited_by_count": work.cited_by_count,
                    "citation_context": None,
                },
                "instruction": instruction,
            }
            lines.append(json.dumps(payload, ensure_ascii=False))

    out_path = out_dir / "gemini_materials.jsonl"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def _build_document(
    theme, classified, query: str, collected_count: int, gen_mode: str, gen_config: GenerationConfig
) -> OutputDocument:
    keywords = list(theme.keywords.include or [])
    sections = [
        OutputSection(
            title="関連度が高い論文（100本）",
            entries=generate_entries(
                classified.related,
                keywords=keywords,
                theme=theme,
                mode=gen_mode,
                config=gen_config,
            ),
        ),
        OutputSection(
            title="広域探索（200本）",
            entries=generate_entries(
                classified.broad,
                keywords=keywords,
                theme=theme,
                mode=gen_mode,
                config=gen_config,
            ),
        ),
        OutputSection(
            title="無関係論文（200本）",
            entries=generate_entries(
                classified.unrelated,
                keywords=keywords,
                theme=theme,
                mode=gen_mode,
                config=gen_config,
            ),
        ),
    ]

    chapter_titles = [
        "無関係論文：反証・対立仮説（50本）",
        "無関係論文：測定・評価の地雷（50本）",
        "無関係論文：手法転用（50本）",
        "無関係論文：制約条件が真逆（50本）",
    ]
    for title in chapter_titles:
        key = title.replace("無関係論文：", "").replace("（50本）", "")
        works = classified.unrelated_chapters.get(key, [])
        sections.append(
            OutputSection(
                title=title,
                entries=generate_entries(
                    works,
                    keywords=keywords,
                    theme=theme,
                    mode=gen_mode,
                    config=gen_config,
                ),
            )
        )

    return OutputDocument(
        theme=theme,
        sections=sections,
        query=query,
        collected_count=collected_count,
        filter_policy="abstract任意",
        collected_at=date.today().isoformat(),
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Phase 1 CLI")
    parser.add_argument("--input", help="Path to input JSON")
    parser.add_argument("--out", help="Output directory")
    parser.add_argument("--openalex-test", action="store_true", help="Test OpenAlex API")
    parser.add_argument("--collect-test", action="store_true", help="Collect works from OpenAlex")
    parser.add_argument("--query", help="OpenAlex search query")
    parser.add_argument("--per-page", type=int, default=5, help="OpenAlex per-page")
    parser.add_argument("--max-pages", type=int, default=2, help="OpenAlex max pages")
    parser.add_argument("--mailto", help="OpenAlex mailto (optional)")
    parser.add_argument(
        "--gen-mode",
        choices=["simple", "structured", "llm", "plan_a", "plan_b"],
        default="simple",
        help="Generation mode for relation/summary/caution",
    )
    parser.add_argument("--llm-model", default="gpt-4o-mini", help="OpenAI model name")
    parser.add_argument(
        "--llm-max-items", type=int, default=20, help="Max items to send to LLM"
    )
    args = parser.parse_args(argv)

    if args.openalex_test:
        if not args.query:
            print("[error] --query is required with --openalex-test", file=sys.stderr)
            return 1
        return _run_openalex_test(args.query, args.per_page, args.mailto)

    if args.collect_test:
        if not args.input:
            print("[error] --input is required with --collect-test", file=sys.stderr)
            return 1
        return _run_collect_test(
            Path(args.input), args.per_page, args.max_pages, args.mailto
        )

    if not args.input or not args.out:
        print("[error] --input and --out are required", file=sys.stderr)
        return 1

    input_path = Path(args.input)
    out_dir = Path(args.out)

    try:
        payload = _load_json(input_path)
        theme = validate_and_normalize(payload)
    except InputValidationError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    # Write normalized input for traceability.
    out_payload = {
        "theme_overview": theme.theme_overview,
        "goal": theme.goal,
        "why_problem": theme.why_problem,
        "approach_type": theme.approach_type,
        "assumptions": theme.assumptions,
        "scope": {
            "field": theme.scope.field,
            "scale": theme.scope.scale,
            "time_range": theme.scope.time_range,
        },
        "keywords": {
            "include": theme.keywords.include,
            "exclude": theme.keywords.exclude,
        },
        "concern": theme.concern,
    }

    normalized_path = out_dir / "normalized_input.json"
    normalized_path.write_text(
        json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    config = CollectConfig(per_page=args.per_page, max_pages=args.max_pages, mailto=args.mailto)
    try:
        works = collect_and_filter(theme, config, max_count=500, require_abstract=False)
        classified = classify_stub(
            works,
            include_keywords=theme.keywords.include,
            exclude_keywords=theme.keywords.exclude,
        )
    except (OpenAlexError, OpenAlexParseError) as exc:
        print(f"[error] openalex: {exc}", file=sys.stderr)
        return 1

    print(f"[ok] collected: {len(works)}")
    query = _build_query(theme)
    gen_config = GenerationConfig(
        llm_model=args.llm_model, llm_max_items=args.llm_max_items
    )
    gen_mode = args.gen_mode
    if gen_mode == "plan_a":
        gen_mode = "structured"
    if gen_mode == "plan_b":
        gen_mode = "llm"

    doc = _build_document(
        theme,
        classified,
        query=query,
        collected_count=len(works),
        gen_mode=gen_mode,
        gen_config=gen_config,
    )
    md_path = out_dir / "brainstorm_output.md"
    export_markdown(doc, md_path)
    materials_path = _write_gemini_materials(out_dir, theme, classified)

    print(f"[ok] wrote {normalized_path}")
    print(f"[ok] wrote {md_path}")
    print(f"[ok] wrote {materials_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
