"""Depletion measurement: quantify run-to-run NEW-CANDIDATE YIELD for one theme under
history dedup, so we can later compare M1 (recency bias) / M2 (history-steered queries)
against this baseline.

The long-run risk (see memory contra_depletion_risk) is that the OpenAlex well does not
regenerate: queries are history-blind and the search is relevance-fixed, so each run keeps
fetching the same top-of-relevance papers and the history dedup keeps discarding them, until
genuinely-new good candidates dry up and the report stops standing up.

This harness simulates N consecutive runs on ONE theme with history ON (accumulated in
memory across runs, NOT touching data/history), reusing the REAL collection path
(generate_track_b_queries + the same OpenAlex paging + id/title/DOI dedup as collect_track_b).
Per run it reports:
  - fetched   : abstract-bearing rows returned by OpenAlex this run (pre-history-dedup, post intra-run dedup)
  - recycled  : of those, how many were dropped because already surfaced in a PRIOR run (the depletion signal)
  - new       : genuinely-new candidates this run (what downstream scoring actually gets to see)
  - recycle_rate = recycled / (recycled + new)

With --score it additionally runs the real select_track_b on each run's NEW works and reports
how many clear the output floor (the "floor超え候補数" — does new yield translate into a report?).
This is the expensive path (LLM scoring); collection-only is the default.

Run from repo root with OPENAI_API_KEY set:
  python scripts/depletion_probe.py --input data/samples/theme_social.json --runs 4
  python scripts/depletion_probe.py --input data/samples/theme_social.json --runs 3 --score
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.core.input_schema import validate_and_normalize  # noqa: E402
from src.core.models import Work  # noqa: E402
from src.openalex.parser import normalize_results  # noqa: E402
from src.pipeline.collect import (  # noqa: E402
    CollectConfig,
    Collector,
    _norm_doi,
    _norm_title,
    generate_track_b_queries,
)
from src.pipeline.filter import filter_retracted  # noqa: E402


def _collect_run_counted(
    theme,
    collector: Collector,
    cfg: CollectConfig,
    model: str,
    *,
    hist_ids: Set[str],
    hist_titles: Set[str],
    hist_dois: Set[str],
    max_count: int = 60,
) -> dict:
    """One Track B collection run, instrumented to count fetched / recycled / new.

    Mirrors collect_track_b's paging + dedup exactly, but separates "dropped because seen in a
    PRIOR run (recycled)" from "new this run". `hist_*` are the accumulated prior-run sets and
    are NOT mutated here; the caller folds in the returned new works.
    """
    queries = generate_track_b_queries(theme, model)
    seen_ids: Set[str] = set()      # intra-run dedup only
    seen_titles: Set[str] = set()
    seen_dois: Set[str] = set()
    new_works: List[Work] = []
    fetched = 0
    recycled = 0
    per_query = max(max_count // max(len(queries), 1), 5)
    for query in queries:
        count = 0
        for page in range(1, cfg.max_pages + 1):
            payload = collector.client.get(
                {"search": query, "per-page": cfg.per_page, "page": page}
            )
            for w in filter_retracted(normalize_results(payload)):
                if not w.abstract:
                    continue
                nt, nd = _norm_title(w.title), _norm_doi(w.doi)
                # intra-run dedup (same paper across queries/pages) — not counted as recycled
                if w.id in seen_ids or (nt and nt in seen_titles) or (nd and nd in seen_dois):
                    continue
                seen_ids.add(w.id)
                if nt:
                    seen_titles.add(nt)
                if nd:
                    seen_dois.add(nd)
                fetched += 1
                # recycled = would-be-new this run, but surfaced in a prior run
                if w.id in hist_ids or (nt and nt in hist_titles) or (nd and nd in hist_dois):
                    recycled += 1
                    continue
                new_works.append(w)
                count += 1
            if count >= per_query:
                break
        if len(new_works) >= max_count:
            break
    new_works = new_works[:max_count]
    return {
        "queries": queries,
        "fetched": fetched,
        "recycled": recycled,
        "new": len(new_works),
        "new_works": new_works,
    }


def _score_floor_passers(new_works: List[Work], theme, model: str, output_floor: float) -> dict:
    """Run the real select_track_b on this run's new works; count units above the output floor."""
    from src.pipeline.classify import select_track_b

    entries = select_track_b(
        new_works, theme, model=model, count=len(new_works) or 1,
        use_llm=True, theme_profile=None, output_floor=output_floor,
    )
    above = [e for e in entries if getattr(e, "serendipity_score", 0.0) >= output_floor]
    return {
        "selected": len(entries),
        "floor_passed": len(above),
        "top_serendipity": round(max((getattr(e, "serendipity_score", 0.0) for e in entries), default=0.0), 3),
    }


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to a theme JSON (e.g. data/samples/theme_social.json)")
    ap.add_argument("--runs", type=int, default=4, help="Number of consecutive history-ON runs to simulate")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--per-page", type=int, default=50)
    ap.add_argument("--max-pages", type=int, default=4)
    ap.add_argument("--max-count", type=int, default=60, help="Track B candidate cap per run (matches collect_track_b)")
    ap.add_argument("--mailto", default=None)
    ap.add_argument("--score", action="store_true", help="Also score each run's new works and count floor-passers (LLM cost)")
    ap.add_argument("--output-floor", type=float, default=0.35)
    ap.add_argument("--out", default="output/depletion_probe.json")
    args = ap.parse_args(argv)
    if not os.getenv("OPENAI_API_KEY"):
        print("[error] OPENAI_API_KEY not set", file=sys.stderr)
        return 1

    theme = validate_and_normalize(json.loads(Path(args.input).read_text(encoding="utf-8")))
    cfg = CollectConfig(per_page=args.per_page, max_pages=args.max_pages, mailto=args.mailto)
    collector = Collector(cfg)

    hist_ids: Set[str] = set()
    hist_titles: Set[str] = set()
    hist_dois: Set[str] = set()
    runs: List[dict] = []

    print(f"theme: {Path(args.input).name}  runs={args.runs}  model={args.model}  score={args.score}\n")
    for i in range(1, args.runs + 1):
        r = _collect_run_counted(
            theme, collector, cfg, args.model,
            hist_ids=hist_ids, hist_titles=hist_titles, hist_dois=hist_dois,
            max_count=args.max_count,
        )
        denom = r["recycled"] + r["new"]
        recycle_rate = round(r["recycled"] / denom, 3) if denom else 0.0
        row = {
            "run": i,
            "hist_size_before": len(hist_ids),
            "fetched": r["fetched"],
            "recycled": r["recycled"],
            "new": r["new"],
            "recycle_rate": recycle_rate,
            "queries": r["queries"],
        }
        if args.score and r["new_works"]:
            row["score"] = _score_floor_passers(r["new_works"], theme, args.model, args.output_floor)
        elif args.score:
            row["score"] = {"selected": 0, "floor_passed": 0, "top_serendipity": 0.0}

        # fold this run's new works into the accumulated history for the next run
        for w in r["new_works"]:
            hist_ids.add(w.id)
            nt, nd = _norm_title(w.title), _norm_doi(w.doi)
            if nt:
                hist_titles.add(nt)
            if nd:
                hist_dois.add(nd)
        runs.append(row)

        score_str = ""
        if "score" in row:
            score_str = f"  floor_passed={row['score']['floor_passed']} top={row['score']['top_serendipity']}"
        print(
            f"[run {i}/{args.runs}] hist_before={row['hist_size_before']:3d}  "
            f"fetched={row['fetched']:3d}  recycled={row['recycled']:3d}  new={row['new']:3d}  "
            f"recycle_rate={recycle_rate}{score_str}"
        )

    summary = {
        "input": args.input,
        "runs": args.runs,
        "model": args.model,
        "scored": args.score,
        "per_run": runs,
        "new_yield_curve": [r["new"] for r in runs],
        "recycle_rate_curve": [r["recycle_rate"] for r in runs],
    }
    if args.score:
        summary["floor_passed_curve"] = [r.get("score", {}).get("floor_passed", 0) for r in runs]

    out_path = _REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nnew-yield curve   : {summary['new_yield_curve']}")
    print(f"recycle-rate curve: {summary['recycle_rate_curve']}")
    if args.score:
        print(f"floor-passed curve: {summary['floor_passed_curve']}")
    print(f"[ok] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
