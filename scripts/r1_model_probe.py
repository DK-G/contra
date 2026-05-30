"""R1 measurement probe: hold a known-good Track B candidate fixed, vary only the LLM model.

Goal (R1, see memory contra-r1-research): determine whether the hypothesis-quality ceiling
is set by MODEL CAPABILITY or by PROMPT DESIGN. We bypass collection/selection and feed a
fixed high-serendipity candidate (the quantum "anomalous subdiffusion" paper, prev serendipity
0.56 on the social theme) through the CURRENT prompts at gpt-4o-mini vs gpt-4o, end to end:

  Stage 1 (classify): _extract_theme_schema + _score_b_candidates_pm
                       -> purpose_sim, mechanism_dist, connection_label, serendipity_rationale (SPINE)
  Stage 2 (generate):  _llm_generate_track_b_text using the label + rationale spine
                       -> the 4-part hypothesis (the actual user-facing output)

Run from repo root with OPENAI_API_KEY set:
  python scripts/r1_model_probe.py
  python scripts/r1_model_probe.py --models gpt-4o-mini gpt-4o
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.core.input_schema import validate_and_normalize  # noqa: E402
from src.core.models import Work  # noqa: E402
from src.pipeline.classify import (  # noqa: E402
    _extract_theme_schema,
    _score_b_candidates_pm,
    _judge_b_candidates,
)
from src.pipeline.generate import _llm_generate_track_b_text  # noqa: E402
import json  # noqa: E402


# Fixed fixture: "Anomalous subdiffusion from subsystem symmetries" (W2963248591),
# prev serendipity 0.56 on the social theme. Abstract recovered from step9_social_v2 run.
QUANTUM_ABSTRACT = (
    "We introduce quantum circuits in two and three spatial dimensions which are classically "
    "simulable, despite producing a high degree of operator entanglement. We provide a partial "
    "characterization of these ``automaton'' quantum circuits and use them to study operator "
    "growth, information spreading, and local charge relaxation in quantum dynamics with "
    "subsystem symmetries, which we define as overlapping symmetries that act on lower-dimensional "
    "submanifolds. With these symmetries, we discover the anomalous subdiffusion of conserved "
    "charges; that is, the charges spread slower than diffusion in the dimension of the subsystem "
    "symmetry. By studying an effective operator hydrodynamics in the presence of these symmetries, "
    "we predict the charge autocorrelator to decay (i) as ln(t)/sqrt(t) in two dimensions with a "
    "conserved U(1) charge along intersecting lines and (ii) as 1/t^{3/4} in three spatial "
    "dimensions with intersecting planar U(1) symmetries. Through large-scale studies of automaton "
    "dynamics with these symmetries, we numerically observe charge relaxation that is consistent "
    "with these predictions. In both cases, the spatial charge distribution is distinctly "
    "non-Gaussian and reminiscent of the diffusion of charges along a fractal surface. We "
    "numerically study the onset of quantum chaos in the spreading of local operators under these "
    "automaton dynamics and observe power-law broadening of the ballistically propagating fronts "
    "of evolving operators in two and three dimensions and the saturation of out-of-time-ordered "
    "correlations to values consistent with quantum chaotic behavior."
)

FIXTURE_WORK = Work(
    id="https://openalex.org/W2963248591",
    title="Anomalous subdiffusion from subsystem symmetries",
    year=2019,
    venue="Physical Review B",
    doi="https://doi.org/10.1103/physrevb.100.214301",
    cited_by_count=0,
    abstract=QUANTUM_ABSTRACT,
)


def _load_social_theme():
    path = _REPO_ROOT / "data" / "samples" / "theme_social.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_and_normalize(payload)


# Hand-written RICH spine that already names the concrete quantitative finding.
# Used by --rich-spine to isolate whether the generation stage CAN produce a concrete
# hypothesis when the spine carries the specific finding (i.e. is the bottleneck classify or generate?).
RICH_LABEL = "保存則の重なりが拡散を律速する"
RICH_RATIONALE = (
    "論文の〈重なり合う部分系対称性（保存則）の数が多いほど電荷拡散が遅くなる異常サブ拡散："
    "通常拡散より遅く、2次元で ln(t)/√t、3次元で 1/t^{3/4} で減衰し分布は非ガウス的〉は、"
    "テーマの〈短期バズと長期浸透の分岐＝何が拡散をスローダウンさせるか〉における"
    "〈発信者の制約（フォロワー構造の閉鎖性）が拡散指数αに相当する律速要因〉に相当する"
)


def probe_model(model: str, theme, rich_spine: bool = False) -> dict:
    t0 = time.time()
    if rich_spine:
        purpose_sim, mechanism_dist = 0.5, 0.8
        serendipity = round(purpose_sim * mechanism_dist, 3)
        label = RICH_LABEL
        rationale = RICH_RATIONALE
        s = {"paper_purpose": "(rich-spine: skipped stage1)", "paper_mechanism": "(rich-spine: skipped stage1)"}
    else:
        schema = _extract_theme_schema(theme, model)
        scores = _score_b_candidates_pm([FIXTURE_WORK], schema, theme, model)
        s = scores.get(FIXTURE_WORK.id, {})
        purpose_sim = s.get("purpose_sim", 0.0)
        mechanism_dist = s.get("mechanism_dist", 0.0)
        serendipity = round(purpose_sim * mechanism_dist, 3)
        label = s.get("connection_label", "")
        rationale = s.get("serendipity_rationale", "")

    # R2 judge gate (skipped under rich-spine since stage1 is bypassed).
    judge = {}
    if not rich_spine:
        schema_for_judge = schema if not rich_spine else {"purpose": theme.goal, "mechanism": ""}
        judge = _judge_b_candidates([(FIXTURE_WORK, s)], schema_for_judge, theme, model).get(FIXTURE_WORK.id, {})

    # Stage 2: generation uses the label + rationale spine (as main.py wires it).
    gen = _llm_generate_track_b_text(theme, FIXTURE_WORK, f"【接続点: {label}】", model, rationale)
    if gen:
        relationship, summary, hypothesis, caution = gen
    else:
        relationship = summary = hypothesis = caution = "(generation failed)"

    return {
        "model": model,
        "elapsed_s": round(time.time() - t0, 1),
        "purpose_sim": purpose_sim,
        "mechanism_dist": mechanism_dist,
        "serendipity": serendipity,
        "paper_purpose": s.get("paper_purpose", ""),
        "paper_mechanism": s.get("paper_mechanism", ""),
        "paper_finding": s.get("paper_finding", ""),
        "connection_label": label,
        "serendipity_rationale": rationale,
        "judge_structural_depth": judge.get("structural_depth"),
        "judge_applicability": judge.get("applicability"),
        "judge_has_causal_pm": judge.get("has_causal_pm"),
        "judge_reason": judge.get("judge_reason"),
        "summary": summary,
        "relationship": relationship,
        "hypothesis": hypothesis,
        "caution": caution,
    }


def _print_result(r: dict) -> None:
    print("=" * 78)
    print(f"MODEL: {r['model']}   ({r['elapsed_s']}s)")
    print("-" * 78)
    print(f"  purpose_sim    : {r['purpose_sim']}")
    print(f"  mechanism_dist : {r['mechanism_dist']}")
    print(f"  serendipity    : {r['serendipity']}")
    print(f"  paper_purpose  : {r['paper_purpose']}")
    print(f"  paper_mechanism: {r['paper_mechanism']}")
    print(f"  paper_finding  : {r.get('paper_finding', '')}")
    print(f"\n  [STAGE 1 SPINE]")
    print(f"  connection_label     : {r['connection_label']}")
    print(f"  serendipity_rationale: {r['serendipity_rationale']}")
    print(f"\n  [R2 JUDGE GATE]")
    print(f"  structural_depth: {r.get('judge_structural_depth')}  applicability: {r.get('judge_applicability')}  has_causal_pm: {r.get('judge_has_causal_pm')}")
    print(f"  judge_reason: {r.get('judge_reason')}")
    print(f"\n  [STAGE 2 OUTPUT]")
    print(f"  summary     : {r['summary']}")
    print(f"  relationship: {r['relationship']}")
    print(f"  ★hypothesis : {r['hypothesis']}")
    print(f"  caution     : {r['caution']}")
    print()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="R1 model probe (fixed candidate)")
    parser.add_argument("--models", nargs="+", default=["gpt-4o-mini", "gpt-4o"])
    parser.add_argument("--rich-spine", action="store_true",
                        help="Inject a hand-written rich spine (skip stage1) to isolate the generation stage")
    parser.add_argument("--out", default="output/r1_probe.json", help="JSON dump of all results")
    args = parser.parse_args(argv)

    if not os.getenv("OPENAI_API_KEY"):
        print("[error] OPENAI_API_KEY is not set", file=sys.stderr)
        return 1

    theme = _load_social_theme()
    print(f"THEME: {theme.theme_overview[:120]}...")
    print(f"FIXTURE: {FIXTURE_WORK.title}\n")

    if args.rich_spine:
        print("[mode] RICH-SPINE: stage1 bypassed, generation fed a hand-written concrete spine\n")
    results = []
    for model in args.models:
        print(f"[info] probing {model} ...")
        results.append(probe_model(model, theme, rich_spine=args.rich_spine))

    print()
    for r in results:
        _print_result(r)

    out_path = _REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
