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


def resolve_ids_batched(
    work_ids: Sequence[str],
    client: Any = None,
    *,
    chunk: int = 50,
) -> Set[str]:
    """The subset of ``work_ids`` that OpenAlex still resolves to a real work.

    One ``ids.openalex:`` call per ``chunk`` ids. Raises on transport failure so callers can
    decide — a *silent* empty answer here would look identical to "every bridge is dead".
    """
    ids: List[str] = []
    seen: Set[str] = set()
    for wid in work_ids or []:
        sid = short_id(wid)
        if sid and sid not in seen:
            seen.add(sid)
            ids.append(sid)
    if not ids:
        return set()
    if client is None:
        from src.openalex.client import OpenAlexClient
        client = OpenAlexClient()
    live: Set[str] = set()
    for i in range(0, len(ids), max(1, chunk)):
        batch = ids[i:i + max(1, chunk)]
        payload = client.get({
            "filter": "ids.openalex:" + "|".join(batch),
            "per_page": len(batch),
            "select": "id",
        })
        for item in (payload or {}).get("results", []) or []:
            sid = short_id(item.get("id", ""))
            if sid:
                live.add(sid)
    return live


def filter_live_bridges(
    bridges: Iterable[str],
    client: Any = None,
) -> "tuple[Set[str], List[str]]":
    """Split a bridge pool into (live, dead). Fails OPEN — on error everything counts as live.

    **Why this gate exists (F-01's true root cause, 2026-08-25).** ``referenced_works`` is a raw
    reference list: OpenAlex merges and deletes work records, but the *old* ids stay behind in
    every citing paper's reference list. Such a dangling id is not a shared intellectual
    ancestor — it is a bibliographic scar, and it can be an enormous one. Measured on the
    seihai theme family: the pool's most-travelled bridge ``W4285719527`` **does not exist**
    (404 / zero hits by id) yet sits in **4,906,577** reference lists — 176x the citer count of
    the largest *live* bridge in the same pool (27,948). Because the 2-hop scan ORs the whole
    pool into one ``cites:`` filter, that one phantom swallowed 59 of 60 candidates and the
    result degenerated into "the most-cited works in OpenAlex, minus the home field" — thematic
    analysis, TAM, LSTM, G*Power. That is the exact shape recorded as F-01 for seven weeks.

    Note what does **not** discriminate: size. The same pool held four other dead ids with
    4,194 / 2,749 / 554 / 59 citers, while its biggest live bridges (Fama-French 27,948; GARCH
    22,513) are legitimate domain classics. A centrality penalty would have kept the small
    phantoms and punished the real ancestors — which is why the 2026-08-18 instrument run
    rejected that prescription. Resolvability is the discriminator, not degree.

    Fail-open is deliberate: a transient OpenAlex failure must degrade to the old behaviour,
    never to an empty pool.
    """
    # Bridges travel as FULL ids ('https://openalex.org/W1') because they come straight out of
    # referenced_works, and every downstream set-intersection (seed contribution, concentration,
    # shared_bridge_count) compares against that form. Resolve on the short id, but hand back the
    # caller's original strings — returning short ids silently zeroes every bridge statistic.
    originals: Dict[str, str] = {}
    for b in bridges or []:
        sid = short_id(b)
        if sid:
            originals.setdefault(sid, str(b))
    if not originals:
        return set(), []
    ids = list(originals)
    try:
        live_ids = resolve_ids_batched(ids, client)
    except Exception:      # transport failure -> keep the old behaviour, drop nothing
        return {originals[i] for i in ids}, []
    if not live_ids:       # an all-dead answer is far likelier to be a bad response than truth
        return {originals[i] for i in ids}, []
    return (
        {originals[i] for i in ids if i in live_ids},
        [i for i in ids if i not in live_ids],
    )


# ---------------------------------------------------------------------------
# F-13: seed-roster provenance (the "where did the retrieval actually land?" instrument).
# A metadata-level clarity check: instead of a language-model KL divergence
# (Cronen-Townsend's Clarity score), it reads the roster's own OpenAlex Topic hierarchy
# (Domain>Field>Subfield>Topic) against what the caller declared — deterministic, key-free,
# one pass over already-fetched metadata.
#
# 2026-09-04 (this instrument's OWN failure, recorded in field_observations_seihai.md): the
# first version reported only the Field match, and a roster of NAFTA / broadband / COVID
# policy / Fox-News papers on a strategy-selection theme scored "home分野一致 20/20 = 100%".
# The Field "Economics, Econometrics and Finance" contains international trade, labour
# economics and asset pricing alike, so a Field match says almost nothing about subject fit —
# and because 100% reads as "checked, fine", the caller stops reading the roster. That is the
# exact shape contra itself named in S-68: a coarse attribute reported as a green verdict
# becomes an undetectable failure. Three changes follow from it:
#
#   (a) SUBFIELD alignment, when the caller's scope resolves to one, is the headline number.
#       Measured 2026-09-04 on live rosters, home subfield = Finance: the drifted 9/04 roster
#       is 1/20 = 5%, two deliberately on-topic controls are 13/20 = 65% and 12/17 = 71%.
#   (b) The TOPIC names are always printed. Drift is readable there and nowhere else
#       ("Healthcare Policy and Management 3 / COVID-19 Pandemic Impacts 2" on a trading
#       theme), and every recorded F-13 incident was in fact caught by a human reading titles.
#   (c) The Field number never stands alone as a verdict — it is labelled as the coarse
#       26-way bucket it is, and the semantic leg's supply is reported beside it, because a
#       roster built with zero theme-prose retrieval has not had its subject fit tested at all.
#
# Topic DISPERSION was tried as a discriminator the same day and rejected: the drifted roster
# spread over 12 topics while an on-topic one spread over 6 — but a second on-topic roster
# spread over 7 and a partly-drifted one over 4, so the ranges overlap and no threshold on it
# would be honest. Recorded (field_observations_seihai.md F-13-I) rather than shipped.
# ---------------------------------------------------------------------------

def seed_domain_alignment(
    seeds: Sequence[Work],
    home_field_ids: Iterable[str],
    *,
    home_subfield_ids: Iterable[str] = (),
    semantic_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Topic-hierarchy stats for a seed roster vs the theme's declared home domain.

    Returns the Field-level keys ``{total, home, fraction, unknown, top_fields}`` plus the
    finer levels ``{sub_home, sub_unknown, sub_fraction, top_subfields, top_topics,
    distinct_topics, semantic_count}``. Works with no classification at a given level count
    into that level's ``unknown`` and are excluded from its denominator (a missing
    classification is not evidence of drift — S-68: never encode "no information" as a bad
    value). ``semantic_count`` is carried through untouched for rendering.
    """
    home = {str(f) for f in home_field_ids if f}
    sub_home_ids = {str(s) for s in home_subfield_ids if s}
    total = len(seeds)
    counts: Dict[str, int] = {}
    sub_counts: Dict[str, int] = {}
    topic_counts: Dict[str, int] = {}
    in_home = 0
    unknown = 0
    sub_in_home = 0
    sub_unknown = 0
    for w in seeds:
        meta = getattr(w, "source_meta", None) or {}
        fid = str(meta.get("primary_topic_field_id") or "")
        fname = str(meta.get("primary_topic_field_name") or "") or (f"Field {fid}" if fid else "")
        if not fid:
            unknown += 1
        else:
            counts[fname] = counts.get(fname, 0) + 1
            if fid in home:
                in_home += 1
        sid = str(meta.get("primary_topic_subfield_id") or "")
        sname = str(meta.get("primary_topic_subfield_name") or "") or (f"Subfield {sid}" if sid else "")
        if not sid:
            sub_unknown += 1
        else:
            sub_counts[sname] = sub_counts.get(sname, 0) + 1
            if sid in sub_home_ids:
                sub_in_home += 1
        tname = str(meta.get("primary_topic_name") or "")
        if tname:
            topic_counts[tname] = topic_counts.get(tname, 0) + 1
    known = total - unknown
    sub_known = total - sub_unknown
    fraction = (in_home / known) if (known and home) else None
    sub_fraction = (sub_in_home / sub_known) if (sub_known and sub_home_ids) else None
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top_sub = sorted(sub_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top_topics = sorted(topic_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return {"total": total, "home": in_home, "unknown": unknown,
            "fraction": fraction, "top_fields": top,
            "sub_home_resolved": bool(sub_home_ids),
            "sub_home": sub_in_home, "sub_unknown": sub_unknown,
            "sub_fraction": sub_fraction, "top_subfields": top_sub,
            "top_topics": top_topics, "distinct_topics": len(topic_counts),
            "semantic_count": semantic_count}


# Warn thresholds, both calibrated against real rosters rather than chosen as round numbers.
#
# FIELD (26-way bucket): unscoped lexical roster = 50% home, field-scoped roster = 100%
# (2026-08-28, r05/F9 theme), and the recorded 8/27 incident roster (agriculture/medicine
# records on an economics theme) reads ~0%. Below 0.5 means the scope failed, was disabled, or
# scope.field did not resolve.
#
# SUBFIELD (252-way): measured live 2026-09-04 with the 9/04 seihai keywords plus two
# deliberately on-topic controls, home subfield = Finance:
#   drifted 9/04 roster (NAFTA / broadband / COVID / Fox News) ...   1/20 =  5%
#   control "pairs trading / statistical arbitrage / cointegration" 13/20 = 65%
#   control "backtest overfitting / deflated sharpe / CV" .......   12/17 = 71%
# 0.35 sits between the observed failure and the observed healthy band with margin on both
# sides; deliberately NOT 0.5, which would sit inside the healthy band for genuinely
# cross-subfield themes.
SEED_ALIGNMENT_WARN_BELOW = 0.5
SEED_SUBFIELD_WARN_BELOW = 0.35


def render_seed_alignment(
    stats: Dict[str, Any],
    *,
    home_label: str = "",
    subfield_label: str = "",
) -> str:
    """Diagnostics block naming where the seed roster actually landed (F-13).

    Deliberately multi-line and deliberately without a single green scalar: the 2026-09-04
    failure of this very instrument was that ``100%`` on one coarse attribute read as
    "checked, no problem" and stopped the caller from looking at the roster at all.
    """
    frac = stats["fraction"]
    frac_txt = f"{frac:.0%}" if frac is not None else "判定不能（home分野未解決）"
    label = f"（home={home_label}）" if home_label else ""
    known = stats["total"] - stats["unknown"]
    top_fields = " / ".join(f"{name} {n}" for name, n in stats["top_fields"][:3]) or "（分類なし）"
    lines = [
        f"- シード名簿の素性 (F-13): {stats['total']} 件を OpenAlex の Topic 階層で読む{label}",
        f"  ・分野(Field) 一致 {stats['home']}/{known} = {frac_txt}・上位分野 {top_fields}"
        "　※Field は 26 分類の最粗レベルで、主題適合ではない"
        "（『Economics, Econometrics and Finance』は国際貿易も労働経済も資産価格も含む）",
    ]
    if stats["unknown"]:
        lines[-1] += f"・分野未分類 {stats['unknown']} 件"

    sub_frac = stats.get("sub_fraction")
    sub_known = stats["total"] - stats.get("sub_unknown", 0)
    sub_top = " / ".join(f"{n} {c}" for n, c in stats.get("top_subfields", [])[:3]) or "（分類なし）"
    sub_label = f"（home サブフィールド={subfield_label}）" if subfield_label else ""
    if sub_frac is None:
        # Two different "cannot say"s, and they call for different actions: the caller can fix
        # an unresolved scope by naming an OpenAlex Subfield, but an unclassified roster is the
        # data's doing. Neither is rendered as 0% (S-68).
        why = (
            "名簿側に Subfield 分類が無い"
            if stats.get("sub_home_resolved")
            else "scope が OpenAlex のサブフィールド名に解決しない"
        )
        lines.append(
            f"  ・サブフィールド(Subfield) 一致: 判定不能（{why}）・上位 {sub_top}"
        )
    else:
        lines.append(
            f"  ・サブフィールド(Subfield) 一致 {stats['sub_home']}/{sub_known} = "
            f"{sub_frac:.0%}{sub_label}・上位 {sub_top}"
        )

    topics = stats.get("top_topics", [])
    top_txt = " / ".join(f"{n} {c}" for n, c in topics[:5]) or "（分類なし）"
    lines.append(
        f"  ・上位トピック {top_txt}"
        f"（{stats['total']} 件が {stats.get('distinct_topics', 0)} トピックに分布）"
        "　← 名簿が主題から外れているかは、この行と下のシード表で読む"
    )

    sem = stats.get("semantic_count")
    if sem is not None:
        lines.append(
            f"  ・semantic レッグ供給 {sem} 件"
            "（テーマ本文そのものを検索に入れる唯一の取得レッグ）"
        )

    if frac is not None and frac < SEED_ALIGNMENT_WARN_BELOW:
        lines.append(
            f"  ⚠ シード名簿がテーマの分野から外れています（分野一致 {frac_txt} < "
            f"{SEED_ALIGNMENT_WARN_BELOW:.0%}）。この run の下流（bridge 構築・交差候補・採点）は"
            "外れた名簿の上で正しく動くため、診断の他の数字が健全でも収穫は主題に当たりません。"
            "キーワードの語彙衝突（F-13）を疑ってください。"
        )
    if sub_frac is not None and sub_frac < SEED_SUBFIELD_WARN_BELOW:
        lines.append(
            f"  ⚠ 分野(Field)は一致していてもサブフィールドが外れています（{sub_frac:.0%} < "
            f"{SEED_SUBFIELD_WARN_BELOW:.0%}）。宣言した主題"
            f"（{subfield_label or 'scope'}）の論文が名簿にほとんど入っていません＝"
            "同一 Field 内の主題ドリフト（2026-09-04 の様式）。上位トピックを読み、"
            "キーワードが別の下位分野の主流語彙に吸われていないか確認してください。"
        )
    if sem == 0:
        lines.append(
            "  ⚠ semantic レッグの供給が 0 件です（取得失敗、または全件が field 選別で落ちた）。"
            "名簿は純語彙シードのみで構成され、テーマ本文は検索に一度も入っていません＝"
            "主題適合は『良好』でも『不良』でもなく未検証です。"
        )
    return "\n".join(lines)


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
    "resolve_ids_batched",
    "filter_live_bridges",
    "render_diagnostics",
]
