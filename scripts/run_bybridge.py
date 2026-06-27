"""Run the bybridge (citation 2-hop) flow from a theme JSON file.

bybridge collects near-field seed papers for the theme from OpenAlex, builds a
bridge pool from their shared references, and returns cross-domain papers that
cite the same bridges but live outside the seeds' home (L0) domain.

Key handling:
  - No OPENAI_API_KEY / ANTHROPIC_API_KEY set  -> key-free `raw_only` path
    (OpenAlex only; deterministic ranking, optional 4-part structured assembly).
  - LLM key present and --llm passed            -> full LLM selection + 4-part
    generation path (purpose x mechanism scoring).

Network: requires outbound HTTPS to api.openalex.org. In sandboxed/egress-
policy environments that host may be blocked (the run then reports a clean
"no seeds / request failed" instead of producing results) — allow it in the
environment's network policy to get real results.

Examples (run from repo root):
  python scripts/run_bybridge.py data/samples/theme_military_c2_multiagent.json
  python scripts/run_bybridge.py <theme.json> --raw                 # raw ranked list
  python scripts/run_bybridge.py <theme.json> --bridge-count 5 --seed-count 20
  python scripts/run_bybridge.py <theme.json> --llm                 # full LLM path (needs key)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.mcp_server import StdinMcpServer  # noqa: E402


def _flatten_theme(payload: dict) -> dict:
    """Map a canonical theme JSON (nested scope/keywords) onto the flat MCP args."""
    scope = payload.get("scope") or {}
    keywords = payload.get("keywords") or {}
    return {
        "theme_overview": payload.get("theme_overview"),
        "goal": payload.get("goal"),
        "why_problem": payload.get("why_problem"),
        "approach_type": payload.get("approach_type") or "application",
        "assumptions": payload.get("assumptions") or [],
        "scope_field": scope.get("field") or "",
        "scope_scale": scope.get("scale") or "small",
        "scope_time_range": scope.get("time_range") or "last_10_years",
        "keywords_include": keywords.get("include") or [],
        "keywords_exclude": keywords.get("exclude") or [],
        "concern": payload.get("concern"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Run bybridge (citation 2-hop) from a theme JSON")
    ap.add_argument("theme", help="path to a theme JSON (canonical nested format)")
    ap.add_argument("--bridge-count", type=int, default=5, help="max bridge-derived entries to return")
    ap.add_argument("--seed-count", type=int, default=20, help="near-field seed papers used to build the bridge pool")
    ap.add_argument("--raw", action="store_true", help="force raw ranked list (no structured 4-part assembly)")
    ap.add_argument("--llm", action="store_true", help="use the full LLM selection/generation path (needs an API key)")
    ap.add_argument("--llm-model", default="gpt-4o-mini", help="LLM model when --llm is set")
    args = ap.parse_args()

    payload = json.loads(Path(args.theme).read_text(encoding="utf-8"))
    theme_args = _flatten_theme(payload)

    has_key = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
    use_llm = args.llm and has_key
    if args.llm and not has_key:
        print("[warn] --llm requested but no OPENAI_API_KEY/ANTHROPIC_API_KEY set; falling back to key-free raw_only.\n")

    theme_args.update({
        "bridge_count": args.bridge_count,
        "seed_count": args.seed_count,
        "raw_only": not use_llm,
        "structured": (not use_llm) and (not args.raw),  # nice 4-part doc unless --raw
        "llm_model": args.llm_model,
    })

    mode = "LLM (select+generate)" if use_llm else ("raw_only+structured" if theme_args["structured"] else "raw_only (ranked list)")
    print(f"# bybridge — mode: {mode}\n")

    server = StdinMcpServer()
    result = server.handle_tool_call("bybridge_collect", theme_args)
    for block in result.get("content", []):
        print(block.get("text", ""))
    if result.get("isError"):
        sys.exit(1)


if __name__ == "__main__":
    main()
