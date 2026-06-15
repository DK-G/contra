"""Stdio-based MCP Server for the entire "by" series (byrepo, byserendipity, bynote, bybridge)."""

from __future__ import annotations

import io
import json
import sys
import traceback
from typing import Any, Dict, List, Optional

from src.core.input_schema import validate_and_normalize
from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.classify import select_track_b
from src.pipeline.collect import (
    CollectConfig,
    _bridge_pool_from_seeds,
    collect_and_filter,
    collect_citation_candidates,
    collect_track_b,
)
from src.pipeline.concept_distance import build_theme_profile
from src.pipeline.delegate import assemble_keyless_bridge_document, finalize_delegated_document
from src.pipeline.generate import GenerationConfig, fill_track_entries
from src.pipeline.git_collect import GitCollectConfig, collect_track_a_git_works
from src.core.output_spec import render_markdown


def _log(msg: str) -> None:
    sys.stderr.write(f"[mcp-server] {msg}\n")
    sys.stderr.flush()


def _make_error_response(rpc_id: Optional[Any], code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": err
    }


def _make_result_response(rpc_id: Any, result: Any) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "result": result
    }


def _build_theme_input(args: Dict[str, Any]) -> ThemeInput:
    """Helper to convert flat MCP arguments into a ThemeInput model."""
    scope_data = {
        "field": args.get("scope_field") or "",
        "scale": args.get("scope_scale") or "small",
        "time_range": args.get("scope_time_range") or "last_10_years"
    }
    keywords_data = {
        "include": args.get("keywords_include") or [],
        "exclude": args.get("keywords_exclude") or []
    }
    raw_payload = {
        "theme_overview": args.get("theme_overview"),
        "goal": args.get("goal"),
        "why_problem": args.get("why_problem"),
        "approach_type": args.get("approach_type") or "application",
        "assumptions": args.get("assumptions") or [],
        "scope": scope_data,
        "keywords": keywords_data,
        "concern": args.get("concern")
    }
    return validate_and_normalize(raw_payload)


class StdinMcpServer:
    def __init__(self) -> None:
        self.initialized = False

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "byserendipity_discover",
                "description": "Run the Track B serendipity pipeline to discover far-domain scientific papers containing structural causal/Purpose-Mechanism mapping matching the input theme.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "theme_overview": {"type": "string", "description": "Overview of the research theme (3-6 sentences)."},
                        "goal": {"type": "string", "description": "What goal or output you want to achieve."},
                        "why_problem": {"type": "string", "description": "Why this is a hard problem or bottleneck."},
                        "approach_type": {"type": "string", "description": "Type of approach (e.g., theory, experiment, system-building, application).", "default": "application"},
                        "assumptions": {"type": "array", "items": {"type": "string"}, "description": "Current assumptions or working hypotheses."},
                        "scope_field": {"type": "string", "description": "Core field of study."},
                        "scope_scale": {"type": "string", "description": "Scale of study.", "default": "small"},
                        "scope_time_range": {"type": "string", "description": "Time range (last_10_years or no_limit).", "default": "last_10_years"},
                        "keywords_include": {"type": "array", "items": {"type": "string"}, "description": "Include keywords."},
                        "keywords_exclude": {"type": "array", "items": {"type": "string"}, "description": "Exclude keywords."},
                        "concern": {"type": "string", "description": "Specific concern or failure mode."},
                        "track_b_count": {"type": "integer", "description": "Maximum number of serendipitous connections to return.", "default": 1},
                        "llm_model": {"type": "string", "description": "LLM model for classification/generation.", "default": "gpt-4o-mini"},
                        "output_floor": {"type": "number", "description": "Lower floor for quality filtering (set to 0.0 to return best fallback).", "default": 0.0}
                    },
                    "required": ["theme_overview", "goal", "why_problem"]
                }
            },
            {
                "name": "byrepo_search",
                "description": "Run the Track A Git practical-anchors pipeline to discover functional GitHub repositories matching the theme, evaluated and ranked by the 4-pillar reliability score.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "theme_overview": {"type": "string", "description": "Overview of the research theme."},
                        "goal": {"type": "string", "description": "What goal or output you want to achieve."},
                        "why_problem": {"type": "string", "description": "Why this is a hard problem or bottleneck."},
                        "approach_type": {"type": "string", "description": "Type of approach.", "default": "application"},
                        "assumptions": {"type": "array", "items": {"type": "string"}, "description": "Current assumptions or working hypotheses."},
                        "scope_field": {"type": "string", "description": "Core field of study."},
                        "scope_scale": {"type": "string", "description": "Scale of study.", "default": "small"},
                        "scope_time_range": {"type": "string", "description": "Time range (last_10_years or no_limit).", "default": "last_10_years"},
                        "keywords_include": {"type": "array", "items": {"type": "string"}, "description": "Include keywords."},
                        "keywords_exclude": {"type": "array", "items": {"type": "string"}, "description": "Exclude keywords."},
                        "concern": {"type": "string", "description": "Specific concern or failure mode."},
                        "track_a_count": {"type": "integer", "description": "Maximum number of practical repositories to return.", "default": 3}
                    },
                    "required": ["theme_overview", "goal", "why_problem"]
                }
            },
            {
                "name": "bynote_link_concepts",
                "description": "Analyze a draft idea/note text, extract core concepts, and provide bridging hypotheses or semantic links to other domains.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "note_content": {"type": "string", "description": "The raw text of the note or idea draft to analyze."},
                        "theme_overview": {"type": "string", "description": "Optional background theme to align the note against."}
                    },
                    "required": ["note_content"]
                }
            },
            {
                "name": "bybridge_collect",
                "description": "Run the citation 2-hop bridge flow: collect near-field seed papers for the theme, build a bridge pool from their shared references, and return cross-domain papers that cite the same bridges but live outside the seeds' home (L0) domain.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "theme_overview": {"type": "string", "description": "Overview of the research theme (3-6 sentences)."},
                        "goal": {"type": "string", "description": "What goal or output you want to achieve."},
                        "why_problem": {"type": "string", "description": "Why this is a hard problem or bottleneck."},
                        "approach_type": {"type": "string", "description": "Type of approach (e.g., theory, experiment, system-building, application).", "default": "application"},
                        "assumptions": {"type": "array", "items": {"type": "string"}, "description": "Current assumptions or working hypotheses."},
                        "scope_field": {"type": "string", "description": "Core field of study."},
                        "scope_scale": {"type": "string", "description": "Scale of study.", "default": "small"},
                        "scope_time_range": {"type": "string", "description": "Time range (last_10_years or no_limit).", "default": "last_10_years"},
                        "keywords_include": {"type": "array", "items": {"type": "string"}, "description": "Include keywords."},
                        "keywords_exclude": {"type": "array", "items": {"type": "string"}, "description": "Exclude keywords."},
                        "concern": {"type": "string", "description": "Specific concern or failure mode."},
                        "bridge_count": {"type": "integer", "description": "Maximum number of bridge-derived entries to return after LLM selection.", "default": 3},
                        "seed_count": {"type": "integer", "description": "Number of near-field seed papers used to build the bridge pool.", "default": 20},
                        "raw_only": {"type": "boolean", "description": "If true, skip LLM selection/generation and return the raw cross-domain candidate list (no API key needed beyond OpenAlex).", "default": False},
                        "structured": {"type": "boolean", "description": "When raw_only is true, format the deterministic bridge candidates into the full 4-part Track B document (key-free structured assembly; no LLM). The agent can then refine the prose/scores.", "default": False},
                        "llm_model": {"type": "string", "description": "LLM model for selection/generation when raw_only is false.", "default": "gpt-4o-mini"},
                        "output_floor": {"type": "number", "description": "Lower floor for quality filtering (set to 0.0 to return best fallback).", "default": 0.0}
                    },
                    "required": ["theme_overview", "goal", "why_problem"]
                }
            },
            {
                "name": "delegate_finalize",
                "description": (
                    "Delegation post-gate (stage c): the CALLING AGENT scores cross-domain "
                    "candidates with its own inference (no contra API key), then sends them here. "
                    "Contra deterministically re-applies the hard floors (anomaly purpose_sim<0.20 / "
                    "near-domain mechanism cap / serendipity / hollow structural_depth<0.50 / percentile "
                    "/ output_floor / fallback / M3) and returns the rendered Track B markdown. "
                    "Whatever the agent claims, gate violations are dropped here. No LLM is called."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "theme_overview": {"type": "string"},
                        "goal": {"type": "string"},
                        "why_problem": {"type": "string"},
                        "approach_type": {"type": "string", "default": "experiment"},
                        "assumptions": {"type": "array", "items": {"type": "string"}},
                        "scope_field": {"type": "string"},
                        "scope_scale": {"type": "string", "default": "small"},
                        "scope_time_range": {"type": "string", "default": "last_10_years"},
                        "keywords_include": {"type": "array", "items": {"type": "string"}},
                        "keywords_exclude": {"type": "array", "items": {"type": "string"}},
                        "concern": {"type": "string"},
                        "count": {"type": "integer", "description": "Max entries to emit (cap, not target).", "default": 1},
                        "output_floor": {"type": "number", "description": "Output-quality floor for serendipity.", "default": 0.35},
                        "emit_fallback": {"type": "boolean", "description": "If false, a run with nothing above output_floor reports saturation instead of a weak single-best (M3).", "default": True},
                        "candidates": {
                            "type": "array",
                            "description": (
                                "Agent-scored candidates. Each item echoes contra's candidate material "
                                "(id, title, abstract, year, venue, doi, cited_by_count, concepts, "
                                "concept_tags[{name,level,score}], referenced_works) AND carries the agent's "
                                "scoring: purpose_sim (0-1), mechanism_dist (0-1), optional structural_depth "
                                "(0-1) and has_causal_pm (bool), connection_label, serendipity_rationale, and "
                                "optional relationship/summary/caution prose."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "purpose_sim": {"type": "number"},
                                    "mechanism_dist": {"type": "number"},
                                    "structural_depth": {"type": "number"},
                                    "has_causal_pm": {"type": "boolean"},
                                    "connection_label": {"type": "string"},
                                    "serendipity_rationale": {"type": "string"}
                                },
                                "required": ["id", "purpose_sim", "mechanism_dist"]
                            }
                        }
                    },
                    "required": ["theme_overview", "goal", "why_problem", "candidates"]
                }
            }
        ]

    def handle_tool_call(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Routes and executes tool calls, capturing stdout to prevent protocol corruption."""
        buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buffer

        try:
            if name == "byserendipity_discover":
                result = self._execute_byserendipity(args)
            elif name == "byrepo_search":
                result = self._execute_byrepo(args)
            elif name == "bynote_link_concepts":
                result = self._execute_bynote(args)
            elif name == "bybridge_collect":
                result = self._execute_bybridge(args)
            elif name == "delegate_finalize":
                result = self._execute_delegate_finalize(args)
            else:
                raise ValueError(f"Unknown tool: {name}")
            
            # Add stdout logs if there are any, for tracing
            sys.stdout = old_stdout
            console_log = buffer.getvalue()
            if console_log:
                _log(f"Captured logs during tool execute:\n{console_log}")
            return result
        except Exception as e:
            sys.stdout = old_stdout
            _log(f"Exception during tool execution: {traceback.format_exc()}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error executing tool {name}: {str(e)}\n\nDetails:\n{traceback.format_exc()}"
                    }
                ],
                "isError": True
            }

    def _execute_byserendipity(self, args: Dict[str, Any]) -> Dict[str, Any]:
        theme = _build_theme_input(args)
        model = args.get("llm_model") or "gpt-4o-mini"
        target_count = args.get("track_b_count") or 1
        output_floor = args.get("output_floor") if args.get("output_floor") is not None else 0.0

        # Run pipeline
        _log("Byserendipity: collecting candidates...")
        works = collect_track_b(theme, CollectConfig(), model=model)
        
        # Build theme profile & citation expansion
        _log("Byserendipity: classifying and selecting serendipity candidates...")
        theme_profile = build_theme_profile(works)
        select_diag: dict = {}
        entries = select_track_b(
            works, theme, model=model, count=target_count,
            gate=0.0, use_llm=True, theme_profile=theme_profile,
            struct_depth_gate=0.0, output_floor=output_floor,
            vote_k=1, emit_fallback=True, diag=select_diag
        )
        
        if not entries:
            return {
                "content": [{"type": "text", "text": "テーマ飽和判定：条件を満たす遠ドメイン論文が見つかりませんでした。"}],
                "isError": False
            }

        # Fill text
        _log("Byserendipity: generating text for entries...")
        entries = fill_track_entries(entries, GenerationConfig(llm_model=model), theme=theme, mode="llm")
        
        # Build markdown response
        lines = []
        for i, entry in enumerate(entries, 1):
            lines.append(f"### {i}. {entry.work.title}")
            lines.append(f"- **接続点**: {entry.label}")
            lines.append(f"- **セレンディピティ・スコア**: {entry.serendipity_score:.2f} (距離: {entry.distance_score:.2f} / 構造: {entry.structure_score:.2f})")
            lines.append(f"- 年: {entry.work.year} | 掲載: {entry.work.venue} | 被引用: {entry.work.cited_by_count}")
            lines.append(f"- リンク: {entry.work.id}")
            lines.append("")
            lines.append(f"1) 概要: {entry.abstract_summary}")
            lines.append(f"2) 関連性: {entry.relationship}")
            lines.append(f"3) 役に立つ可能性の仮説: {entry.usefulness_hypothesis}")
            lines.append(f"4) 注意点: {entry.caution}")
            lines.append("")

        return {
            "content": [
                {
                    "type": "text",
                    "text": "\n".join(lines)
                }
            ],
            "isError": False
        }

    def _execute_byrepo(self, args: Dict[str, Any]) -> Dict[str, Any]:
        theme = _build_theme_input(args)
        target_count = args.get("track_a_count") or 3
        git_config = GitCollectConfig(per_page=target_count * 2, max_repos=target_count * 2)

        _log("Byrepo: collecting Git repositories...")
        works = collect_track_a_git_works(theme, git_config)
        
        if not works:
            return {
                "content": [{"type": "text", "text": "条件に合致するGitHubリポジトリが見つかりませんでした。"}],
                "isError": False
            }

        # Select & rank works based on reliability score
        works = sorted(works, key=lambda w: w.source_meta.get("reliability_score", 0), reverse=True)[:target_count]
        
        # Convert to entries / fill text
        from src.pipeline.classify import classify_track_a
        entries = classify_track_a(works, theme, model="gpt-4o-mini", count=target_count, use_llm=True)
        entries = fill_track_entries(entries, GenerationConfig(llm_model="gpt-4o-mini"), theme=theme, mode="llm")
        
        # Render markdown response
        lines = []
        for i, entry in enumerate(entries, 1):
            meta = entry.work.source_meta
            lines.append(f"### {i}. {entry.work.title}")
            lines.append(f"- **関係軸**: {entry.label} (関係度: {entry.relationship_level})")
            lines.append(f"- **Reliability Score**: {meta.get('reliability_score', 0)} "
                         f"(Impl/Doc: {meta.get('impl_doc_score', 0)}, LMA: {meta.get('lma_score', 0)}, "
                         f"Comm: {meta.get('community_score', 0)}, Sec: {meta.get('security_score', 0)})")
            lines.append(f"- 更新年: {entry.work.year} | 種別: {entry.work.venue} | stars: {entry.work.cited_by_count}")
            lines.append(f"- リンク: {entry.work.id}")
            lines.append("")
            lines.append(f"1) 概要: {entry.abstract_summary}")
            lines.append(f"2) 関連性: {entry.relationship}")
            lines.append(f"3) 役に立つ可能性の仮説: {entry.usefulness_hypothesis}")
            lines.append(f"4) 注意点: {entry.caution}")
            lines.append("")

        return {
            "content": [
                {
                    "type": "text",
                    "text": "\n".join(lines)
                }
            ],
            "isError": False
        }

    def _execute_bynote(self, args: Dict[str, Any]) -> Dict[str, Any]:
        note = args.get("note_content")
        theme_overview = args.get("theme_overview") or ""

        # Using lightweight LLM call to establish semantic connections
        from src.openai_client import responses_create, extract_output_text
        
        _log("Bynote: analyzing note concepts and suggesting semantic bridges...")
        
        system_prompt = (
            "あなたは知識アソシエーション・アナロジーの専門エージェントです。\n"
            "入力されたメモ（アイディアのドラフト）を分析し、以下の項目を日本語で簡潔に提示してください：\n"
            "1. メモの中核コンセプト（Purpose/Mechanismに分解）\n"
            "2. 類推可能な他の抽象的ドメインの例（2-3個、なぜ類推可能かも記述）\n"
            "3. 異なる前提を持ち込んでアイディアを跳躍させるための『問い（Serendipity Bridge）』"
        )
        if theme_overview:
            system_prompt += f"\nまた、背景テーマとして指定されている「{theme_overview}」との整合性や、そのテーマにこのメモを転用する際の接続ロジックも示してください。"

        payload = {
            "model": "gpt-4o-mini",
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"分析対象メモ:\n{note}"}
            ],
            "temperature": 0.5
        }
        
        resp = responses_create(payload)
        output_text = extract_output_text(resp)

        return {
            "content": [
                {
                    "type": "text",
                    "text": output_text
                }
            ],
            "isError": False
        }

    def _execute_bybridge(self, args: Dict[str, Any]) -> Dict[str, Any]:
        theme = _build_theme_input(args)
        model = args.get("llm_model") or "gpt-4o-mini"
        target_count = args.get("bridge_count") or 3
        seed_count = args.get("seed_count") or 20
        raw_only = bool(args.get("raw_only"))
        structured = bool(args.get("structured"))
        output_floor = args.get("output_floor") if args.get("output_floor") is not None else 0.0

        _log("Bybridge: collecting near-field seed papers...")
        seeds = collect_and_filter(theme, CollectConfig(), max_count=seed_count, require_abstract=True)
        if not seeds:
            return {
                "content": [{"type": "text", "text": "近傍シード論文が見つからず、bridge プールを構築できませんでした。キーワードを見直してください。"}],
                "isError": False
            }

        bridges = set(_bridge_pool_from_seeds(seeds, cap=50))

        _log("Bybridge: running citation 2-hop scan across the bridge pool...")
        cands = collect_citation_candidates(seeds, CollectConfig(), max_count=60)
        if not cands:
            return {
                "content": [{"type": "text", "text": f"citation 2-hop で交差候補が見つかりませんでした（シード {len(seeds)} 件 / bridge {len(bridges)} 本。ホームドメイン除外で全滅した可能性があります）。"}],
                "isError": False
            }

        def shared_bridge_count(work) -> int:
            return sum(1 for r in (work.referenced_works or []) if r in bridges)

        diag_line = f"収集診断: シード {len(seeds)} 件 / bridge プール {len(bridges)} 本 / 交差候補 {len(cands)} 件"

        if raw_only:
            if structured:
                # Stage (a) delegation path: key-free deterministic selection +
                # structured 4-part assembly (no LLM). See docs/research/mcp_subscription_delegation.md.
                _log("Bybridge: key-free structured assembly (no LLM)...")
                profile = build_theme_profile(seeds)
                doc = assemble_keyless_bridge_document(
                    theme, cands, set(bridges), profile=profile, count=target_count
                )
                md = render_markdown(doc)
                return {
                    "content": [{"type": "text", "text": f"{diag_line}\n\n{md}"}],
                    "isError": False
                }
            lines = [f"## Bybridge 交差候補（raw）", diag_line, ""]
            ranked = sorted(cands, key=shared_bridge_count, reverse=True)
            for i, w in enumerate(ranked[:max(target_count, 10)], 1):
                lines.append(f"{i}. {w.title}")
                lines.append(f"   - 共有bridge: {shared_bridge_count(w)}本 | 年: {w.year} | 掲載: {w.venue} | 被引用: {w.cited_by_count}")
                lines.append(f"   - リンク: {w.id}")
            return {
                "content": [{"type": "text", "text": "\n".join(lines)}],
                "isError": False
            }

        _log("Bybridge: selecting bridge-derived candidates (purpose x mechanism)...")
        theme_profile = build_theme_profile(seeds)
        select_diag: dict = {}
        entries = select_track_b(
            cands, theme, model=model, count=target_count,
            gate=0.0, use_llm=True, theme_profile=theme_profile,
            struct_depth_gate=0.0, output_floor=output_floor,
            vote_k=1, emit_fallback=True, diag=select_diag
        )
        if not entries:
            return {
                "content": [{"type": "text", "text": f"{diag_line}\n\nbridge 経由の交差候補はありましたが、選別ゲートを通過するものがありませんでした。raw_only=true で候補リストを直接確認できます。"}],
                "isError": False
            }

        _log("Bybridge: generating text for entries...")
        entries = fill_track_entries(entries, GenerationConfig(llm_model=model), theme=theme, mode="llm")

        lines = [diag_line, ""]
        for i, entry in enumerate(entries, 1):
            lines.append(f"### {i}. {entry.work.title}")
            lines.append(f"- **接続点**: {entry.label}")
            lines.append(f"- **共有bridge**: {shared_bridge_count(entry.work)}本")
            lines.append(f"- **セレンディピティ・スコア**: {entry.serendipity_score:.2f} (距離: {entry.distance_score:.2f} / 構造: {entry.structure_score:.2f})")
            lines.append(f"- 年: {entry.work.year} | 掲載: {entry.work.venue} | 被引用: {entry.work.cited_by_count}")
            lines.append(f"- リンク: {entry.work.id}")
            lines.append("")
            lines.append(f"1) 概要: {entry.abstract_summary}")
            lines.append(f"2) 関連性: {entry.relationship}")
            lines.append(f"3) 役に立つ可能性の仮説: {entry.usefulness_hypothesis}")
            lines.append(f"4) 注意点: {entry.caution}")
            lines.append("")

        return {
            "content": [{"type": "text", "text": "\n".join(lines)}],
            "isError": False
        }

    def _execute_delegate_finalize(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Stage (c): the calling agent already scored the candidates; contra re-applies
        # the deterministic hard floors (no LLM) and renders. See
        # docs/research/mcp_subscription_delegation.md.
        theme = _build_theme_input(args)
        materials = args.get("candidates") or []
        if not materials:
            return {
                "content": [{"type": "text", "text": "candidates が空です。エージェント採点済みの候補リストを渡してください。"}],
                "isError": False
            }
        count = int(args.get("count") or 1)
        output_floor = args.get("output_floor") if args.get("output_floor") is not None else 0.35
        emit_fallback = bool(args.get("emit_fallback", True))
        diag: dict = {}
        try:
            doc = finalize_delegated_document(
                materials, theme,
                count=count, output_floor=output_floor, emit_fallback=emit_fallback, diag=diag,
            )
        except ValueError as exc:
            return {"content": [{"type": "text", "text": f"委譲採点の検証に失敗: {exc}"}], "isError": True}

        entries = doc.sections[0].entries if doc.sections else []
        diag_line = (
            f"post-gate 診断: status={diag.get('status')} / 採点 {diag.get('scored', 0)} 件 / "
            f"anomaly {diag.get('anomaly', 0)} / hollow {diag.get('hollow', 0)} / "
            f"通過 {diag.get('passed', 0)} / 出力 {len(entries)}"
        )
        if not entries:
            return {
                "content": [{"type": "text", "text": f"{diag_line}\n\n決定論ゲートを通過した候補がありませんでした（飽和または全棄却）。"}],
                "isError": False
            }
        md = render_markdown(doc)
        return {
            "content": [{"type": "text", "text": f"{diag_line}\n\n{md}"}],
            "isError": False
        }

    def run(self) -> None:
        """Starts the main stdio loop listening for JSON-RPC messages."""
        _log("Stdio MCP Server started.")
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                
                request = json.loads(line)
                method = request.get("method")
                rpc_id = request.get("id")
                
                if method == "initialize":
                    self.initialized = True
                    result = {
                        "protocolVersion": request.get("params", {}).get("protocolVersion", "2024-11-05"),
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "contra-mcp",
                            "version": "0.1.0"
                        }
                    }
                    self._send_response(_make_result_response(rpc_id, result))
                    
                elif method == "notifications/initialized":
                    # Handshake complete notification
                    _log("Handshake completed successfully.")
                    
                elif method == "tools/list":
                    if not self.initialized:
                        self._send_response(_make_error_response(rpc_id, -32002, "Server not initialized"))
                        continue
                    
                    tools_list = self.list_tools()
                    self._send_response(_make_result_response(rpc_id, {"tools": tools_list}))
                    
                elif method == "tools/call":
                    if not self.initialized:
                        self._send_response(_make_error_response(rpc_id, -32002, "Server not initialized"))
                        continue
                    
                    params = request.get("params", {})
                    tool_name = params.get("name")
                    tool_args = params.get("arguments", {})
                    
                    _log(f"Handling tool call for: {tool_name}")
                    result = self.handle_tool_call(tool_name, tool_args)
                    self._send_response(_make_result_response(rpc_id, result))
                    
                elif method is not None:
                    # Unsupported method
                    self._send_response(_make_error_response(rpc_id, -32601, f"Method not found: {method}"))
                    
            except json.JSONDecodeError:
                self._send_response(_make_error_response(None, -32700, "Parse error"))
            except Exception as e:
                _log(f"Error in main loop: {traceback.format_exc()}")
                self._send_response(_make_error_response(None, -32603, f"Internal error: {str(e)}"))

    def _send_response(self, response: Dict[str, Any]) -> None:
        """Helper to send a JSON-RPC response, flushing stdout."""
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def run_mcp_server() -> None:
    server = StdinMcpServer()
    server.run()
