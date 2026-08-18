"""bybridge run diagnostics — make the seeds and the bridges VISIBLE to the caller.

Background: ``docs/field_observations_seihai.md`` F-02. Until now ``bybridge_collect``
reported only *counts* ("seeds 30 / bridge pool 50 / candidates 60"). With counts alone the
caller cannot tell a **seed-search failure** (the near-field seeds were off-topic, so every
downstream hop is off-topic) from **giant-hub absorption** (the seeds were fine but the bridge
pool collapsed onto one universally-cited work). Those two failures need opposite fixes, and
the 2026-08-02 ruling on M-16 ("adjust the seeds and it resolves") stayed unverifiable for five
weeks precisely because the seeds were never returned.

This module is the instrument, not the prescription. It adds:

* **seed rows** — every seed actually used, with title / year / venue / DOI / citation count, so
  "were the seeds on-topic?" is answerable from the output alone.
* **bridge usage** — for each bridge: how many seeds cite it and how many cross-domain
  candidates route through it, i.e. which shared reference the 2-hop scan actually travelled.
* **hub concentration** — the share of candidates that hang off the single most-used bridge.
  This is the direct meter for F-01: "top 10 all share one bridge" becomes a number that can be
  compared before/after a centrality penalty is applied.

Everything except :func:`resolve_work_labels` is pure and computed from data already in hand
(zero API cost). ``resolve_work_labels`` spends **one** OpenAlex call to name the handful of
bridges that get displayed, and fails soft to bare ids so a diagnostics failure can never take
down a run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from src.core.models import Work

_ID_RE = re.compile(r"(W\d+)")


def _as_set(bridges: Iterable[str]) -> Set[str]:
    return bridges if isinstance(bridges, set) else set(bridges)


def short_id(work_id: str) -> str:
    """'https://openalex.org/W123' -> 'W123'; anything unrecognised is returned unchanged."""
    m = _ID_RE.search(str(work_id or ""))
    return m.group(1) if m else str(work_id or "")


@dataclass
class SeedRow:
    """One near-field seed exactly as it was used to build the bridge pool."""
    id: str
    title: str
    year: Optional[int]
    venue: str
    doi: Optional[str]
    cited_by_count: int
    bridge_contribution: int = 0   # how many of its references made it into the bridge pool


@dataclass
class BridgeUsage:
    """One bridge (shared reference) and the traffic that actually went through it."""
    id: str
    seed_citers: int
    candidate_citers: int
    title: str = ""
    cited_by_count: Optional[int] = None


@dataclass
class BridgeConcentration:
    """How far the cross-domain candidates collapsed onto a single bridge (F-01's meter)."""
    candidates: int = 0
    top_bridge_id: str = ""
    top_bridge_share: float = 0.0        # fraction of ALL candidates citing the top bridge
    top_n: int = 0                       # size of the head window examined
    top_n_share: float = 0.0             # same fraction within the head window
    mean_shared_bridges: float = 0.0     # avg distinct bridges per candidate (1.0 = no redundancy)
    single_bridge_candidates: int = 0    # candidates hanging off exactly one bridge
    distinct_bridges_used: int = 0       # bridges that at least one candidate actually cites


def seed_rows(seeds: Sequence[Work], bridges: Optional[Iterable[str]] = None) -> List[SeedRow]:
    """Project the seeds onto the fields a caller needs to judge whether seed search was sane."""
    bset = _as_set(bridges) if bridges is not None else None
    rows: List[SeedRow] = []
    for s in seeds or []:
        refs = set(s.referenced_works or [])
        rows.append(SeedRow(
            id=str(s.id or ""),
            title=str(s.title or "(no title)"),
            year=getattr(s, "year", None),
            venue=str(getattr(s, "venue", "") or ""),
            doi=getattr(s, "doi", None),
            cited_by_count=int(getattr(s, "cited_by_count", 0) or 0),
            bridge_contribution=len(refs & bset) if bset is not None else 0,
        ))
    return rows


def bridge_usage(
    seeds: Sequence[Work],
    candidates: Sequence[Work],
    bridges: Iterable[str],
) -> List[BridgeUsage]:
    """Per-bridge traffic, busiest first (candidate citers, then seed citers, then id).

    Only bridges in the pool are reported. A bridge with ``candidate_citers == 0`` was in the
    pool but carried no cross-domain traffic; it is still returned so the caller can see how
    much of a 50-strong pool went unused.
    """
    bset = _as_set(bridges)
    seed_hits: Dict[str, int] = {}
    cand_hits: Dict[str, int] = {}
    for s in seeds or []:
        for b in set(s.referenced_works or []) & bset:
            seed_hits[b] = seed_hits.get(b, 0) + 1
    for c in candidates or []:
        for b in set(c.referenced_works or []) & bset:
            cand_hits[b] = cand_hits.get(b, 0) + 1
    out = [
        BridgeUsage(id=b, seed_citers=seed_hits.get(b, 0), candidate_citers=cand_hits.get(b, 0))
        for b in bset
    ]
    out.sort(key=lambda u: (-u.candidate_citers, -u.seed_citers, u.id))
    return out


def bridge_concentration(
    candidates: Sequence[Work],
    bridges: Iterable[str],
    *,
    top_n: int = 10,
    ranked: Optional[Sequence[Work]] = None,
) -> BridgeConcentration:
    """Measure collapse onto one bridge over all candidates and over the ranked head.

    ``ranked`` lets the caller pass the list in the order the user will actually see (the
    bybridge rank order); it defaults to ``candidates``. ``top_n_share`` answers exactly the
    shape seihai kept reporting — "the top 10 all shared one bridge" — as a number.
    """
    bset = _as_set(bridges)
    cands = list(candidates or [])
    conc = BridgeConcentration(candidates=len(cands))
    if not cands or not bset:
        return conc

    hits: Dict[str, Set[str]] = {}
    total_shared = 0
    for c in cands:
        hit = set(c.referenced_works or []) & bset
        total_shared += len(hit)
        if len(hit) == 1:
            conc.single_bridge_candidates += 1
        for b in hit:
            hits.setdefault(b, set()).add(str(c.id))

    conc.mean_shared_bridges = total_shared / len(cands)
    conc.distinct_bridges_used = len(hits)
    if not hits:
        return conc

    top_bridge, citers = max(hits.items(), key=lambda kv: (len(kv[1]), kv[0]))
    conc.top_bridge_id = top_bridge
    conc.top_bridge_share = len(citers) / len(cands)

    head = list(ranked if ranked is not None else cands)[:max(1, top_n)]
    conc.top_n = len(head)
    if head:
        conc.top_n_share = sum(1 for c in head if str(c.id) in citers) / len(head)
    return conc


def resolve_work_labels(
    work_ids: Sequence[str],
    client: Any = None,
    *,
    cap: int = 50,
) -> Dict[str, Dict[str, Any]]:
    """Name a batch of OpenAlex works in ONE call. Fails soft to ``{}`` — never raises.

    Bridges arrive as bare ids (they come from ``referenced_works``), and an unnamed id tells
    the caller nothing about whether the bridge is a giant generic hub. Keys of the returned map
    are the SHORT ids (``W123``); look them up with :func:`short_id`.
    """
    ids: List[str] = []
    seen: Set[str] = set()
    for wid in work_ids or []:
        sid = short_id(wid)
        if sid and sid not in seen:
            seen.add(sid)
            ids.append(sid)
        if len(ids) >= cap:
            break
    if not ids:
        return {}
    try:
        if client is None:
            from src.openalex.client import OpenAlexClient
            client = OpenAlexClient()
        payload = client.get({
            "filter": "ids.openalex:" + "|".join(ids),
            "per_page": len(ids),
            "select": "id,display_name,publication_year,cited_by_count",
        })
        out: Dict[str, Dict[str, Any]] = {}
        for item in (payload or {}).get("results", []) or []:
            sid = short_id(item.get("id", ""))
            if sid:
                out[sid] = {
                    "title": item.get("display_name") or "",
                    "year": item.get("publication_year"),
                    "cited_by_count": item.get("cited_by_count"),
                }
        return out
    except Exception:  # diagnostics must never break a run
        return {}


def _fmt_int(n: Optional[int]) -> str:
    return f"{int(n):,}" if isinstance(n, int) else "?"


def render_diagnostics(
    seeds: Sequence[Work],
    candidates: Sequence[Work],
    bridges: Iterable[str],
    *,
    ranked: Optional[Sequence[Work]] = None,
    labels: Optional[Dict[str, Dict[str, Any]]] = None,
    seed_limit: int = 30,
    bridge_limit: int = 5,
    top_n: int = 10,
) -> str:
    """Render the seed list, the busiest bridges, and the hub-concentration meter as markdown."""
    bset = _as_set(bridges)
    rows = seed_rows(seeds, bset)
    usage = bridge_usage(seeds, candidates, bset)
    conc = bridge_concentration(candidates, bset, top_n=top_n, ranked=ranked)
    labels = labels or {}

    lines: List[str] = []
    lines.append(
        f"収集診断: シード {len(rows)} 件 / bridge プール {len(bset)} 本 / "
        f"交差候補 {len(candidates or [])} 件"
    )

    if conc.candidates and conc.top_bridge_id:
        top_lab = labels.get(short_id(conc.top_bridge_id), {})
        top_name = top_lab.get("title") or short_id(conc.top_bridge_id)
        lines.append(
            f"- bridge 集中度: 最頻 bridge が交差候補の {conc.top_bridge_share * 100:.0f}%"
            f"（上位 {conc.top_n} 件では {conc.top_n_share * 100:.0f}%）を占める"
            f" / 候補あたり平均 {conc.mean_shared_bridges:.2f} 本"
            f" / 共有 bridge 1本のみの候補 {conc.single_bridge_candidates}/{conc.candidates} 件"
            f" / 実際に使われた bridge {conc.distinct_bridges_used} 本"
        )
        lines.append(
            f"- 最頻 bridge: {top_name}"
            + (f"（被引用 {_fmt_int(top_lab.get('cited_by_count'))}）" if top_lab else "")
        )

    lines.append("")
    lines.append(f"**使用シード（{len(rows)} 件・この検索結果が全ての起点）**")
    for i, r in enumerate(rows[:seed_limit], 1):
        ref = r.doi or r.id
        lines.append(
            f"{i}. {r.title} — {r.year or '?'} | {r.venue or '(venue不明)'} | "
            f"被引用 {_fmt_int(r.cited_by_count)} | bridge 寄与 {r.bridge_contribution} 本 | {ref}"
        )
    if len(rows) > seed_limit:
        lines.append(f"…他 {len(rows) - seed_limit} 件")

    used = [u for u in usage if u.candidate_citers > 0]
    lines.append("")
    lines.append(
        f"**交差候補が通った bridge（上位 {min(bridge_limit, len(used))} 本 / "
        f"通行のあった bridge {len(used)} 本）**"
    )
    for i, u in enumerate(used[:bridge_limit], 1):
        lab = labels.get(short_id(u.id), {})
        name = lab.get("title") or short_id(u.id)
        cited = f" | 被引用 {_fmt_int(lab.get('cited_by_count'))}" if lab else ""
        lines.append(
            f"{i}. {name} — 交差候補 {u.candidate_citers} 件 / "
            f"シード {u.seed_citers} 件が引用{cited} | {short_id(u.id)}"
        )
    if not used:
        lines.append("（bridge 通行の記録なし＝候補の referenced_works が取得できていない可能性）")

    return "\n".join(lines)


__all__ = [
    "SeedRow",
    "BridgeUsage",
    "BridgeConcentration",
    "short_id",
    "seed_rows",
    "bridge_usage",
    "bridge_concentration",
    "resolve_work_labels",
    "render_diagnostics",
]
