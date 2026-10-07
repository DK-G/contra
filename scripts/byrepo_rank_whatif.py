"""byrepo ranking what-if (F-43): re-rank cached pools under candidate relevance rules.

Reads the pools ``byrepo_pool_probe.py`` cached (no network), so one evening's GitHub quota buys
any number of ranking comparisons. For each theme it prints the returned top N under:

  A  default pool      x current ranking        (what byrepo returns today)
  B  fair-share pool   x current ranking        (F-41-R alone)
  C  default pool      x rarity-weighted coverage
  D  fair-share pool   x rarity-weighted coverage
  E  fair-share pool   x rarity-weighted coverage, a keyword matched alone keeps equal weight

Rarity weight of keyword k = log(OR total / k's own total), floored at a small positive value and
normalised to sum 1 (the totals are the ones GitHub returns for the F-41-R keyword searches).

With ``--floors`` it prints instead the floor grid (F-29, second half): the relevance floor in
rank = Reliability x (floor + (1 - floor) x relevance), today 0.35, crossed with the pool
(default / fair-share) and the relevance rule (equal coverage / rarity-weighted).

Usage: python scripts/byrepo_rank_whatif.py [--floors 0.35,0.2,0.1,0] <name>:<pool>[:<as-of>] ...
  e.g. python scripts/byrepo_rank_whatif.py 2026-10-02:30:2026-10-06 2026-10-06:10:2026-10-06
  <name> selects output/byrepo_pool_cache/<name> and scripts/byrepo_probe_themes/<name>.json
  (2026-10-02 uses the probe's built-in arguments).
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import src.pipeline.git_collect as git_collect  # noqa: E402
from byrepo_pool_probe import ARGS as DEFAULT_ARGS, CachingGitHubClient  # noqa: E402
from src.mcp_server import _build_theme_input  # noqa: E402
from src.pipeline.git_collect import GitCollectConfig  # noqa: E402
from src.pipeline.track_a import _RANK_RELEVANCE_FLOOR, anchor_rank_key, collect_track_a_works  # noqa: E402

TOP = 4
WEIGHT_FLOOR = 0.05   # a keyword as frequent as the OR query still counts for something


def _pool(args: Dict[str, Any], cache: Path, pool: int, fair: bool):
    legs: List[dict] = []
    gh = CachingGitHubClient(cache, offline=True)
    works = collect_track_a_works(
        _build_theme_input(args), sources=["github"],
        git_config=GitCollectConfig(per_page=pool, max_repos=pool, keyword_fair_share=fair),
        github_client=gh, on_error=lambda s, e: print(f"   [error] {s}: {e}"), git_search_stats=legs)
    return works, legs, gh.failures


def rarity_weights(keywords: Sequence[str], legs: Sequence[dict]) -> Dict[str, float]:
    totals = {leg["label"]: leg.get("total_count") for leg in legs}
    or_total = legs[0].get("total_count") or 0
    raw = {}
    for kw in keywords:
        own = totals.get(kw)
        raw[kw] = max(math.log(or_total / own), WEIGHT_FLOOR) if (or_total and own) else WEIGHT_FLOOR
    norm = sum(raw.values()) or 1.0
    return {k: v / norm for k, v in raw.items()}


def _credits(work) -> Dict[str, float]:
    return {m["keyword"]: float(m.get("credit", 0)) for m in work.source_meta.get("theme_fit_matched") or []}


def weighted_relevance(work, weights: Dict[str, float], *, lone_equal: bool) -> float:
    credits = _credits(work)
    if lone_equal and len(credits) < 2:
        return sum(credits.values()) / max(len(weights), 1)   # the current, equal-weight coverage
    return sum(weights.get(k, 0.0) * c for k, c in credits.items())


def _rank(works, relevance, floor: float = _RANK_RELEVANCE_FLOOR) -> list:
    def key(w):
        rel = relevance(w)
        score = (w.source_meta.get("reliability_score", 0) or 0) * (floor + (1 - floor) * rel)
        return (1 if rel > 0 else 0, score)
    return sorted(works, key=key, reverse=True)


def _equal(work) -> float:
    return float(work.source_meta.get("relevance") or 0.0)


def _floor_grid(default, fair, weights, floors) -> None:
    w_all = lambda w: weighted_relevance(w, weights, lone_equal=False)   # noqa: E731
    for pool_label, pool in (("default pool", default), ("fair-share pool", fair)):
        for rule_label, rule in (("equal coverage", _equal), ("rarity-weighted", w_all)):
            print(f"  {pool_label} x {rule_label}")
            for floor in floors:
                top = _rank(pool, rule, floor)[:TOP]
                print(f"    floor {floor:<4g}: " + " / ".join(
                    f"{w.title.split('/')[-1]} ({rule(w):.2f}x{w.source_meta.get('reliability_score')})"
                    for w in top))


def _show(label: str, ranked, relevance=None) -> None:
    print(f"  {label}")
    for i, w in enumerate(ranked[:TOP], 1):
        m = w.source_meta
        rel = m.get("relevance") if relevance is None else round(relevance(w), 2)
        kws = ",".join(f"{k}:{c:g}" for k, c in _credits(w).items())
        desc = " ".join((w.abstract or "").split())[:60]
        print(f"    {i}. {w.title} rel={rel} Rel={m.get('reliability_score')} [{kws}] :: {desc}")


def main() -> None:
    argv = sys.argv[1:]
    floors = None
    if argv and argv[0] == "--floors":
        floors = [float(x) for x in argv[1].split(",")]
        argv = argv[2:]
    for spec in argv:
        name, pool, *rest = spec.split(":")
        as_of = rest[0] if rest else None
        theme_file = ROOT / "scripts" / "byrepo_probe_themes" / f"{name}.json"
        args = json.loads(theme_file.read_text(encoding="utf-8")) if theme_file.exists() else dict(DEFAULT_ARGS)
        cutoff = (date.fromisoformat(as_of) if as_of else date.today()) - timedelta(
            days=git_collect._GH_PUSHED_WITHIN_DAYS)
        git_collect._pushed_qualifier = lambda c=cutoff: f"pushed:>{c.isoformat()}"
        cache = ROOT / "output" / "byrepo_pool_cache" / name
        keywords = args["keywords_include"]

        print(f"\n===== {name} (pool {pool}) keywords={keywords}")
        default, _, fail_d = _pool(args, cache, int(pool), fair=False)
        fair, legs, fail_f = _pool(args, cache, int(pool), fair=True)
        if fail_d or fail_f:
            print(f"   not cached: default {fail_d} / fair-share {fail_f}")
        if len(legs) < 2 or any(leg.get("error") for leg in legs):
            print("   keyword searches are not cached -> A only")
            _show("A default x current", sorted(default, key=anchor_rank_key, reverse=True))
            continue
        weights = rarity_weights(keywords, legs)
        print("   weights: " + " / ".join(
            f"{k} {weights[k]:.2f} ({next(l['total_count'] for l in legs if l['label'] == k):,})"
            for k in keywords) + f" | OR {legs[0]['total_count']:,}")
        print("   fair-share seats: " + " / ".join(f"{l['label']} {l['seated']}" for l in legs))
        if floors:
            _floor_grid(default, fair, weights, floors)
            continue
        w_all = lambda w: weighted_relevance(w, weights, lone_equal=False)   # noqa: E731
        w_lone = lambda w: weighted_relevance(w, weights, lone_equal=True)   # noqa: E731
        _show("A default x current", sorted(default, key=anchor_rank_key, reverse=True))
        _show("B fair-share x current", sorted(fair, key=anchor_rank_key, reverse=True))
        _show("C default x rarity-weighted", _rank(default, w_all), w_all)
        _show("D fair-share x rarity-weighted", _rank(fair, w_all), w_all)
        _show("E fair-share x rarity-weighted (lone match keeps equal weight)", _rank(fair, w_lone), w_lone)


if __name__ == "__main__":
    main()
