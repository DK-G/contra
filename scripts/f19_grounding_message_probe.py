"""F-19 probe (2026-09-01, seihai): grounding failure vs. missing echoed material.

seihai scored 5 raw_only candidates, pulled `source_quote` VERBATIM from each candidate's
abstract, and got "5/5 接地検証失敗 — source_quote が候補の title/abstract に存在しない
（逐語一致が必要）". The quotes were correct; the caller had sent only `id` + its score
fields, so the haystack contra matched against was empty. The message read as "your quote
was fabricated" and sent the caller to audit its own prose.

This probe replays both submissions through the REAL `delegate_finalize` handler (no
network, no API key) and prints the diagnostic block the caller actually sees.

    python scripts/f19_grounding_message_probe.py
"""
from __future__ import annotations

import os, sys, pathlib, tempfile
_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
# finalize records adopted papers under ./data/history — run from a throwaway cwd so the
# probe's fake candidate never enters the real dedup store.
os.chdir(tempfile.mkdtemp(prefix='contra_f19_probe_'))

from src.mcp_server import StdinMcpServer

THEME = {
    "theme_overview": "選択圧の一部が沈黙しても探索そのものは正常に見える、という構造を扱う。"
                      "単一軸の停止規則は、規則の見ていない軸での劣化に対して恒久的に沈黙する。"
                      "探索は走り続け、指標は動き、記録は残る。にもかかわらず選抜が効いていない"
                      "軸が存在しうる。この沈黙は候補が弱いのとも候補が無いのとも異なる第三の"
                      "様式であり、事後の記録からは区別が付かない。したがって検出は事前の"
                      "生存確認に依存する。" * 2,
    "goal": "沈黙した選択圧を検出する仕組みを設計する",
    "why_problem": "見ていない軸の劣化は測定されないまま蓄積する",
    "approach_type": "application",
    "assumptions": ["停止規則は単一軸で定義される", "未監視軸の劣化は自己申告されない"],
    "scope_field": "biology", "scope_scale": "small", "scope_time_range": "last_10_years",
}

# The real shape of a raw_only candidate as contra returns it.
FULL = {
    "id": "W2000000001",
    "title": "Cryptic genetic variation and the release of hidden selective potential",
    "abstract": "Selection can act on a trait while leaving no detectable signal in the "
                "observed phenotype, so a population under stabilizing selection may appear "
                "static while variance accumulates below the threshold of measurement.",
    "year": 2013, "venue": "Genetics", "doi": "10.1/probe", "cited_by_count": 812,
    "concept_tags": [{"name": "cryptic variation"}, {"name": "stabilizing selection"}],
    "purpose_sim": 0.62, "mechanism_dist": 0.86, "structural_depth": 0.88,
    "relationship": "個体群が静止して見えるまま分散が蓄積する構造は、停止規則が沈黙したまま劣化が進む構造に対応する",
    "serendipity_rationale": "測定閾値の下で進む変化という機序が共通する",
    "theme_quote": "規則の見ていない軸での劣化",
    "source_quote": "may appear static while variance accumulates below the threshold of measurement",
}

# seihai's 1st submission: join key + its own scoring fields, prose + quotes, NO material echo.
BARE = {k: v for k, v in FULL.items()
        if k not in ("title", "abstract", "year", "venue", "cited_by_count", "concept_tags")}

# The partial-echo shape: title echoed, abstract dropped. The haystack is NON-empty, so
# this is a genuine mismatch — but an abstract-derived quote can never match it, and the
# unqualified "存在しない" still reads as fabrication.
PARTIAL = {k: v for k, v in FULL.items() if k != "abstract"}


def run(label: str, candidate: dict) -> None:
    srv = StdinMcpServer.__new__(StdinMcpServer)          # the handler is pure/local
    out = srv._execute_delegate_finalize({**THEME, "candidates": [candidate], "count": 1})
    text = out["content"][0]["text"]
    body = text.split("<untrusted_external_data>", 1)[-1]
    head = body.split("# ", 1)[0].strip()                 # the diagnostic block only
    print("===== " + label + " =====")
    print(head)
    print("")


if __name__ == "__main__":
    run("(1) id + 採点欄のみ ＝ seihai 2026-09-01 の1回目", BARE)
    run("(2) 全欄 echo ＝ 同じ引用・同じスコアで再投", FULL)
    run("(3) title のみ echo・abstract 欠落 ＝ 部分 echo", PARTIAL)
