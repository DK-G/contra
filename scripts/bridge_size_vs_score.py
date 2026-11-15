"""F-85 instrument: join a bybridge result's bridge sizes with the caller's finalize scores.

Usage:
  python scripts/bridge_size_vs_score.py <bybridge_result.(txt|json)> <finalize_input.json | session.jsonl>

The first file is a saved bybridge_collect result (the MCP content list, or plain text) whose
materials carry ``bridge_signals.bridge_cited_min`` (2026-11-13 onward). The second is either
the ``delegate_finalize`` arguments as JSON, or a Claude Code session transcript (.jsonl): the
LAST delegate_finalize call whose candidate ids overlap the bybridge ids is used.

Prints, per tier of the smallest bridge's cited_by_count, how many candidates the caller
scored, how many fell to anomaly (purpose_sim < 0.20), and the mean purpose_sim — the number
F-85's prescription (a) (cap bridges by size) needs before anyone decides on it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.bridge_diagnostics import BRIDGE_SIZE_TIERS, bridge_size_tier, short_id  # noqa: E402

ANOMALY = 0.20


def _text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(data, list):
        return "\n".join(str(b.get("text", "")) for b in data if isinstance(b, dict))
    if isinstance(data, dict) and "content" in data:
        return "\n".join(str(b.get("text", "")) for b in data["content"])
    return raw


def bridge_sizes(path: Path) -> dict:
    text = _text(path)
    out = {}
    for m in re.finditer(r'\{"id": "([^"]+)"', text):
        chunk = text[m.start(): m.start() + 20000]
        end = chunk.find('\n{"id"', 1)
        chunk = chunk if end < 0 else chunk[:end]
        lo = re.search(r'"bridge_cited_min": (\d+)', chunk)
        hi = re.search(r'"bridge_cited_max": (\d+)', chunk)
        if lo:
            out[short_id(m.group(1))] = (int(lo.group(1)), int(hi.group(1)) if hi else None)
            continue
        # F-88: under materials_max_chars the signals are a positional row
        # [shared, betweenness, strength, hybrid, route, cited_min, cited_max, field, topic, seen].
        row = re.search(r'"bridge_signals_row": (\[.*?\])\s*(?:,|\}|$)', chunk, re.S)
        if row:
            try:
                vals = json.loads(row.group(1))
            except json.JSONDecodeError:
                continue
            if len(vals) >= 7 and isinstance(vals[5], int):
                out[short_id(m.group(1))] = (vals[5], vals[6] if isinstance(vals[6], int) else None)
    return out


def finalize_scores(path: Path, wanted: set) -> dict:
    calls = []
    if path.suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = (o.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if c.get("type") == "tool_use" and c.get("name", "").endswith("delegate_finalize"):
                    calls.append(c["input"])
    else:
        calls.append(json.loads(path.read_text(encoding="utf-8")))
    best = None
    for args in calls:
        ids = {short_id(str(c.get("id", ""))) for c in args.get("candidates") or []}
        if ids & wanted:
            best = args
    if best is None:
        return {}
    return {short_id(str(c.get("id", ""))): c for c in best.get("candidates") or []}


def main(argv) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    sizes = bridge_sizes(Path(argv[1]))
    scores = finalize_scores(Path(argv[2]), set(sizes))
    tiers = {label: [] for _, label in BRIDGE_SIZE_TIERS}
    for sid, (lo, _hi) in sizes.items():
        if sid in scores:
            tiers[bridge_size_tier(lo)].append(scores[sid])
    print(f"bybridge 候補（大きさあり）{len(sizes)} 件 / うち呼び手が採点 {sum(len(v) for v in tiers.values())} 件")
    for _, label in BRIDGE_SIZE_TIERS:
        rows = tiers[label]
        ps = [float(r["purpose_sim"]) for r in rows if r.get("purpose_sim") is not None]
        anomaly = sum(1 for p in ps if p < ANOMALY)
        mean = f"{sum(ps) / len(ps):.2f}" if ps else "-"
        print(f"  最小 bridge {label}: 採点 {len(rows)} 件 / anomaly {anomaly} / purpose_sim 平均 {mean}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
