"""bybridge B-0 false-bridge probe (roadmap Phase 1.5, docs/bybridge_concept.md §8).

The cheapest test of the third mode BEFORE any pipeline work: does the shared-structure
hypothesis generator surface the KNOWN bridge for answer-known theme pairs, and at what
abstraction level do FALSE bridges creep in?

Pipeline exercised here (no collection/scoring infra beyond what's needed):
  1. _extract_theme_schema  on theme A and theme B           [reused from classify.py]
  2. generate_bridge_hypotheses(schema_a, schema_b)          [NEW — the heart of bybridge]
       -> 2-4 abstract shared structures, in TOPIC-FREE vocabulary, each with a query
  3. fetch a few OpenAlex candidates per hypothesis query
  4. judge_bridge per candidate: structural match to A and to B separately
       -> gate = min (a bridge fails at its weaker pier), rank = product

Gold pairs (answer known):
  - 群れの移動  +  風・乱流        -> Toner-Tu / active-matter hydrodynamics
  - 株価予測    +  弾道・着弾推定  -> Kalman filter / state-space estimation

Run from repo root with OPENAI_API_KEY set:
  python scripts/bybridge_b0_probe.py                # full live probe
  python scripts/bybridge_b0_probe.py --runs 3       # repeat hypothesis gen (stability)
  python scripts/bybridge_b0_probe.py --no-collect   # schemas + hypotheses only (no OpenAlex)
  python scripts/bybridge_b0_probe.py --show-prompts  # print prompts + fixtures, no API calls

Offline note: with no key/network the LLM calls return None and the script reports a
clean "needs API key" status per pair instead of crashing; --show-prompts works offline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.core.input_schema import validate_and_normalize  # noqa: E402
from src.core.models import Work  # noqa: E402
from src.pipeline.classify import _extract_theme_schema, _llm_call, _parse_array, _parse_object  # noqa: E402
from src.pipeline.collect import _clean_query  # noqa: E402
from src.openalex.client import OpenAlexClient, OpenAlexConfig, OpenAlexError  # noqa: E402
from src.openalex.parser import normalize_results  # noqa: E402
from src.pipeline.filter import filter_has_abstract, filter_retracted  # noqa: E402

_MODEL = "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Gold-test fixtures: two theme pairs whose bridge is known in the literature.
# Each side is a full ThemeInput payload (overview 200-1200 chars, 2-5 assumptions)
# so the SAME _extract_theme_schema the real pipeline uses can run on it unchanged.
# ---------------------------------------------------------------------------
GOLD_PAIRS = [
    {
        "name": "flock x wind",
        "expected_bridge": "Toner-Tu / active-matter hydrodynamics (collective transport of "
        "many self-driven units described as a continuum)",
        "theme_a": {
            "theme_overview": (
                "鳥やイワシの群れは、中央の指揮者がいないのに、個体どうしの局所的な相互作用だけで"
                "全体が一つの流れのように向きを変え、密度の波を伝える。本テーマでは、こうした自己駆動する"
                "多数個体の集団運動が、どの条件で秩序立った大規模な流れとして立ち上がり、どの条件で崩れて"
                "乱れるのかを明らかにしたい。個体数・相互作用半径・ノイズ強度を変えたときの秩序相転移を"
                "定量化し、群れ全体の輸送と密度ゆらぎの法則を記述することを目的とする。"
            ),
            "goal": "自己駆動する多数個体の集団運動が秩序ある大規模な流れとして立ち上がる条件を定量化する",
            "why_problem": "群れの制御・予測は生態調査やドローン群制御の基盤になるため",
            "approach_type": "experiment",
            "assumptions": [
                "個体は局所的な近傍とだけ相互作用する",
                "全体を統率する中央指令は存在しない",
                "ノイズが大きいと秩序が崩れる",
            ],
            "scope": {"field": "集団行動・生物物理", "scale": "large", "time_range": "no_limit"},
            "keywords": {"include": ["collective motion", "flocking", "self-propelled"], "exclude": []},
            "concern": "秩序の立ち上がりを測る指標が恣意的になり再現しないのではないか",
        },
        "theme_b": {
            "theme_overview": (
                "大気の流れは、無数の微小な渦が相互に作用しながらエネルギーを大きなスケールから小さな"
                "スケールへ受け渡し、密度や速度のゆらぎを伝えていく。本テーマでは、乱流場における"
                "速度ゆらぎと運動量の輸送が、どの条件で組織だったコヒーレント構造として現れ、どの条件で"
                "完全な乱れに崩れるのかを明らかにしたい。レイノルズ数や外力の強さを変えたときの"
                "ゆらぎのスペクトルと輸送の法則を、連続体の場の方程式として記述することを目的とする。"
            ),
            "goal": "乱流場における速度ゆらぎと運動量輸送がコヒーレント構造として組織する条件を定量化する",
            "why_problem": "気象予測やエネルギー散逸の理解は防災・工学の基盤になるため",
            "approach_type": "experiment",
            "assumptions": [
                "渦は局所的に相互作用しエネルギーをカスケードさせる",
                "外力とノイズが秩序と乱れの境界を決める",
                "流れは連続体の場として記述できる",
            ],
            "scope": {"field": "流体力学・乱流", "scale": "large", "time_range": "no_limit"},
            "keywords": {"include": ["turbulence", "fluid dynamics", "momentum transport"], "exclude": []},
            "concern": "コヒーレント構造の定義が恣意的になり比較できないのではないか",
        },
    },
    {
        "name": "stock x ballistics",
        "expected_bridge": "Kalman filter / recursive state-space estimation (tracking a moving "
        "target's hidden state from noisy sequential observations)",
        "theme_a": {
            "theme_overview": (
                "株価や為替は、観測できる価格そのものは激しいノイズに覆われており、その背後にある"
                "本当の状態（トレンドやボラティリティ）は直接は見えない。本テーマでは、ノイズの乗った"
                "逐次的な価格観測の系列から、背後で動いている隠れた状態を時々刻々と推定し、次の時点の"
                "値を予測する手法を明らかにしたい。観測ノイズと状態遷移の不確実性を分離してモデル化し、"
                "新しい観測が来るたびに推定を逐次更新する枠組みを構築することを目的とする。"
            ),
            "goal": "ノイズの乗った逐次観測から隠れた状態を推定し次時点の値を予測する枠組みを構築する",
            "why_problem": "金融の予測誤差は運用リスクに直結するため",
            "approach_type": "application",
            "assumptions": [
                "観測される価格には大きなノイズが乗っている",
                "背後に直接は見えない状態変数が時間発展している",
                "新しい観測ごとに推定を更新できる",
            ],
            "scope": {"field": "金融時系列", "scale": "large", "time_range": "last_10_years"},
            "keywords": {"include": ["state estimation", "time series", "forecasting"], "exclude": []},
            "concern": "ノイズと真の状態の分離が恣意的になり予測が外れるのではないか",
        },
        "theme_b": {
            "theme_overview": (
                "飛翔する砲弾やミサイルの着弾地点を予測するには、レーダーが返す位置の観測値が"
                "ノイズに汚れている上に、対象は重力や空気抵抗を受けながら刻々と動き続ける。本テーマでは、"
                "ノイズの乗った逐次的な位置観測の系列から、対象の真の位置と速度という隠れた状態を"
                "時々刻々と推定し、未来の軌道と着弾点を予測する手法を明らかにしたい。観測誤差と"
                "運動モデルの不確実性を分離し、観測が届くたびに推定を逐次更新する枠組みを構築することを目的とする。"
            ),
            "goal": "ノイズの乗った逐次観測から飛翔体の隠れた状態を推定し未来の軌道を予測する枠組みを構築する",
            "why_problem": "着弾予測の誤差は防空・安全に直結するため",
            "approach_type": "application",
            "assumptions": [
                "レーダー観測には誤差が乗っている",
                "対象は運動方程式に従って状態が時間発展する",
                "観測が届くたびに推定を更新できる",
            ],
            "scope": {"field": "弾道・航跡推定", "scale": "large", "time_range": "no_limit"},
            "keywords": {"include": ["target tracking", "trajectory estimation", "radar"], "exclude": []},
            "concern": "観測誤差と運動モデル誤差の切り分けが恣意的になるのではないか",
        },
    },
]


# ---------------------------------------------------------------------------
# THE HEART OF bybridge (B-0): shared-structure hypothesis generation.
# Given both themes' Purpose/Mechanism schemas, propose abstract structures that
# could be ISOMORPHIC across the two — in vocabulary that contains NEITHER theme's
# topic words, specific enough to be transferable (the "membrane/tension/strike"
# level, not the "both make sound" level). Each hypothesis carries an OpenAlex query.
# ---------------------------------------------------------------------------
_HYP_SYSTEM = (
    "You find the ABSTRACT RELATIONAL STRUCTURE that two research themes from different "
    "domains might SHARE — the formal shape both are instances of, stripped of every topic word.\n"
    "You are given each theme's Purpose and Mechanism. Propose 2-4 candidate shared structures.\n"
    "ABSTRACTION CALIBRATION (this is the whole game):\n"
    "- TOO ABSTRACT (reject): 'a feedback loop', 'optimization under noise', 'a dynamical system'. "
    "These fit almost anything and produce FALSE bridges. The drum/conga pair is a real isomorphism "
    "because it matches at the mechanism level (a struck membrane under tension), not at 'both make sound'.\n"
    "- TOO CONCRETE (reject): anything that names either theme's own domain, phenomenon, or surface "
    "keywords. That is the trivial intersection, not a bridge.\n"
    "- RIGHT LEVEL: a structure concrete enough that a method or law could be TRANSFERRED between the "
    "two (e.g. 'collective transport of many locally-coupled self-driven units described as a continuum "
    "field', 'recursive estimation of a hidden moving state from noisy sequential observations').\n"
    "For each candidate return an object with:\n"
    "  structure: one sentence naming the shared abstract structure, NO topic words from either theme\n"
    "  why_a: how theme A is an instance of it\n"
    "  why_b: how theme B is an instance of it\n"
    "  abstraction_self_check: 'right' | 'too_abstract' | 'too_concrete' — your honest rating\n"
    "  query: 3-5 plain OpenAlex keywords naming the structure in NEUTRAL/FORMAL terms; NO topic words "
    "from either theme, NO 'x'/'X'/'×' token\n"
    "Return ONLY a JSON array of these objects, best first."
)


def generate_bridge_hypotheses(schema_a: dict, schema_b: dict, model: str = _MODEL, temperature: float = 0.7) -> List[dict]:
    text = _llm_call({
        "model": model,
        "input": [
            {"role": "system", "content": _HYP_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Theme A:\n"
                    f"  purpose: {schema_a.get('purpose')}\n"
                    f"  mechanism: {schema_a.get('mechanism')}\n"
                    "Theme B:\n"
                    f"  purpose: {schema_b.get('purpose')}\n"
                    f"  mechanism: {schema_b.get('mechanism')}\n\n"
                    "Propose 2-4 shared abstract structures at the transferable level. JSON array only."
                ),
            },
        ],
        "temperature": temperature,
    })
    if not text:
        return []
    arr = _parse_array(text) or []
    out: List[dict] = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        item["query"] = _clean_query(str(item.get("query") or ""))
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Bridge judge: structural match to A and to B SEPARATELY. Gate = min (a bridge
# fails at its weaker pier); rank = product. Surface-only overlap is flagged as a
# false bridge (the "both make sound" trap).
# ---------------------------------------------------------------------------
_JUDGE_SYSTEM = (
    "You judge whether a paper is a genuine STRUCTURAL BRIDGE between two research themes, "
    "i.e. its core method/finding is an instance of an abstract structure that BOTH themes also "
    "instantiate (Gentner analogy: shared RELATIONS, not shared surface topic).\n"
    "Score the paper's structural match to EACH theme separately, 0.0-1.0:\n"
    "  - 0.7-1.0: the paper's causal/mechanistic structure clearly maps onto the theme's purpose+mechanism\n"
    "  - 0.3-0.6: partial / one-relation overlap\n"
    "  - 0.0-0.2: only surface/lexical overlap, or no real relation (Anomaly)\n"
    "Also set false_bridge=true if the only thing connecting the two themes via this paper is a "
    "vague abstraction ('both involve feedback/noise/optimization') rather than a transferable mechanism.\n"
    "Return ONLY a JSON object: {match_a, match_b, false_bridge, shared_structure, note} (note in Japanese, 1 sentence)."
)


def judge_bridge(work: Work, schema_a: dict, schema_b: dict, structure_hint: str, model: str = _MODEL) -> Optional[dict]:
    text = _llm_call({
        "model": model,
        "input": [
            {"role": "system", "content": _JUDGE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Paper title: {work.title}\n"
                    f"Paper abstract: {(work.abstract or '')[:1500]}\n\n"
                    f"Candidate shared structure (hypothesis): {structure_hint}\n\n"
                    f"Theme A purpose/mechanism: {schema_a.get('purpose')} / {schema_a.get('mechanism')}\n"
                    f"Theme B purpose/mechanism: {schema_b.get('purpose')} / {schema_b.get('mechanism')}\n\n"
                    "JSON object only."
                ),
            },
        ],
        "temperature": 0.0,
    })
    if not text:
        return None
    obj = _parse_object(text)
    if not obj:
        return None
    try:
        ma = float(obj.get("match_a", 0.0))
        mb = float(obj.get("match_b", 0.0))
    except (TypeError, ValueError):
        return None
    return {
        "match_a": ma,
        "match_b": mb,
        "bridge_gate": min(ma, mb),      # weaker pier
        "bridge_rank": ma * mb,           # product
        "false_bridge": bool(obj.get("false_bridge", False)),
        "shared_structure": str(obj.get("shared_structure") or ""),
        "note": str(obj.get("note") or ""),
    }


def _fetch_candidates(query: str, client: OpenAlexClient, n: int) -> List[Work]:
    try:
        payload = client.get({"search": query, "per-page": max(n * 3, 10), "page": 1})
    except OpenAlexError:
        return []
    works = filter_has_abstract(filter_retracted(normalize_results(payload)))
    return works[:n]


def run_pair(pair: dict, *, runs: int, collect: bool, per_query: int, model: str) -> None:
    print("=" * 78)
    print(f"PAIR: {pair['name']}")
    print(f"EXPECTED BRIDGE: {pair['expected_bridge']}")
    print("=" * 78)

    theme_a = validate_and_normalize(pair["theme_a"])
    theme_b = validate_and_normalize(pair["theme_b"])
    schema_a = _extract_theme_schema(theme_a, model)
    schema_b = _extract_theme_schema(theme_b, model)
    print(f"  schema A: purpose={schema_a.get('purpose')!r} mechanism={schema_a.get('mechanism')!r}")
    print(f"  schema B: purpose={schema_b.get('purpose')!r} mechanism={schema_b.get('mechanism')!r}")
    if not schema_a.get("mechanism") and not schema_b.get("mechanism"):
        print("  [!] schemas empty — no API key / network. Skipping LLM stages for this pair.\n")
        return

    client = OpenAlexClient(OpenAlexConfig()) if collect else None
    for r in range(1, runs + 1):
        tag = f"run {r}/{runs}" if runs > 1 else "hypotheses"
        print(f"\n  --- {tag} ---")
        hyps = generate_bridge_hypotheses(schema_a, schema_b, model)
        if not hyps:
            print("    [!] no hypotheses (LLM unavailable).")
            continue
        for i, h in enumerate(hyps, 1):
            sc = h.get("abstraction_self_check", "?")
            print(f"    [{i}] ({sc}) {h.get('structure')}")
            print(f"        query: {h.get('query')}")
            if not collect or not h.get("query"):
                continue
            cands = _fetch_candidates(h["query"], client, per_query)
            if not cands:
                print("        (no candidates)")
                continue
            scored = []
            for w in cands:
                j = judge_bridge(w, schema_a, schema_b, str(h.get("structure")), model)
                if j:
                    scored.append((j, w))
            scored.sort(key=lambda t: t[0]["bridge_rank"], reverse=True)
            for j, w in scored[:per_query]:
                flag = " FALSE-BRIDGE" if j["false_bridge"] else ""
                print(
                    f"        - gate={j['bridge_gate']:.2f} rank={j['bridge_rank']:.2f}"
                    f" (A={j['match_a']:.2f} B={j['match_b']:.2f}){flag}"
                )
                print(f"          {w.title[:90]}")
                if j["note"]:
                    print(f"          note: {j['note']}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="bybridge B-0 false-bridge probe")
    ap.add_argument("--runs", type=int, default=1, help="repeat hypothesis generation per pair (stability)")
    ap.add_argument("--no-collect", action="store_true", help="schemas + hypotheses only, skip OpenAlex + judge")
    ap.add_argument("--per-query", type=int, default=3, help="candidates fetched+judged per hypothesis query")
    ap.add_argument("--model", default=_MODEL)
    ap.add_argument("--show-prompts", action="store_true", help="print prompts + fixtures and exit (offline)")
    args = ap.parse_args()

    if args.show_prompts:
        print("# HYPOTHESIS-GENERATION SYSTEM PROMPT\n")
        print(_HYP_SYSTEM)
        print("\n\n# BRIDGE-JUDGE SYSTEM PROMPT\n")
        print(_JUDGE_SYSTEM)
        print("\n\n# GOLD PAIRS\n")
        for p in GOLD_PAIRS:
            print(f"- {p['name']}: expected = {p['expected_bridge']}")
        return

    for pair in GOLD_PAIRS:
        run_pair(
            pair,
            runs=args.runs,
            collect=not args.no_collect,
            per_query=args.per_query,
            model=args.model,
        )


if __name__ == "__main__":
    main()
