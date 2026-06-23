"""Key-free (no-LLM) delegation path: contra as a material provider.

Stage (a) of the MCP-client delegation design
(``docs/research/mcp_subscription_delegation.md``): run a full ``bybridge`` loop
— collect → deterministic bridge ranking → structured 4-part assembly → markdown —
with **no LLM API key**. The LLM-dependent scoring (purpose_sim × mechanism_dist,
hollow judgement) and the polished 4-part authoring are left for the calling agent
(Max/Opus) to fill in later; here every step is deterministic so the loop completes
offline (OpenAlex collection only).

These functions are pure (they take already-collected candidates/bridges as input),
so they unit-test without network or LLM access.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from typing import Any, Dict, List, Optional, Sequence, Set

from src.core.models import (
    Concept,
    OutputDocument,
    OutputEntry,
    OutputSection,
    ThemeInput,
    Work,
)
from src.pipeline.classify import apply_post_gates
from src.pipeline.bridges import annotate_bridge_signals, bridge_rank_key, shared_bridge_count
from src.pipeline.concept_distance import ThemeProfile, near_domain_signal
from src.pipeline.generate import GenerationConfig, fill_track_entries


def _l01_jaccard(work: Work, profile: Optional[ThemeProfile]) -> float:
    """Deterministic L0/L1 concept overlap between a work and the theme (0..1)."""
    if profile is None or not getattr(profile, "l01", None):
        return 0.0
    work_l01 = {tag.name for tag in work.concept_tags if tag.level <= 1 and tag.name}
    union = work_l01 | profile.l01
    if not union:
        return 0.0
    return len(work_l01 & profile.l01) / len(union)


def select_bridge_candidates_raw(
    cands: Sequence[Work],
    bridges: Set[str],
    *,
    profile: Optional[ThemeProfile] = None,
    count: int = 3,
    drop_near_domain: bool = True,
) -> List[Work]:
    """Deterministic, key-free candidate selection.

    Drops same-broad-domain (myopia) candidates via the deterministic L0/L1 Jaccard
    gate, then ranks by shared citation-bridge count (more shared bridges = stronger
    structural link). No LLM. This is the code-layer pre-filter; the agent layer adds
    purpose/mechanism judgement on top.
    """
    pool = list(cands)
    if drop_near_domain and profile is not None and not profile.is_empty():
        pool = [w for w in pool if not near_domain_signal(w, profile)]
    # Rank by cross-community betweenness first, then co-citation strength (Phase 2):
    # a candidate routing through a bridge that connects many fields beats one whose shared
    # bridge only circulates inside a single field, even at equal shared-bridge count.
    annotate_bridge_signals(pool, bridges)
    pool.sort(key=bridge_rank_key, reverse=True)
    return pool[: max(count, 0)]


def build_bridge_entries(
    cands: Sequence[Work],
    bridges: Set[str],
    *,
    profile: Optional[ThemeProfile] = None,
    count: int = 3,
) -> List[OutputEntry]:
    """Build deterministic Track B entries (no LLM, no 4-part prose yet).

    distance_score comes from the deterministic L0/L1 Jaccard (far = high). The
    structure/serendipity scores require LLM judgement and stay at 0.0 for the
    delegated agent to fill.
    """
    chosen = select_bridge_candidates_raw(cands, bridges, profile=profile, count=count)
    entries: List[OutputEntry] = []
    for work in chosen:
        shared = shared_bridge_count(work, bridges)
        betweenness = int((work.source_meta or {}).get("bridge_betweenness", 0) or 0)
        distance = round(1.0 - _l01_jaccard(work, profile), 2)
        entries.append(
            OutputEntry(
                work=work,
                relationship="",
                abstract_summary="",
                caution="",
                track="B",
                label=f"引用ブリッジ（共有 {shared} 本 / 異分野 {betweenness}）",
                distance_score=distance,
                structure_score=0.0,
                serendipity_score=0.0,
            )
        )
    return entries


def assemble_keyless_bridge_document(
    theme: ThemeInput,
    cands: Sequence[Work],
    bridges: Set[str],
    *,
    profile: Optional[ThemeProfile] = None,
    count: int = 3,
    config: Optional[GenerationConfig] = None,
    section_title: str = "Track B: 引用ブリッジ候補（キー無し・構造整形）",
) -> OutputDocument:
    """Full key-free assembly: deterministic selection → structured 4-part fill → document.

    ``fill_track_entries(mode="structured")`` is fully deterministic (it never calls the
    LLM), so the entire document is produced without an API key.
    """
    entries = build_bridge_entries(cands, bridges, profile=profile, count=count)
    filled = fill_track_entries(entries, config or GenerationConfig(), theme=theme, mode="structured")
    section = OutputSection(title=section_title, track="B", entries=filled)
    return OutputDocument(theme=theme, sections=[section])


# --- Stage (c): accept agent scoring and finalize through the post-gate -----
#
# Contract for one delegated candidate (the agent returns a list of these). The
# metadata fields are the material contra handed out (so the Work can be rebuilt
# without re-collecting); the scoring fields are the agent's own judgement, which
# the deterministic post-gate then re-checks against the hard floors.
#
#   {
#     # --- candidate material (echoed back from contra) ---
#     "id": str,                       # required (OpenAlex/work id; the join key)
#     "title": str, "abstract": str|null,
#     "year": int, "venue": str, "doi": str|null, "cited_by_count": int,
#     "concepts": [str], "concept_tags": [{"name": str, "level": int, "score": float}],
#     "referenced_works": [str], "publication_type": str|null,
#     # --- agent scoring (the delegated LLM judgement) ---
#     "purpose_sim": float,            # required, 0..1
#     "mechanism_dist": float,         # required, 0..1
#     "structural_depth": float|null,  # optional hollow-judge verdict, 0..1
#     "has_causal_pm": bool|null,      # optional
#     "connection_label": str,         # optional (default below)
#     "serendipity_rationale": str,    # optional -> usefulness hypothesis
#     # --- optional agent prose (else deterministic structured fill) ---
#     "relationship": str, "summary": str, "caution": str,
#   }
AGENT_SCORE_REQUIRED = ("id", "purpose_sim", "mechanism_dist")


def _as_float(value: Any) -> float:
    return float(value)


def work_from_material(material: Dict[str, Any]) -> Work:
    """Rebuild a Work from the candidate material the agent echoes back."""
    tags = [
        Concept(name=str(t.get("name", "")), level=int(t.get("level", 0)), score=float(t.get("score", 0.0)))
        for t in (material.get("concept_tags") or [])
        if t.get("name")
    ]
    return Work(
        id=str(material["id"]),
        title=str(material.get("title", "")),
        year=int(material.get("year") or 0),
        venue=str(material.get("venue", "")),
        doi=material.get("doi"),
        cited_by_count=int(material.get("cited_by_count") or 0),
        abstract=material.get("abstract"),
        concepts=[str(c) for c in (material.get("concepts") or [])],
        concept_tags=tags,
        publication_type=material.get("publication_type"),
        referenced_works=[str(r) for r in (material.get("referenced_works") or [])],
    )


def material_from_work(work: Work) -> Dict[str, Any]:
    """Serialize a Work into the candidate-material dict the agent scores and echoes back.

    The inverse of :func:`work_from_material`: contra's key-free raw collection emits these so the
    calling agent can score them and pass the scored list to :func:`finalize_delegated_document`
    (the ``delegate_finalize`` MCP tool). Carries exactly the fields ``work_from_material`` reads,
    so a round-trip preserves the Work.
    """
    return {
        "id": work.id,
        "title": work.title,
        "abstract": work.abstract,
        "year": work.year,
        "venue": work.venue,
        "doi": work.doi,
        "cited_by_count": work.cited_by_count,
        "concepts": list(work.concepts or []),
        "concept_tags": [
            {"name": t.name, "level": t.level, "score": t.score}
            for t in (work.concept_tags or [])
        ],
        "referenced_works": list(work.referenced_works or []),
        "publication_type": work.publication_type,
    }


def score_row_from_material(material: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the post-gate score row from an agent-scored candidate."""
    row: Dict[str, Any] = {
        "purpose_sim": _as_float(material["purpose_sim"]),
        "mechanism_dist": _as_float(material["mechanism_dist"]),
        "connection_label": str(material.get("connection_label") or "構造的接続"),
        "serendipity_rationale": str(material.get("serendipity_rationale") or ""),
    }
    if material.get("structural_depth") is not None:
        row["structural_depth"] = _as_float(material["structural_depth"])
    if material.get("has_causal_pm") is not None:
        row["has_causal_pm"] = bool(material["has_causal_pm"])
    return row


def normalize_agent_scores(
    materials: Sequence[Dict[str, Any]],
) -> "tuple[Dict[str, Work], Dict[str, dict], Dict[str, Dict[str, Any]]]":
    """Validate + split agent-scored candidates into (works, score rows, raw-by-id).

    Raises ValueError if a candidate is missing a required field.
    """
    works: Dict[str, Work] = {}
    scores: Dict[str, dict] = {}
    by_id: Dict[str, Dict[str, Any]] = {}
    for i, material in enumerate(materials):
        for key in AGENT_SCORE_REQUIRED:
            if material.get(key) is None:
                raise ValueError(f"delegated candidate #{i} missing required field '{key}'")
        wid = str(material["id"])
        works[wid] = work_from_material(material)
        scores[wid] = score_row_from_material(material)
        by_id[wid] = material
    return works, scores, by_id


def finalize_delegated_document(
    materials: Sequence[Dict[str, Any]],
    theme: ThemeInput,
    *,
    theme_profile: Optional[ThemeProfile] = None,
    count: int = 1,
    config: Optional[GenerationConfig] = None,
    emit_fallback: bool = True,
    section_title: str = "Track B: 接続点フィーチャー（委譲採点 → post-gate）",
    diag: Optional[dict] = None,
    **gate_kwargs: Any,
) -> OutputDocument:
    """Stage (c): run agent-scored candidates through the deterministic post-gate.

    The agent supplies purpose_sim / mechanism_dist / (optional) structural_depth etc.;
    ``apply_post_gates`` re-applies the hard floors (anomaly / near-cap / serendipity /
    hollow / percentile / output-floor / fallback / M3) with NO LLM. Any agent-supplied
    4-part prose is honored; missing parts fall back to the deterministic structured fill.
    """
    works, scores, by_id = normalize_agent_scores(materials)
    entries = apply_post_gates(
        scores, works,
        theme_profile=theme_profile, count=count, emit_fallback=emit_fallback,
        diag=diag, **gate_kwargs,
    )
    # Seed any agent-supplied prose, then deterministically fill the rest (no LLM).
    seeded: List[OutputEntry] = []
    for entry in entries:
        material = by_id.get(entry.work.id, {})
        seeded.append(dc_replace(
            entry,
            relationship=str(material.get("relationship") or "") or entry.relationship,
            abstract_summary=str(material.get("summary") or "") or entry.abstract_summary,
            caution=str(material.get("caution") or "") or entry.caution,
        ))
    filled = fill_track_entries(seeded, config or GenerationConfig(), theme=theme, mode="structured")
    section = OutputSection(title=section_title, track="B", entries=filled)
    return OutputDocument(theme=theme, sections=[section])


# --- Stage (d): key-free Track A (byrepo) assembly --------------------------
#
# Track A delegation is simpler than Track B: byrepo's selection is the 4-Pillar
# Reliability Score, computed deterministically in code (no LLM). There is no
# agent-supplied number for contra to re-gate -- the only LLM step is the 4-part
# prose. So the key-free path collects + scores (deterministic) and fills the
# prose with the structured mode; the agent refines the prose afterward in its
# own context. (Track B, by contrast, needs delegate_finalize because the agent
# supplies purpose_sim/mechanism_dist that the post-gate must re-check.)

_TRACK_A_LABEL = "実装アンカー"


def _reliability_level(score: int) -> str:
    if score >= 70:
        return "高"
    if score >= 40:
        return "中"
    return "低"


def build_track_a_entries(works: Sequence[Work], *, count: int = 3) -> List[OutputEntry]:
    """Deterministic Track A entries ranked by the 4-Pillar Reliability Score (no LLM)."""
    chosen = sorted(
        works, key=lambda w: w.source_meta.get("reliability_score", 0), reverse=True
    )[: max(count, 0)]
    return [
        OutputEntry(
            work=work,
            relationship="",
            abstract_summary="",
            caution="",
            track="A",
            label=_TRACK_A_LABEL,
            relationship_level=_reliability_level(work.source_meta.get("reliability_score", 0)),
        )
        for work in chosen
    ]


def assemble_keyless_track_a_document(
    theme: ThemeInput,
    works: Sequence[Work],
    *,
    count: int = 3,
    config: Optional[GenerationConfig] = None,
    section_title: str = "Track A: Practical Anchors（キー無し・構造整形）",
) -> OutputDocument:
    """Full key-free Track A assembly: deterministic reliability ranking → structured fill."""
    entries = build_track_a_entries(works, count=count)
    filled = fill_track_entries(entries, config or GenerationConfig(), theme=theme, mode="structured")
    section = OutputSection(title=section_title, track="A", entries=filled)
    return OutputDocument(theme=theme, sections=[section])


__all__ = [
    "select_bridge_candidates_raw",
    "build_bridge_entries",
    "assemble_keyless_bridge_document",
    "AGENT_SCORE_REQUIRED",
    "work_from_material",
    "material_from_work",
    "score_row_from_material",
    "normalize_agent_scores",
    "finalize_delegated_document",
    "build_track_a_entries",
    "assemble_keyless_track_a_document",
]
