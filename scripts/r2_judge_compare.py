"""R2 decision material: run several fixed candidates through stage1 (P/M + finding) and the
R2 judge gate in ONE call, side by side, with NO collection noise. Lets a human decide whether
the judge's hollow/genuine distinction is defensible (e.g. is the quantum subdiffusion pairing a
lexical 'diffusion' false-far, or a genuine far analogy?).

Run from repo root with OPENAI_API_KEY set:
  python scripts/r2_judge_compare.py
  python scripts/r2_judge_compare.py --runs 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.core.input_schema import validate_and_normalize  # noqa: E402
from src.core.models import Work  # noqa: E402
from src.pipeline.classify import (  # noqa: E402
    _STRUCT_DEPTH_GATE,
    _extract_theme_schema,
    _score_b_candidates_pm,
    _judge_b_candidates,
)

# Three fixed candidates spanning the spectrum (abstracts recovered from prior runs):
#  - quantum: the previously-"best" far analogy (serendipity 0.56) — suspected lexical 'diffusion'
#  - epidemic: an epidemiology paper that PASSED the judge, with a concrete R0 54% finding
#  - climate: the climate-tipping paper the first real run surfaced (cascade/domino network)
FIXTURES = [
    Work(
        id="quantum",
        title="Anomalous subdiffusion from subsystem symmetries",
        year=2019, venue="Physical Review B", doi=None, cited_by_count=0,
        abstract=(
            "We introduce quantum circuits in two and three spatial dimensions which are "
            "classically simulable, despite producing a high degree of operator entanglement. "
            "We study operator growth, information spreading, and local charge relaxation in "
            "quantum dynamics with subsystem symmetries (overlapping symmetries acting on "
            "lower-dimensional submanifolds). With these symmetries we discover the anomalous "
            "subdiffusion of conserved charges; charges spread slower than diffusion in the "
            "dimension of the subsystem symmetry. We predict the charge autocorrelator to decay "
            "as ln(t)/sqrt(t) in two dimensions and as 1/t^{3/4} in three dimensions, and "
            "numerically observe charge relaxation consistent with these predictions; the spatial "
            "charge distribution is distinctly non-Gaussian, reminiscent of diffusion along a "
            "fractal surface."
        ),
    ),
    Work(
        id="epidemic",
        title="Pandemia de la COVID-19 y las Politicas de Salud Publica en el Peru",
        year=2020, venue="—", doi=None, cited_by_count=0,
        abstract=(
            "OBJECTIVE: analyze the dynamics of COVID-19 in Peru, estimate and evaluate the "
            "impact of the suppression public policy (quarantine). METHODS: The SIR "
            "epidemiological model and estimation with ordinary Least Squares (OLS). RESULTS: "
            "the basic reproduction number (Ro) fell from 6.0 to 3.2, reduced by 54% due to the "
            "suppression strategy; two months later it falls to 1.7, but remains high and the "
            "level of infected continues to expand. CONCLUSION: COVID-19 grows exponentially; "
            "the suppression strategy flattened the contagion curve, avoiding health-system "
            "collapse."
        ),
    ),
    Work(
        id="climate",
        title="Interacting tipping elements increase risk of climate domino effects",
        year=2021, venue="Earth System Dynamics", doi=None, cited_by_count=0,
        abstract=(
            "With progressing global warming there is increased risk that one or several tipping "
            "elements in the climate system cross a critical threshold. While the underlying "
            "processes are fairly well-understood, it is unclear how their interactions impact "
            "overall stability. We study physical interactions among the Greenland and West "
            "Antarctic ice sheets, the AMOC and the Amazon rainforest using a conceptual network "
            "approach, propagating uncertainties via Monte Carlo ensembles. We find interactions "
            "tend to destabilise the network of tipping elements; the polar ice sheets are often "
            "the initiators of tipping cascades, while the AMOC acts as a mediator transmitting "
            "cascades."
        ),
    ),
]


def _load_social_theme():
    payload = json.loads((_REPO_ROOT / "data" / "samples" / "theme_social.json").read_text(encoding="utf-8"))
    return validate_and_normalize(payload)


def run_once(theme, schema, model: str) -> list:
    scores = _score_b_candidates_pm(FIXTURES, schema, theme, model)
    survivors = [(w, scores.get(w.id, {})) for w in FIXTURES]
    judged = _judge_b_candidates(survivors, schema, theme, model)
    rows = []
    for w in FIXTURES:
        s = scores.get(w.id, {})
        j = judged.get(w.id, {})
        sd = j.get("structural_depth")
        cpm = j.get("has_causal_pm")
        # Calibrated gate: structural_depth only; loose causal link is kept (thought-seed).
        passes = (sd is not None and sd >= _STRUCT_DEPTH_GATE)
        rows.append({
            "id": w.id,
            "purpose_sim": s.get("purpose_sim"),
            "mechanism_dist": s.get("mechanism_dist"),
            "paper_finding": s.get("paper_finding", ""),
            "serendipity_rationale": s.get("serendipity_rationale", ""),
            "structural_depth": sd,
            "applicability": j.get("applicability"),
            "has_causal_pm": cpm,
            "judge_reason": j.get("judge_reason", ""),
            "gate": "PASS" if passes else "REJECT(hollow)",
        })
    return rows


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args(argv)
    if not os.getenv("OPENAI_API_KEY"):
        print("[error] OPENAI_API_KEY not set", file=sys.stderr)
        return 1
    theme = _load_social_theme()
    schema = _extract_theme_schema(theme, args.model)
    print(f"THEME purpose : {schema['purpose']}")
    print(f"THEME mechanism: {schema['mechanism']}")
    print(f"GATE: structural_depth >= {_STRUCT_DEPTH_GATE} AND has_causal_pm == True\n")
    all_runs = []
    for r in range(args.runs):
        print(f"########## RUN {r + 1}/{args.runs} ##########")
        rows = run_once(theme, schema, args.model)
        all_runs.append(rows)
        for row in rows:
            print(f"\n--- {row['id'].upper()} -> {row['gate']} ---")
            print(f"  purpose_sim={row['purpose_sim']} mechanism_dist={row['mechanism_dist']}")
            print(f"  structural_depth={row['structural_depth']} applicability={row['applicability']} has_causal_pm={row['has_causal_pm']}")
            print(f"  finding : {row['paper_finding']}")
            print(f"  mapping : {row['serendipity_rationale']}")
            print(f"  judge   : {row['judge_reason']}")
        print()
    (_REPO_ROOT / "output" / "r2_judge_compare.json").write_text(
        json.dumps(all_runs, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[ok] wrote output/r2_judge_compare.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
