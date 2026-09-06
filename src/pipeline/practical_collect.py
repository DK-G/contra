"""Unified Track A practical-anchor collection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from src.core.models import ThemeInput, Work
from src.pipeline.artifact_collect import ArtifactCollectConfig, collect_track_a_artifact_works
from src.pipeline.git_collect import GitCollectConfig, collect_track_a_git_works
from src.pipeline.problem_search import ProblemSearchPlan, build_problem_search_plan


@dataclass
class PracticalCollectConfig:
    git: GitCollectConfig
    artifacts: ArtifactCollectConfig
    max_items: int = 10


def _norm_title(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").casefold()).strip()


def _norm_doi(doi: Optional[str]) -> str:
    if not doi:
        return ""
    text = doi.strip().lower()
    text = text.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    return text


def _track_a_kind_priority(work: Work) -> int:
    if (work.publication_type or "").endswith("_repository"):
        return 1
    if work.source_meta.get("artifact_kind_label") == "paper_only":
        return 0
    return 1


def collect_track_a_practical_works(
    theme: ThemeInput,
    config: PracticalCollectConfig,
) -> List[Work]:
    shared_plan: Optional[ProblemSearchPlan] = None
    if (
        config.git.use_problem_search
        and config.artifacts.use_problem_search
        and config.git.use_llm_problem_plan == config.artifacts.use_llm_problem_plan
        and config.git.llm_problem_plan_model == config.artifacts.llm_problem_plan_model
    ):
        shared_plan = build_problem_search_plan(
            theme,
            use_llm=config.git.use_llm_problem_plan,
            model=config.git.llm_problem_plan_model,
        )

    works: List[Work] = []
    works.extend(collect_track_a_git_works(theme, config.git, problem_plan=shared_plan))
    works.extend(collect_track_a_artifact_works(theme, config.artifacts, problem_plan=shared_plan))

    deduped: List[Work] = []
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    seen_dois: set[str] = set()
    for work in sorted(
        works,
        key=lambda w: (
            _track_a_kind_priority(w),
            w.source_meta.get("field_problem_score", 0),
            w.source_meta.get("problem_match_score", 0),
            w.source_meta.get("artifact_kind_score", 0),
            w.source_meta.get("problem_solution_fit_score", 0),
            w.source_meta.get("reliability_score", 0),
        ),
        reverse=True,
    ):
        work_id = (work.id or "").strip().lower()
        title = _norm_title(work.title)
        doi = _norm_doi(work.doi)
        if (work_id and work_id in seen_ids) or (title and title in seen_titles) or (doi and doi in seen_dois):
            continue
        if work_id:
            seen_ids.add(work_id)
        if title:
            seen_titles.add(title)
        if doi:
            seen_dois.add(doi)
        deduped.append(work)
        if len(deduped) >= config.max_items:
            break
    return deduped
