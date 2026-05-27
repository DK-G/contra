"""Core data models for Phase 1."""

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
class Work:
    id: str
    title: str
    year: int
    venue: str
    doi: Optional[str]
    cited_by_count: int
    abstract: Optional[str]
    concepts: List[str] = field(default_factory=list)
    author_affiliations: List[str] = field(default_factory=list)
    publication_type: Optional[str] = None


@dataclass
class OutputEntry:
    work: Work
    relationship: str
    abstract_summary: str
    caution: str


@dataclass
class OutputSection:
    title: str
    entries: List[OutputEntry] = field(default_factory=list)


@dataclass
class OutputDocument:
    theme: ThemeInput
    sections: List[OutputSection] = field(default_factory=list)
    query: Optional[str] = None
    collected_count: Optional[int] = None
    filter_policy: Optional[str] = None
    collected_at: Optional[str] = None
