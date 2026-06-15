"""CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from src.core.input_schema import InputValidationError, validate_and_normalize
from src.core.models import OutputDocument, OutputSection, ThemeHistory
from src.openalex.client import OpenAlexClient, OpenAlexConfig, OpenAlexError
from src.openalex.parser import OpenAlexParseError, normalize_results
from src.pipeline.classify import (
    _STRUCT_DEPTH_GATE,
    classify_track_a,
    classify_track_b,
    select_track_b,
)
from src.pipeline.collect import (
    CollectConfig,
    Collector,
    _norm_doi,
    _norm_title,
    collect_and_filter,
    collect_citation_candidates,
    collect_track_b,
    filter_by_used_ids,
)
from src.pipeline.concept_distance import ThemeProfile, build_theme_profile
from src.pipeline.export import export_markdown
from src.pipeline.generate import GenerationConfig, fill_track_entries
from src.pipeline.git_collect import GitCollectConfig, collect_track_a_git_works
from src.pipeline.history import compute_theme_hash, load_history, save_history


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
    tokens = list(theme.keywords.include)
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


def _write_gemini_materials(
    out_dir: Path,
    theme,
    track_a_entries: list,
    track_b_entries: list,
) -> Path:
    theme_summary = _build_theme_summary(theme)
    lines: list[str] = []
    for entry in track_a_entries:
        payload = {
            "id": entry.work.id,
            "track": "A",
            "relationship_level": entry.relationship_level,
            "axis_label": entry.label,
            "input_theme_summary": theme_summary,
            "paper_metadata": {
                "title": entry.work.title,
                "abstract": entry.work.abstract,
                "url": entry.work.id,
                "doi": entry.work.doi,
                "year": entry.work.year,
                "venue": entry.work.venue,
                "concepts": entry.work.concepts,
                "cited_by_count": entry.work.cited_by_count,
            },
            "generated": {
                "summary": entry.abstract_summary,
                "relationship": entry.relationship,
                "usefulness_hypothesis": entry.usefulness_hypothesis,
                "caution": entry.caution,
            },
            "instruction": (
                "4部構成（概要・テーマとの関連性・役に立つ可能性の仮説・注意点）を各1〜2文で洗練させてください。"
                "言い換えを中心に構成し、語彙の重複を避けてください。"
            ),
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    for entry in track_b_entries:
        payload = {
            "id": entry.work.id,
            "track": "B",
            "connection_label": entry.label,
            "serendipity_score": entry.serendipity_score,
            "distance_score": entry.distance_score,
            "structure_score": entry.structure_score,
            "input_theme_summary": theme_summary,
            "paper_metadata": {
                "title": entry.work.title,
                "abstract": entry.work.abstract,
                "url": entry.work.id,
                "doi": entry.work.doi,
                "year": entry.work.year,
                "venue": entry.work.venue,
                "concepts": entry.work.concepts,
                "cited_by_count": entry.work.cited_by_count,
            },
            "generated": {
                "summary": entry.abstract_summary,
                "relationship": entry.relationship,
                "usefulness_hypothesis": entry.usefulness_hypothesis,
                "caution": entry.caution,
            },
            "instruction": (
                f"接続点ラベル「{entry.label}」が指す『関係構造』を起点に、4部構成（概要・関連性・役に立つ可能性の仮説・注意点）を洗練させてください。"
                "『役に立つ可能性の仮説』を中核に、課題枠と解決枠を並置すること。異なるドメインからの転用リスクを注意点に含めてください。"
            ),
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    out_path = out_dir / "gemini_materials.jsonl"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def _write_saturation_report(out_dir: Path, theme, track_b_works: list, diag: dict, args) -> int:
    """M3: emit an explicit saturation note when no Track B unit cleared the output floor.

    A depleted/saturated cycle should NOT pad the report with a single weak fallback paper —
    that reads as a finding when it isn't. We instead leave a short, honest marker so a periodic
    run is traceable, write no Gemini materials, and adopt nothing into history.
    """
    reason_label = {
        "no_qualified": f"スコア候補はあったが output_floor({args.output_floor}) を超える接続点が無し",
        "all_anomaly": "全候補が purpose 構造の整合を欠き棄却（有効スコア候補なし）",
        "all_hollow": "全候補が hollow（構造対応が表層的）と判定",
        "below_fallback_floor": "全候補がゲート未通過かつ fallback 閾値未満",
    }.get(diag.get("reason", ""), diag.get("reason", "良候補乏しい"))
    lines = [
        "# Contra — 今回はテーマ飽和（新規良候補が乏しい回）",
        "",
        f"- テーマ: {theme.theme_overview[:120]}",
        f"- 収集した Track B 候補: {len(track_b_works)} 件",
        f"- 判定: **{reason_label}**",
        f"- 内訳: scored={diag.get('scored', 0)} / anomaly={diag.get('anomaly', 0)} "
        f"/ hollow={diag.get('hollow', 0)} / passed={diag.get('passed', 0)} / qualified=0",
        "",
        "今回の周期では、テーマと十分に遠く構造的に噛み合う新規論文が見つかりませんでした。",
        "誤った弱い接続点で水増しレポートを出すことを避け、本回は **接続点 0 件** とします。",
        "（履歴は更新していません。次回以降の収集多様化／最新性補充で井戸が再生すれば再び成立します。）",
        "",
    ]
    md_path = out_dir / "brainstorm_output.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[info] M3: テーマ飽和と判定 → 飽和ノートを出力（弱fallback抑止・履歴不更新）")
    print(f"[ok] wrote {md_path}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Contra CLI")
    parser.add_argument("--input", help="Path to input JSON")
    parser.add_argument("--out", help="Output directory")
    parser.add_argument("--openalex-test", action="store_true", help="Test OpenAlex API")
    parser.add_argument("--collect-test", action="store_true", help="Collect works from OpenAlex")
    parser.add_argument("--query", help="OpenAlex search query")
    parser.add_argument("--per-page", type=int, default=50, help="OpenAlex per-page")
    parser.add_argument("--max-pages", type=int, default=4, help="OpenAlex max pages")
    parser.add_argument("--mailto", help="OpenAlex mailto (optional)")
    parser.add_argument(
        "--gen-mode",
        choices=["simple", "structured", "llm", "plan_a", "plan_b"],
        default="llm",
        help="Generation mode",
    )
    parser.add_argument("--llm-model", default="gpt-4o-mini", help="OpenAI model name")
    parser.add_argument("--llm-max-items", type=int, default=20, help="Max items for LLM generation")
    parser.add_argument("--no-history", action="store_true", help="Skip history deduplication")
    parser.add_argument("--history-dir", default="data/history", help="History directory")
    parser.add_argument("--single", action="store_true", help="MVP mode: output the single best Track B serendipity unit")
    parser.add_argument("--track-b-count", type=int, default=10, help="Max Track B entries (quality-gated)")
    parser.add_argument("--track-a-count", type=int, default=0, help="Track A anchor entries (0 = omit)")
    parser.add_argument(
        "--git-rich-signals",
        dest="git_rich_signals",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="Track A: fetch release-cadence + CI-health signals (Pillar 1 weight migration, A-RS2). "
        "Adds ~2 REST calls/repo; default auto-enables only when GITHUB_TOKEN is set.",
    )
    parser.add_argument("--serendipity-gate", type=float, default=0.25, help="Track B quality gate on structure x distance")
    parser.add_argument("--struct-depth-gate", type=float, default=_STRUCT_DEPTH_GATE, help="Track B hollow gate: min judge structural_depth (0-1); candidates below it are rejected as hollow (shared-category/lacks-systematicity). Default tracks the calibrated _STRUCT_DEPTH_GATE")
    parser.add_argument("--output-floor", type=float, default=0.35, help="Track B output-quality floor on serendipity; --track-b-count is a MAX cap and only units above this bar are emitted (thin themes return fewer strong units instead of padding)")
    parser.add_argument("--allow-weak-fallback", action="store_true", help="Track B saturation (M3): by default a run that yields NO unit above --output-floor reports 'テーマ飽和' instead of padding the report with a single weak fallback paper. Set this to restore the old single-best fallback behaviour")
    parser.add_argument("--score-votes", type=int, default=1, help="Track B self-consistency (R5): run the PM scoring + hollow judge K times and reduce by median/majority to stop borderline candidates flipping across the floor between runs. 1 = single pass (default); 3 = ~3x LLM cost for more stable scores")
    parser.add_argument("--fulltext", action="store_true", help="OA full-text補強 (opt-in, default off): for Track B candidates that are OA AND have a short abstract, fetch the OA full text (arXiv e-print first) and append a cleaned excerpt to the mechanism判定 input. Resolution is cached per paper id; serendipity score formula/thresholds are unchanged (input material only)")
    parser.add_argument("--fulltext-cache-dir", default="data/fulltext", help="Directory for per-paper full-text cache (gitignored). Re-runs reuse cached hits AND misses")
    parser.add_argument("--fulltext-max-abstract", type=int, default=280, help="Only fetch full text for OA candidates whose abstract is shorter than this many characters (無駄打ち防止)")
    parser.add_argument("--mcp", action="store_true", help="Launch Stdio MCP Server")
    args = parser.parse_args(argv)

    if args.mcp:
        from src.mcp_server import run_mcp_server
        run_mcp_server()
        return 0

    if args.openalex_test:

        if not args.query:
            print("[error] --query is required with --openalex-test", file=sys.stderr)
            return 1
        return _run_openalex_test(args.query, args.per_page, args.mailto)

    if args.collect_test:
        if not args.input:
            print("[error] --input is required with --collect-test", file=sys.stderr)
            return 1
        return _run_collect_test(Path(args.input), args.per_page, args.max_pages, args.mailto)

    if not args.input or not args.out:
        print("[error] --input and --out are required", file=sys.stderr)
        return 1

    input_path = Path(args.input)
    out_dir = Path(args.out)
    history_dir = Path(args.history_dir)

    try:
        payload = _load_json(input_path)
        theme = validate_and_normalize(payload)
    except InputValidationError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    out_payload = {
        "theme_overview": theme.theme_overview,
        "goal": theme.goal,
        "why_problem": theme.why_problem,
        "approach_type": theme.approach_type,
        "assumptions": theme.assumptions,
        "scope": {"field": theme.scope.field, "scale": theme.scope.scale, "time_range": theme.scope.time_range},
        "keywords": {"include": theme.keywords.include, "exclude": theme.keywords.exclude},
        "concern": theme.concern,
    }
    normalized_path = out_dir / "normalized_input.json"
    normalized_path.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    theme_hash = compute_theme_hash(theme.theme_overview)
    used_ids: set = set()
    used_titles: set = set()
    used_dois: set = set()
    history = None
    if not args.no_history:
        history = load_history(theme_hash, history_dir)
        used_ids = set(history.used_ids)
        used_titles = set(history.used_titles)
        used_dois = set(history.used_dois)
        if used_ids:
            print(f"[info] history: {len(used_ids)} used IDs / {len(used_titles)} titles / {len(used_dois)} DOIs will be excluded")

    gen_mode = args.gen_mode
    if gen_mode == "plan_a":
        gen_mode = "structured"
    if gen_mode == "plan_b":
        gen_mode = "llm"
    use_llm = gen_mode == "llm"

    config = CollectConfig(per_page=args.per_page, max_pages=args.max_pages, mailto=args.mailto)
    git_config = GitCollectConfig(
        per_page=max(args.track_a_count * 2, 10),
        max_repos=max(args.track_a_count * 2, 10),
        include_rich_signals=args.git_rich_signals,
    )

    # MVP (--single): the single best Track B serendipity unit. Track A is an optional anchor.
    track_b_target = 1 if args.single else args.track_b_count
    track_a_target = 0 if args.single else args.track_a_count

    track_a_works: list = []
    track_a_entries: list = []
    try:
        if track_a_target > 0:
            print("[info] collecting Track A Git practical anchors...")
            track_a_works = collect_track_a_git_works(theme, git_config)
            track_a_works = filter_by_used_ids(track_a_works, used_ids, used_titles, used_dois)
            print(f"[ok] Track A candidates: {len(track_a_works)}")

        print("[info] collecting Track B candidates (distant domain x theme anchor)...")
        track_b_works = collect_track_b(
            theme,
            config,
            model=args.llm_model,
            used_ids=used_ids,
            used_titles=used_titles,
            used_dois=used_dois,
        )
        print(f"[ok] Track B candidates: {len(track_b_works)}")
    except (OpenAlexError, OpenAlexParseError) as exc:
        print(f"[error] openalex: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[error] track-a git collect: {exc}", file=sys.stderr)
        return 1

    if track_a_target > 0:
        print("[info] classifying Track A...")
        track_a_entries = classify_track_a(
            track_a_works, theme, model=args.llm_model, count=track_a_target, use_llm=use_llm
        )
        print(f"[ok] Track A: {len(track_a_entries)} entries")

    # Build objective domain profile for near_domain_signal() in Track B selection.
    # Reuse Track A near-field works when available; otherwise collect a small set.
    theme_profile: Optional[ThemeProfile] = None
    if use_llm:
        profile_works = track_a_works if track_a_works else []
        if not profile_works:
            try:
                print("[info] 近傍論文を収集してドメインプロファイルを構築中...")
                profile_works = collect_and_filter(theme, config, max_count=20, require_abstract=True)
            except (OpenAlexError, OpenAlexParseError) as exc:
                print(f"[warn] domain profile collection failed: {exc}", file=sys.stderr)
                profile_works = []
        if profile_works:
            theme_profile = build_theme_profile(profile_works)
            if not theme_profile.is_empty():
                print(
                    f"[ok] ドメインプロファイル: L0/L1={len(theme_profile.l01)}概念, "
                    f"L2-L4={len(theme_profile.l234)}概念 ({len(profile_works)}件から)"
                )

        # Citation 2-hop: harvest cross-domain papers linked to the near-field seeds via shared
        # references (bridges), excluding the seeds' L0 home domain. Merged into the Track B pool
        # so downstream P/M scoring and gates stay unchanged (staged rollout step 1).
        if profile_works:
            try:
                print("[info] citation 2-hop で遠ドメイン候補を収集中...")
                cite_cands = collect_citation_candidates(
                    profile_works, config, max_count=60, used_ids=used_ids
                )
                existing_ids = {w.id for w in track_b_works} | used_ids
                existing_titles = {_norm_title(w.title) for w in track_b_works} | used_titles
                existing_dois = {_norm_doi(w.doi) for w in track_b_works if w.doi} | used_dois
                added = 0
                for w in cite_cands:
                    nt, nd = _norm_title(w.title), _norm_doi(w.doi)
                    if (w.id not in existing_ids and w.abstract
                            and not (nt and nt in existing_titles)
                            and not (nd and nd in existing_dois)):
                        existing_ids.add(w.id)
                        if nt:
                            existing_titles.add(nt)
                        if nd:
                            existing_dois.add(nd)
                        track_b_works.append(w)
                        added += 1
                print(f"[ok] citation 2-hop: +{added} 件 (Track B 候補 {len(track_b_works)} 件に統合)")
            except (OpenAlexError, OpenAlexParseError) as exc:
                print(f"[warn] citation 2-hop collection failed: {exc}", file=sys.stderr)

    # OA full-text補強 (opt-in). Runs BEFORE selection so the P/M mechanism scorer sees the
    # enriched text. Only OA + short-abstract Track B candidates are fetched (無駄打ち防止);
    # misses/hits are cached per id, and any failure falls back to the abstract-only path.
    if args.fulltext and use_llm and track_b_works:
        from src.fulltext import attach_fulltext, build_default_chain, needs_fulltext

        chain = build_default_chain(cache_dir=args.fulltext_cache_dir)
        targeted = [
            w for w in track_b_works
            if needs_fulltext(w, max_abstract_chars=args.fulltext_max_abstract)
        ]
        print(
            f"[info] 全文補強: OA×短abstract候補 {len(targeted)}/{len(track_b_works)} 件を "
            "arXiv で解決中 (1 req/3s)..."
        )
        ft_hits = 0
        for w in targeted:
            if attach_fulltext(w, chain.resolve(w)):
                ft_hits += 1
        print(f"[ok] 全文補強: {ft_hits} 件取得 (LaTeX e-print 要点を mechanism 判定入力に連結)")

    print("[info] Track B 選別中 (serendipity = purpose × mechanism, gated)...")
    select_diag: dict = {}
    track_b_entries = select_track_b(
        track_b_works, theme, model=args.llm_model,
        count=track_b_target, gate=args.serendipity_gate, use_llm=use_llm,
        theme_profile=theme_profile, struct_depth_gate=args.struct_depth_gate,
        output_floor=args.output_floor, vote_k=args.score_votes,
        emit_fallback=args.allow_weak_fallback, diag=select_diag,
    )
    print(f"[ok] Track B: {len(track_b_entries)} 件 (gate={args.serendipity_gate})")

    # M3: graceful degradation. When the run produced no unit above the output-quality floor
    # (theme saturated / no good NEW candidate this cycle), write an explicit saturation note
    # instead of a misleadingly thin report, and skip Gemini materials + history adoption.
    if not track_b_entries and select_diag.get("status") == "saturated":
        return _write_saturation_report(out_dir, theme, track_b_works, select_diag, args)

    gen_config = GenerationConfig(llm_model=args.llm_model, llm_max_items=args.llm_max_items)

    if track_a_entries:
        print("[info] generating Track A text...")
        track_a_entries = fill_track_entries(track_a_entries, gen_config, theme=theme, mode=gen_mode)
    print("[info] generating Track B text (4-part)...")
    track_b_entries = fill_track_entries(track_b_entries, gen_config, theme=theme, mode=gen_mode)

    sections = [
        OutputSection(
            title=f"Track B: 接続点フィーチャー（{len(track_b_entries)}本）",
            track="B",
            entries=track_b_entries,
        ),
    ]
    if track_a_entries:
        sections.append(
            OutputSection(
                title=f"Track A: Practical Anchors（{len(track_a_entries)}件）",
                track="A",
                entries=track_a_entries,
            )
        )

    doc = OutputDocument(
        theme=theme,
        sections=sections,
        query=_build_query(theme),
        collected_count=len(track_a_works) + len(track_b_works),
        filter_policy="abstractあり必須・撤回論文除外・質ゲート",
        collected_at=date.today().isoformat(),
    )

    md_path = out_dir / "brainstorm_output.md"
    export_markdown(doc, md_path)
    materials_path = _write_gemini_materials(out_dir, theme, track_a_entries, track_b_entries)

    if not args.no_history:
        adopted = track_a_entries + track_b_entries
        adopted_ids = [e.work.id for e in adopted]
        adopted_titles = [_norm_title(e.work.title) for e in adopted]
        adopted_dois = [_norm_doi(e.work.doi) for e in adopted]
        save_history(
            history or ThemeHistory(theme_hash=theme_hash, used_ids=[], generated_at=""),
            adopted_ids,
            adopted_titles,
            adopted_dois,
            history_dir,
        )
        print(f"[ok] saved history: {len(adopted_ids)} IDs → {history_dir}/{theme_hash}.json")

    print(f"[ok] wrote {normalized_path}")
    print(f"[ok] wrote {md_path}")
    print(f"[ok] wrote {materials_path}")
    return 0


if __name__ == "__main__":
    code = main(sys.argv[1:])
    try:
        from src.openai_client import get_usage
        u = get_usage()
        if u["calls"]:
            print(
                f"[usage] LLM calls={u['calls']} input_tokens={u['input_tokens']} "
                f"output_tokens={u['output_tokens']} (reasoning={u['reasoning_tokens']}, "
                f"cached_input={u['cached_input_tokens']})"
            )
    except Exception:
        pass
    raise SystemExit(code)
