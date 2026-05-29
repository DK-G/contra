"""Collection pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set

from src.core.models import ThemeInput, Work
from src.openalex.client import OpenAlexClient, OpenAlexConfig
from src.openalex.parser import normalize_results
from src.pipeline.filter import filter_has_abstract, limit_count


@dataclass
class CollectConfig:
    per_page: int = 50
    max_pages: int = 5
    mailto: Optional[str] = None
    relax_search: bool = True


class Collector:
    def __init__(self, config: Optional[CollectConfig] = None) -> None:
        self.config = config or CollectConfig()
        self.client = OpenAlexClient(OpenAlexConfig(mailto=self.config.mailto))

    def _query_from_theme(self, theme: ThemeInput) -> str:
        # Minimal query builder: use include keywords if present; otherwise fallback.
        tokens: List[str] = []
        tokens.extend(theme.keywords.include)
        if not tokens:
            if theme.scope.field:
                tokens.append(theme.scope.field)
            if theme.goal:
                tokens.append(theme.goal)
        return " ".join(t for t in tokens if t)

    def _query_variants(self, theme: ThemeInput) -> List[str]:
        tokens = [t for t in theme.keywords.include if t]
        variants: List[str] = []
        if tokens:
            for k in range(len(tokens), 0, -1):
                variants.append(" ".join(tokens[:k]))
        fallback: List[str] = []
        if theme.scope.field:
            fallback.append(theme.scope.field)
        if theme.goal:
            fallback.append(theme.goal)
        if fallback:
            variants.append(" ".join(fallback))
        seen = set()
        ordered: List[str] = []
        for q in variants:
            if q and q not in seen:
                seen.add(q)
                ordered.append(q)
        return ordered

    def collect(self, theme: ThemeInput) -> List[Work]:
        query = self._query_from_theme(theme)
        works: List[Work] = []
        for page in range(1, self.config.max_pages + 1):
            payload = self.client.get(
                {"search": query, "per-page": self.config.per_page, "page": page}
            )
            works.extend(normalize_results(payload))
            if len(works) >= self.config.per_page * page:
                continue
        return works


def collect_candidates(theme: ThemeInput, config: Optional[CollectConfig] = None) -> List[Work]:
    collector = Collector(config)
    return collector.collect(theme)


def collect_and_filter(
    theme: ThemeInput,
    config: Optional[CollectConfig] = None,
    *,
    max_count: int = 500,
    require_abstract: bool = True,
) -> List[Work]:
    cfg = config or CollectConfig()
    collector = Collector(cfg)
    collected: List[Work] = []
    seen_ids = set()
    queries = (
        collector._query_variants(theme) if cfg.relax_search else [collector._query_from_theme(theme)]
    )
    for query in queries:
        works: List[Work] = []
        for page in range(1, cfg.max_pages + 1):
            payload = collector.client.get(
                {"search": query, "per-page": cfg.per_page, "page": page}
            )
            works.extend(normalize_results(payload))
        if require_abstract:
            works = filter_has_abstract(works)
        for w in works:
            if w.id in seen_ids:
                continue
            seen_ids.add(w.id)
            collected.append(w)
            if len(collected) >= max_count:
                return collected
    return limit_count(collected, max_count)


def filter_by_used_ids(works: List[Work], used_ids: Set[str]) -> List[Work]:
    return [w for w in works if w.id not in used_ids]


def generate_track_b_query(theme: ThemeInput, model: str = "gpt-4o-mini") -> str:
    """Generate a cross-domain OpenAlex query for Track B via LLM."""
    from src.openai_client import OpenAIError, extract_output_text, responses_create

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You generate a concise OpenAlex academic search query for a domain DIFFERENT from "
                    "the given research theme. The goal is to find papers that might have one surprising "
                    "methodological or conceptual connection. Return only the query string, 3-5 keywords."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research theme: {theme.theme_overview[:300]}\n"
                    f"Domain: {theme.scope.field}\n"
                    f"Keywords: {', '.join(theme.keywords.include)}\n\n"
                    "Generate a search query for a different academic domain with a potential single surprising connection."
                ),
            },
        ],
        "temperature": 0.7,
    }
    try:
        response = responses_create(payload)
        query = extract_output_text(response).strip().strip('"').strip("'")
        if query:
            return query
    except OpenAIError:
        pass
    fallback = theme.keywords.include[0] if theme.keywords.include else theme.scope.field
    return f"{fallback} algorithm optimization"


def collect_track_b(
    theme: ThemeInput,
    config: Optional[CollectConfig] = None,
    model: str = "gpt-4o-mini",
    *,
    max_count: int = 60,
    used_ids: Optional[Set[str]] = None,
) -> List[Work]:
    """Collect Track B candidates from a different domain using an LLM-generated query."""
    cfg = config or CollectConfig()
    query = generate_track_b_query(theme, model)
    collector = Collector(cfg)
    works: List[Work] = []
    seen_ids: Set[str] = set(used_ids or set())
    for page in range(1, cfg.max_pages + 1):
        payload = collector.client.get(
            {"search": query, "per-page": cfg.per_page, "page": page}
        )
        for w in normalize_results(payload):
            if w.id not in seen_ids and w.abstract:
                seen_ids.add(w.id)
                works.append(w)
        if len(works) >= max_count:
            break
    return works[:max_count]


__all__ = [
    "Collector",
    "CollectConfig",
    "collect_candidates",
    "collect_and_filter",
    "collect_track_b",
    "filter_by_used_ids",
    "generate_track_b_query",
]
