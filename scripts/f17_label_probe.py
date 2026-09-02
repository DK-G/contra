"""F-17 probe (seihai 2026-08-27): byrepo `structured:true` 関係度 label vs theme relevance.

Replays the three anchors seihai reported — reliability/fit chosen so that rank score and
theme関連度 reproduce the observed numbers (62.0/1.0, 51.0/0.33, 47.0/0.33) — through the
REAL key-free Track A assembly and prints the rendered label lines. No network, no key.

    python scripts/f17_label_probe.py
"""
from __future__ import annotations

import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.core.models import Keywords, Scope, ThemeInput, Work
from src.core.output_spec import render_markdown
from src.pipeline.delegate import assemble_keyless_track_a_document
from src.pipeline.track_a import annotate_anchor_rank


def _anchor(name: str, reliability: int, fit: int, stars: int) -> Work:
    return Work(
        id=f"https://github.com/{name}", title=name, year=2026, venue="GitHub", doi=None,
        cited_by_count=stars, abstract="README summary. second. third.",
        publication_type="github_repository",
        source_meta={"reliability_score": reliability, "theme_fit_score": fit,
                     "license_name": "MIT", "issue_signal_summary": "-"},
    )


THEME = ThemeInput(
    theme_overview="K回連続の負の期間で退場させるカウンタを較正済みの逐次検定へ置き換える。" * 6,
    goal="退場ルールの偽陽性率を no-change null 下で測る",
    why_problem="固定Kのカウンタは較正されていない",
    approach_type="application",
    assumptions=["退場は単一指標で決まる", "null 下の偽陽性率は未測定"],
    scope=Scope(field="statistics", scale="small", time_range="last_10_years"),
    keywords=Keywords(include=["cusum", "drift", "sequential"]),
)

WORKS = [
    _anchor("IFCA-Advanced-Computing/frouros", 62, 30, 261),   # rank 62.0 / relevance 1.0
    _anchor("facebookresearch/Kats", 90, 10, 6460),             # rank 51.0 / relevance 0.33
    _anchor("SCStelz/security-investigator", 83, 10, 239),      # rank 47.0 / relevance 0.33
]

if __name__ == "__main__":
    annotate_anchor_rank(WORKS)
    doc = assemble_keyless_track_a_document(THEME, WORKS, count=3)
    for line in render_markdown(doc).splitlines():
        if line.startswith("### ") or "関係度" in line or "順位スコア" in line:
            print(line)
