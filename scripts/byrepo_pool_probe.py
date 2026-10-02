"""byrepo pool probe: replay seihai's 2026-10-02 r05 byrepo call against the real GitHub API.

Every GitHub response is cached on disk (``--cache DIR``), so the pool is fetched once and
re-ranked offline afterwards (unauthenticated core quota is 60 req/h and a pool of 30 costs
60: README + issues per repository). Only GitHub is contacted (no OpenAlex quota is used).

Usage: python scripts/byrepo_pool_probe.py --cache <dir> [--offline] [--mcp] [--fair-share] [--list] [--pool 30] [--count 4]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.github.client import GitHubClient, GitHubError  # noqa: E402
from src.mcp_server import _build_theme_input  # noqa: E402
from src.pipeline.git_collect import GitCollectConfig  # noqa: E402
from src.pipeline.track_a import anchor_rank_key, collect_track_a_works  # noqa: E402

ARGS = {
    "theme_overview": "Trend-following entries defined as state predicates (price versus a moving "
                      "average) suffer a stop-and-reverse whipsaw: the move that triggers the "
                      "stop-loss simultaneously satisfies the opposite-side entry condition. "
                      "Looking for implementations that suppress it with hysteresis bands, dead "
                      "time, or re-arm conditions after a stop, and that charge for it at selection.",
    "goal": "implementation anchors for whipsaw suppression (hysteresis band, re-arm after SL)",
    "why_problem": "the stop-and-reverse whipsaw erases the trend-following edge",
    "keywords_include": ["whipsaw", "hysteresis", "trend-following", "regime-filter", "backtesting"],
    "assumptions": ["entries are state predicates on price versus a moving average",
                    "the stop distance exceeds the typical deviation from the moving average"],
    "scope_field": "quantitative finance",
}


class CachingGitHubClient(GitHubClient):
    """Disk cache keyed by (path, params); failures are counted, never cached."""

    def __init__(self, cache_dir: Path, offline: bool = False) -> None:
        super().__init__()
        self.cache_dir = cache_dir
        self.offline = offline
        self.live_calls = 0
        self.cache_hits = 0
        self.failures: Dict[str, int] = {}
        cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        key = hashlib.sha1(json.dumps([path, params or {}], sort_keys=True).encode()).hexdigest()
        file = self.cache_dir / f"{key}.json"
        if file.exists():
            self.cache_hits += 1
            return json.loads(file.read_text(encoding="utf-8"))
        kind = path.rsplit("/", 1)[-1]
        if self.offline:
            self.failures[kind] = self.failures.get(kind, 0) + 1
            raise GitHubError(f"offline: {path} not cached")
        try:
            payload = super().get(path, params)
        except GitHubError:
            self.failures[kind] = self.failures.get(kind, 0) + 1
            raise
        self.live_calls += 1
        file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--pool", type=int, default=30)
    ap.add_argument("--count", type=int, default=4)
    ap.add_argument("--mcp", action="store_true", help="print the byrepo MCP output itself")
    ap.add_argument("--chars", type=int, default=2500)
    ap.add_argument("--fair-share", action="store_true",
                    help="F-41-R: also search the crowded-out keywords on their own (opt-in)")
    ap.add_argument("--list", action="store_true", help="print every pooled repository")
    ns = ap.parse_args()

    theme = _build_theme_input(ARGS)
    gh = CachingGitHubClient(Path(ns.cache), offline=ns.offline)
    if ns.mcp:
        # The real byrepo path, with only the HTTP client swapped for the cached one.
        import src.pipeline.git_collect as git_collect
        from src.mcp_server import StdinMcpServer
        git_collect.GitHubClient = lambda *a, **k: gh
        result = StdinMcpServer()._execute_byrepo(
            {**ARGS, "structured": True, "sources": ["github"],
             "track_a_count": ns.count, "track_a_pool_size": ns.pool,
             "keyword_fair_share": ns.fair_share})
        print(f"live_calls={gh.live_calls}  cache_hits={gh.cache_hits}  failures={gh.failures}\n")
        print(result["content"][0]["text"][:ns.chars])
        return
    legs: list = []
    works = collect_track_a_works(
        theme, sources=["github"],
        git_config=GitCollectConfig(per_page=ns.pool, max_repos=ns.pool,
                                    keyword_fair_share=ns.fair_share),
        github_client=gh, on_error=lambda s, e: print(f"[error] {s}: {e}"),
        git_search_stats=legs)
    ranked = sorted(works, key=anchor_rank_key, reverse=True)
    print(f"pool={len(works)}  live_calls={gh.live_calls}  cache_hits={gh.cache_hits}  failures={gh.failures}")
    for leg in legs:
        print(f"  leg {leg['label']}: total={leg['total_count']} returned={leg['returned']} "
              f"seated={leg['seated']} {leg['error']}")
    for kw in ARGS["keywords_include"]:
        hit = [w for w in works if any(m.get("keyword") == kw for m in w.source_meta.get("theme_fit_matched") or [])]
        strong = sum(1 for w in hit if any(m.get("keyword") == kw and m.get("where") != "readme"
                                           for m in w.source_meta["theme_fit_matched"]))
        print(f"  {kw}: {len(hit)}/{len(works)} (name/description/topics {strong})")
    print(f"\n== top {ns.count} ==")
    for i, w in enumerate(ranked[:ns.count], 1):
        m = w.source_meta
        kws = ",".join(x["keyword"] for x in m.get("theme_fit_matched") or [])
        print(f"{i}. {w.title}  rel={m.get('relevance')}  Rel={m.get('reliability_score')}"
              f"  score={m.get('anchor_rank_score')}  matched=[{kws}]  leg={m.get('search_leg')}")
    if ns.list:
        print()
        print("== pool (ranked) ==")
        for i, w in enumerate(ranked, 1):
            m = w.source_meta
            kws = ",".join(f"{x['keyword']}:{x['credit']}" for x in m.get("theme_fit_matched") or [])
            desc = " ".join((w.abstract or "").split())[:70]
            print(f"{i:>2}. [{m.get('search_leg')}] {w.title} *{w.cited_by_count} rel={m.get('relevance')} "
                  f"Rel={m.get('reliability_score')} score={m.get('anchor_rank_score')} [{kws}] :: {desc}")


if __name__ == "__main__":
    main()
