"""Tests for the key-free (no-LLM) delegation path (stage a)."""

from __future__ import annotations

from src.core.models import Concept, Keywords, Scope, ThemeInput, Work
from src.pipeline.concept_distance import ThemeProfile
from src.pipeline.delegate import (
    assemble_keyless_bridge_document,
    build_bridge_entries,
    select_bridge_candidates_raw,
)
from src.pipeline.generate import GenerationConfig, _structured_summary


def _theme() -> ThemeInput:
    return ThemeInput(
        theme_overview="テーマ概要",
        goal="目的",
        why_problem="問題意識",
        approach_type="experiment",
        assumptions=["仮説1"],
        scope=Scope(field="energy", scale="small", time_range="last_10_years"),
        keywords=Keywords(include=["grid"]),
    )


def _work(wid: str, refs, l01_names, abstract="A. B. C. D.") -> Work:
    return Work(
        id=wid,
        title=f"paper {wid}",
        year=2024,
        venue="Journal",
        doi=None,
        cited_by_count=5,
        abstract=abstract,
        concept_tags=[Concept(name=n, level=1, score=0.5) for n in l01_names],
        referenced_works=list(refs),
    )


# Theme near-field broad domain = {"energy systems"}.
_PROFILE = ThemeProfile(l01={"energy systems"})
_BRIDGES = {"B1", "B2", "B3"}


def test_select_ranks_by_shared_bridge_count():
    far_many = _work("W1", ["B1", "B2", "B3"], ["fluid dynamics"])   # 3 shared, far
    far_one = _work("W2", ["B1", "X"], ["ecology"])                  # 1 shared, far
    far_zero = _work("W3", ["Y", "Z"], ["linguistics"])             # 0 shared, far
    chosen = select_bridge_candidates_raw(
        [far_one, far_zero, far_many], _BRIDGES, profile=_PROFILE, count=2
    )
    assert [w.id for w in chosen] == ["W1", "W2"]


def test_select_drops_near_domain_myopia():
    near = _work("N", ["B1", "B2", "B3"], ["energy systems"])  # same broad domain
    far = _work("F", ["B1"], ["marine biology"])
    chosen = select_bridge_candidates_raw([near, far], _BRIDGES, profile=_PROFILE, count=5)
    assert [w.id for w in chosen] == ["F"]  # near-domain dropped despite more bridges


def test_build_entries_deterministic_scores():
    far = _work("F", ["B1", "B2"], ["marine biology"])  # no overlap -> distance 1.0
    entries = build_bridge_entries([far], _BRIDGES, profile=_PROFILE, count=1)
    assert len(entries) == 1
    e = entries[0]
    assert e.track == "B"
    assert "共有 2 本" in e.label
    assert e.distance_score == 1.0          # 1 - jaccard(0) = 1.0
    assert e.structure_score == 0.0         # LLM-pending
    assert e.serendipity_score == 0.0       # LLM-pending


def test_keyless_document_fills_4parts_without_llm():
    # No API key in env; structured assembly must complete and fill all 4 parts.
    abstract = "First sentence. Second sentence. Third sentence. Fourth."
    far = _work("F", ["B1", "B2"], ["marine biology"], abstract=abstract)
    doc = assemble_keyless_bridge_document(_theme(), [far], _BRIDGES, profile=_PROFILE, count=1)
    assert len(doc.sections) == 1
    entry = doc.sections[0].entries[0]
    # Deterministic structured fill: summary equals the structured summarizer output.
    assert entry.abstract_summary == _structured_summary(abstract, GenerationConfig())
    assert entry.relationship      # non-empty deterministic relationship
    assert entry.caution           # non-empty deterministic caution
    assert entry.usefulness_hypothesis
