"""F-29 (first half) live probe: same fetched pool, old key (score only) vs new key (tier, score).

Replays seihai's 2026-09-18 r05 byrepo call (keywords / pool 40 / count 4) against the real
GitHub API. Only GitHub is contacted (no OpenAlex quota is used).
Usage: python scripts/f29_tier_probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_server import _build_theme_input  # noqa: E402
from src.pipeline.git_collect import GitCollectConfig  # noqa: E402
from src.pipeline.hf_collect import HFCollectConfig  # noqa: E402
from src.pipeline.track_a import anchor_rank_key, collect_track_a_works  # noqa: E402

ARGS = {
    "theme_overview": "A/B の挑戦者が現職の行動上のクローンになっており比較が決着しない。"
                      "実現した意思決定の重なりで候補を admission 段階で拒否する実装、"
                      "生成器に低相関制約を課す実装を探す。挑戦者と現職の約定系列を同じ市場データ上で"
                      "突き合わせ、エントリーとエグジットの一致率や損益系列の相関が閾値を超える候補は"
                      "着席させない。あわせて、多様性探索（novelty search や quality diversity）の"
                      "ように行動記述子の空間で既存戦略から離れた候補を供給する生成器を、実装として"
                      "持っているリポジトリを知りたい。バックテスト基盤やポートフォリオ相関の計算も対象。",
    "goal": "行動重複による admission 拒否と、行動が脱相関した候補の生成器の実装アンカー",
    "why_problem": "クローン同士の A/B は原理的に決着しない",
    "keywords_include": ["novelty-search", "behavioral-diversity", "strategy-backtest",
                         "portfolio-correlation", "ab-testing"],
    "assumptions": ["挑戦者と現職は同じ市場データ上で約定系列を比較できる",
                    "行動の重なりは構造の類似度では測れない"],
    "scope_field": "quantitative finance",
}
COUNT, POOL = 4, 40


def main() -> None:
    theme = _build_theme_input(ARGS)
    works = collect_track_a_works(theme, sources=["github"],
                                  git_config=GitCollectConfig(per_page=POOL, max_repos=POOL),
                                  hf_config=HFCollectConfig(limit=POOL, max_works=POOL),
                                  on_error=lambda s, e: print(f"[error] {s}: {e}"))
    old = sorted(works, key=lambda w: w.source_meta.get("anchor_rank_score", 0), reverse=True)
    new = sorted(works, key=anchor_rank_key, reverse=True)
    zero = sum(1 for w in works if w.source_meta.get("relevance_tier") == 0)
    print(f"pool={len(works)}  zero-match={zero}  matching={len(works) - zero}")
    for label, ranked in (("before (score only)", old), ("after (tier, score)", new)):
        print(f"\n== {label}: top {COUNT} ==")
        for i, w in enumerate(ranked[:COUNT], 1):
            m = w.source_meta
            print(f"{i}. {w.id}  rel={m.get('relevance')}  Rel={m.get('reliability_score')}"
                  f"  score={m.get('anchor_rank_score')}  tier={m.get('relevance_tier')}")
    head_old = sum(1 for w in old[:COUNT] if w.source_meta.get("relevance_tier") == 0)
    head_new = sum(1 for w in new[:COUNT] if w.source_meta.get("relevance_tier") == 0)
    print(f"\nzero-match anchors in the returned top {COUNT}: before {head_old} -> after {head_new}")


if __name__ == "__main__":
    main()
