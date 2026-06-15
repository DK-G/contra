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

from typing import List, Optional, Sequence, Set

from src.core.models import OutputDocument, OutputEntry, OutputSection, ThemeInput, Work
from src.pipeline.concept_distance import ThemeProfile, near_domain_signal
from src.pipeline.generate import GenerationConfig, fill_track_entries


def _shared_bridge_count(work: Work, bridges: Set[str]) -> int:
    """How many of the work's references sit in the shared citation-bridge pool."""
    return sum(1 for ref in (work.referenced_works or []) if ref in bridges)


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
    pool.sort(key=lambda w: _shared_bridge_count(w, bridges), reverse=True)
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
        shared = _shared_bridge_count(work, bridges)
        distance = round(1.0 - _l01_jaccard(work, profile), 2)
        entries.append(
            OutputEntry(
                work=work,
                relationship="",
                abstract_summary="",
                caution="",
                track="B",
                label=f"引用ブリッジ（共有 {shared} 本）",
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


__all__ = [
    "select_bridge_candidates_raw",
    "build_bridge_entries",
    "assemble_keyless_bridge_document",
]
