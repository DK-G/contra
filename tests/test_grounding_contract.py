"""A1 (2026-08-22 ruling): the quote-then-claim grounding contract.

The calling agent is the LLM; contra is the deterministic verifier. Relational prose
must arrive with verbatim quotes from BOTH sides (theme text / candidate abstract);
code checks the quotes occur, drops ungrounded prose (scores untouched), and names
the failure — the F-04 fabrication ("需要の変動" on a theme that never mentions
demand) becomes structurally impossible to render.
"""

from __future__ import annotations

from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.delegate import (
    finalize_delegated_document,
    theme_grounding_text,
    verify_grounding,
)


def _theme():
    return ThemeInput(
        theme_overview="単一軸の事前登録停止規則が、規則の見ていない軸での劣化に対して恒久的に沈黙する問題を扱う。" * 3,
        goal="停止規則の盲点を検出する仕組みを設計する",
        why_problem="見ていない軸の劣化は測定されないまま蓄積する",
        approach_type="application",
        assumptions=["停止規則は単一軸で定義される", "未監視軸の劣化は自己申告されない"],
        scope=Scope(field="statistics", scale="small", time_range="last_10_years"),
        keywords=Keywords(include=[], exclude=[]),
    )


def _material(**over):
    m = {
        "id": "W1", "title": "Equivalence trials in medicine",
        "abstract": "Superiority designs cannot conclude equivalence; a dedicated pre-specified rule is required.",
        "year": 1996, "venue": "BMJ", "doi": "10.1/x", "cited_by_count": 1032,
        "purpose_sim": 0.7, "mechanism_dist": 0.8, "structural_depth": 0.9,
    }
    m.update(over)
    return m


def test_grounded_prose_passes():
    m = _material(
        relationship="論文の同等性設計の要請はテーマの停止規則の盲点に対応する",
        theme_quote="規則の見ていない軸での劣化",
        source_quote="a dedicated pre-specified rule is required",
    )
    assert verify_grounding(m, theme_grounding_text(_theme())) == []


def test_fabricated_theme_side_proposition_is_refused():
    # The F-04 shape: the theme-side proposition does not exist in the submitted text.
    m = _material(
        relationship="需要の変動が在庫管理の難易度を高める点で対応する",
        theme_quote="需要の変動が在庫管理の難易度を高める",     # fabricated — not in theme
        source_quote="a dedicated pre-specified rule is required",
    )
    failures = verify_grounding(m, theme_grounding_text(_theme()))
    assert any("theme_quote" in f and "存在しない" in f for f in failures)


def test_prose_without_quotes_is_refused():
    m = _material(serendipity_rationale="この論文はテーマに転用できる")
    failures = verify_grounding(m, theme_grounding_text(_theme()))
    assert len(failures) == 2                    # both quotes missing


def test_short_quote_cannot_anchor():
    m = _material(relationship="r", theme_quote="停止規則", source_quote="rule")
    failures = verify_grounding(m, theme_grounding_text(_theme()))
    assert len(failures) == 2                    # below the 10-char floor


def test_whitespace_and_case_normalisation():
    m = _material(
        relationship="r",
        theme_quote="規則の見ていない軸での  劣化",             # extra internal spaces
        source_quote="A DEDICATED pre-specified rule is required",  # case difference
    )
    assert verify_grounding(m, theme_grounding_text(_theme())) == []


def test_no_prose_needs_no_quotes():
    assert verify_grounding(_material(), theme_grounding_text(_theme())) == []


def test_finalize_drops_ungrounded_prose_keeps_score_and_names_failure():
    fabricated = _material(
        relationship="需要の変動が在庫管理の難易度を高める点で対応",
        serendipity_rationale="需要変動とテーマの対応",
        theme_quote="需要の変動が在庫管理",
        source_quote="a dedicated pre-specified rule is required",
    )
    diag: dict = {}
    doc = finalize_delegated_document([fabricated], _theme(), count=1, diag=diag)
    entries = doc.sections[0].entries
    assert len(entries) == 1                                   # the SCORE still passed the gates
    assert "需要の変動" not in (entries[0].relationship or "")  # fabricated prose did not render
    gf = diag["grounding_failures"]
    assert gf[0]["id"] == "W1" and any("theme_quote" in r for r in gf[0]["reasons"])


def test_finalize_keeps_grounded_prose():
    grounded = _material(
        relationship="論文の『専用の事前規則が要る』はテーマの停止規則の盲点に対応する",
        theme_quote="規則の見ていない軸での劣化",
        source_quote="a dedicated pre-specified rule is required",
    )
    diag: dict = {}
    doc = finalize_delegated_document([grounded], _theme(), count=1, diag=diag)
    assert "grounding_failures" not in diag
    assert "停止規則の盲点" in doc.sections[0].entries[0].relationship


def test_grounded_only_false_restores_old_behaviour():
    fabricated = _material(relationship="接地なしの散文", serendipity_rationale="r")
    diag: dict = {}
    doc = finalize_delegated_document([fabricated], _theme(), count=1, diag=diag,
                                      grounded_only=False)
    assert "接地なしの散文" in doc.sections[0].entries[0].relationship


# --- F-19 (2026-09-01, seihai): 照合不能 vs 不一致 -----------------------------------
# Verification runs against the material the CALLER echoed, not contra's own record. When
# the caller sends only `id` + scores, the haystack is empty and a verbatim-correct quote
# was reported as "存在しない（逐語一致が必要）" — which reads as "your quote was
# fabricated" and sent seihai to re-audit its own prose (the material-echo warning was
# printed in a separate block with no stated causal link).

def test_missing_material_is_reported_as_unverifiable_not_as_mismatch():
    bare = _material(
        relationship="論文の主張はテーマの盲点に対応する",
        theme_quote="規則の見ていない軸での劣化",
        source_quote="a dedicated pre-specified rule is required",   # verbatim-correct
    )
    bare.pop("title"); bare.pop("abstract")                          # caller echoed neither
    failures = verify_grounding(bare, theme_grounding_text(_theme()))
    assert len(failures) == 1
    assert "照合不能" in failures[0]
    assert "材料欄の欠落が原因" in failures[0]
    assert "存在しない" not in failures[0]        # must NOT accuse the quote


def test_partial_echo_mismatch_names_the_missing_field():
    # title echoed, abstract dropped: a real mismatch, but the abstract quote could never
    # have matched. Say so rather than letting it read as fabrication.
    partial = _material(
        relationship="r",
        theme_quote="規則の見ていない軸での劣化",
        source_quote="a dedicated pre-specified rule is required",
    )
    partial.pop("abstract")
    failures = verify_grounding(partial, theme_grounding_text(_theme()))
    assert len(failures) == 1
    assert "存在しない" in failures[0]            # still a mismatch...
    assert "abstract が送られていません" in failures[0]   # ...with its likely cause named


def test_genuine_mismatch_with_full_material_stays_unqualified():
    # Regression guard: when every field IS echoed, a fabricated quote must still be
    # reported plainly — the F-19 hint must not soften real fabrication.
    m = _material(
        relationship="r",
        theme_quote="規則の見ていない軸での劣化",
        source_quote="this sentence appears in neither the title nor the abstract",
    )
    failures = verify_grounding(m, theme_grounding_text(_theme()))
    assert len(failures) == 1
    assert "存在しない" in failures[0]
    assert "照合不能" not in failures[0] and "※" not in failures[0]


def test_has_unverifiable_failure_predicate():
    from src.pipeline.delegate import has_unverifiable_failure
    assert has_unverifiable_failure(["照合不能: 候補の title/abstract が送られていない…"])
    assert not has_unverifiable_failure(["source_quote が候補の title/abstract に存在しない（逐語一致が必要）"])
