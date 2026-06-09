"""Stdio-based MCP Server for the entire "by" series (byrepo, byserendipity, bynote)."""

from __future__ import annotations

import io
import json
import sys
import traceback
from typing import Any, Dict, List, Optional

from src.core.input_schema import validate_and_normalize
from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.classify import select_track_b
from src.pipeline.collect import CollectConfig, collect_track_b
from src.pipeline.concept_distance import build_theme_profile
from src.pipeline.generate import GenerationConfig, fill_track_entries
from src.pipeline.git_collect import GitCollectConfig, collect_track_a_git_works


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
        "time_range": args.get("scope_time_range") or "recent"
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
                        "scope_time_range": {"type": "string", "description": "Time range.", "default": "recent"},
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
                        "scope_time_range": {"type": "string", "description": "Time range.", "default": "recent"},
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
