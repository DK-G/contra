"""R5 measurement: quantify purpose_sim / mechanism_dist run-to-run variance for fixed
candidates, via the real scoring path (_score_b_candidates_pm), with NO collection noise.

Reports per-candidate mean/std/min/max and the pass-rate at the anomaly floor
(_PURPOSE_SIM_MIN), so we can see how often a good far candidate is dropped by the hard cut
— and later measure whether a stabilization change (temp=0, discrete anchors, ...) helps.

Run from repo root with OPENAI_API_KEY set:
  python scripts/r5_score_stability.py --k 8
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Reuse the 3 spectrum fixtures (quantum / epidemic / climate) and the social theme loader.
from r2_judge_compare import FIXTURES, _load_social_theme  # noqa: E402
from src.pipeline.classify import (  # noqa: E402
    _PURPOSE_SIM_MIN,
    _extract_theme_schema,
    _score_b_candidates_pm,
)


def _agg(label: str, values: list) -> dict:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"id": label, "n": 0}
    return {
        "id": label,
        "n": len(vals),
        "mean": round(statistics.mean(vals), 3),
        "std": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0,
        "min": round(min(vals), 3),
        "max": round(max(vals), 3),
        "values": [round(v, 2) for v in vals],
    }


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--k", type=int, default=8, help="number of scoring repetitions")
    ap.add_argument("--out", default="output/r5_score_stability.json")
    args = ap.parse_args(argv)
    if not os.getenv("OPENAI_API_KEY"):
        print("[error] OPENAI_API_KEY not set", file=sys.stderr)
        return 1

    theme = _load_social_theme()
    schema = _extract_theme_schema(theme, args.model)
    print(f"THEME purpose : {schema['purpose']}")
    print(f"anomaly floor (_PURPOSE_SIM_MIN) = {_PURPOSE_SIM_MIN}\n")

    ps = {w.id: [] for w in FIXTURES}
    md = {w.id: [] for w in FIXTURES}
    for i in range(args.k):
        scores = _score_b_candidates_pm(FIXTURES, schema, theme, args.model)
        for w in FIXTURES:
            s = scores.get(w.id, {})
            ps[w.id].append(s.get("purpose_sim"))
            md[w.id].append(s.get("mechanism_dist"))
        line = "  ".join(
            f"{w.id}={scores.get(w.id, {}).get('purpose_sim')}" for w in FIXTURES
        )
        print(f"[run {i + 1}/{args.k}] purpose_sim: {line}")

    print("\n=== purpose_sim variance ===")
    summary = {}
    for w in FIXTURES:
        a = _agg(w.id, ps[w.id])
        passes = sum(1 for v in ps[w.id] if v is not None and v >= _PURPOSE_SIM_MIN)
        a["pass_rate@floor"] = f"{passes}/{a.get('n', 0)}"
        summary[w.id] = {"purpose_sim": a, "mechanism_dist": _agg(w.id, md[w.id])}
        print(
            f"  {w.id:9s} mean={a.get('mean')} std={a.get('std')} "
            f"range=[{a.get('min')},{a.get('max')}] pass@{_PURPOSE_SIM_MIN}={a['pass_rate@floor']} "
            f"values={a.get('values')}"
        )

    (_REPO_ROOT / args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[ok] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
