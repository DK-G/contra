"""Core data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Scope:
    field: str
    scale: str
    time_range: str


@dataclass
class Keywords:
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


@dataclass
class ThemeInput:
    theme_overview: str
    goal: str
    why_problem: str
    approach_type: str
    assumptions: List[str]
    scope: Scope
    keywords: Keywords = field(default_factory=Keywords)
    concern: Optional[str] = None


@dataclass
class Concept:
    """An OpenAlex concept tag with hierarchy level (0=root) and relevance score.

    `id` is the OpenAlex concept id (full URL or bare 'C...'); the citation 2-hop
    collector uses the seeds' L0 ids to exclude their home domain via the API filter.
    """
    name: str
    level: int
    score: float
    id: str = ""


@dataclass
class Work:
    id: str
    title: str
    year: int
    venue: str
    doi: Optional[str]
    cited_by_count: int
    abstract: Optional[str]
    concepts: List[str] = field(default_factory=list)
    # Structured concept tags (level/score) for objective domain-distance scoring.
    # Non-breaking: `concepts` (display names) is retained for existing callers.
    concept_tags: List[Concept] = field(default_factory=list)
    author_affiliations: List[str] = field(default_factory=list)
    publication_type: Optional[str] = None
    is_retracted: bool = False
    # OpenAlex ids of works this paper cites; seeds the citation 2-hop bridge pool.
    referenced_works: List[str] = field(default_factory=list)


@dataclass
class OutputEntry:
    work: Work
    relationship: str
    abstract_summary: str
    caution: str
    track: str = "A"
    label: str = ""
    relationship_level: str = ""
    # Track B serendipity selection scores (0.0-1.0). See plan.md §6.2.
    distance_score: float = 0.0
    structure_score: float = 0.0
    serendipity_score: float = 0.0
    # The 4-part "役に立つ可能性の仮説" (usefulness hypothesis). See plan.md §7.
    usefulness_hypothesis: str = ""


@dataclass
class OutputSection:
    title: str
    track: str = ""
    entries: List[OutputEntry] = field(default_factory=list)


@dataclass
class OutputDocument:
    theme: ThemeInput
    sections: List[OutputSection] = field(default_factory=list)
    query: Optional[str] = None
    collected_count: Optional[int] = None
    filter_policy: Optional[str] = None
    collected_at: Optional[str] = None


@dataclass
class ThemeHistory:
    theme_hash: str
    used_ids: List[str]
    generated_at: str
    # Cross-run near-duplicate guard: a paper can recur under a DIFFERENT OpenAlex id
    # (preprint vs published), so we also remember normalized titles and DOIs of adopted
    # papers and exclude on any of id / norm_title / doi (non-breaking; default empty).
    used_titles: List[str] = field(default_factory=list)
    used_dois: List[str] = field(default_factory=list)
