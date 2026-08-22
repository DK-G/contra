"""Tests for the key-free (no-LLM) delegation path (stage a)."""

from __future__ import annotations

from src.core.models import Concept, Keywords, Scope, ThemeInput, Work
from src.pipeline.concept_distance import ThemeProfile
from src.pipeline.delegate import (
    assemble_keyless_bridge_document,
    build_bridge_entries,
    finalize_delegated_document,
    normalize_agent_scores,
    select_bridge_candidates_raw,
    work_from_material,
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


# --- Stage (c): agent scoring -> deterministic finalize ----------------------

def _material(wid, purpose_sim, mechanism_dist, **extra):
    base = {
        "id": wid,
        "title": f"paper {wid}",
        "abstract": "First. Second. Third. Fourth.",
        "year": 2024,
        "venue": "Journal",
        "cited_by_count": 7,
        "concepts": ["x"],
        "concept_tags": [{"name": "marine biology", "level": 1, "score": 0.5}],
        "referenced_works": ["B1"],
        "purpose_sim": purpose_sim,
        "mechanism_dist": mechanism_dist,
        "connection_label": "構造的接続",
        "serendipity_rationale": "rationale",
    }
    base.update(extra)
    return base


def test_work_from_material_rebuilds_work():
    w = work_from_material(_material("W", 0.7, 0.8))
    assert w.id == "W"
    assert w.referenced_works == ["B1"]
    assert w.concept_tags[0].name == "marine biology"


def test_normalize_agent_scores_requires_fields():
    import pytest
    with pytest.raises(ValueError):
        normalize_agent_scores([{"id": "W", "purpose_sim": 0.5}])  # missing mechanism_dist


def test_finalize_passes_strong_candidate_and_honors_agent_prose():
    # A1 grounding contract (default): agent prose needs verbatim quotes from both sides.
    mats = [_material("W", 0.7, 0.8, structural_depth=0.8, relationship="agent rel",
                      theme_quote="テーマ概要 目的 問題意識",
                      source_quote="First. Second. Third.")]
    diag = {}
    doc = finalize_delegated_document(mats, _theme(), count=1, diag=diag)
    entry = doc.sections[0].entries[0]
    assert entry.serendipity_score == 0.56
    assert entry.relationship == "agent rel"          # agent prose honored
    assert entry.usefulness_hypothesis == "rationale"  # rationale -> hypothesis
    assert entry.abstract_summary                      # structured fallback filled
    assert diag["status"] == "ok"


def test_finalize_drops_agent_anomaly():
    # Agent claims a connection but purpose_sim < 0.20 -> deterministic post-gate drops it.
    mats = [_material("W", 0.1, 0.9, structural_depth=0.9)]
    diag = {}
    doc = finalize_delegated_document(mats, _theme(), diag=diag)
    assert doc.sections[0].entries == []
    assert diag["reason"] == "all_anomaly"


# --- Stage (d): key-free Track A (byrepo) assembly ---------------------------

def _github_work(wid, reliability, title="acme/tool"):
    return Work(
        id=wid,
        title=title,
        year=2026,
        venue="GitHub",
        doi=None,
        cited_by_count=100,
        abstract="repo summary. second sentence. third sentence.",
        publication_type="github_repository",
        source_meta={
            "reliability_score": reliability,
            "license_name": "MIT",
            "issue_signal_summary": "issues 3件 / open 1 / closed 2",
            "impl_doc_score": 20, "lma_score": 18, "community_score": 15, "security_score": 12,
        },
    )


def test_build_track_a_entries_ranks_by_reliability():
    from src.pipeline.delegate import build_track_a_entries
    works = [_github_work("low", 30, "a/low"), _github_work("high", 85, "a/high"), _github_work("mid", 55, "a/mid")]
    entries = build_track_a_entries(works, count=2)
    assert [e.work.id for e in entries] == ["high", "mid"]
    assert entries[0].track == "A"
    assert entries[0].relationship_level == "高"   # 85 >= 70
    assert entries[1].relationship_level == "中"   # 55 in [40,70)


def test_keyless_track_a_document_fills_prose_without_llm():
    from src.pipeline.delegate import assemble_keyless_track_a_document
    works = [_github_work("W", 85)]
    doc = assemble_keyless_track_a_document(_theme(), works, count=1)
    entry = doc.sections[0].entries[0]
    assert entry.track == "A"
    assert entry.abstract_summary   # deterministic structured fill
    assert entry.relationship
    assert entry.caution
    assert entry.usefulness_hypothesis
