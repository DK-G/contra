"""Collection pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set

from src.core.models import ThemeInput, Work
from src.openalex.client import OpenAlexClient, OpenAlexConfig
from src.openalex.parser import normalize_results
from src.pipeline.filter import filter_retracted, filter_has_abstract, limit_count


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
    use_assumption_queries: bool = True,
) -> List[Work]:
    cfg = config or CollectConfig()
    collector = Collector(cfg)
    collected: List[Work] = []
    seen_ids: Set[str] = set()

    base_queries = (
        collector._query_variants(theme) if cfg.relax_search else [collector._query_from_theme(theme)]
    )
    assumption_queries = generate_assumption_queries(theme) if use_assumption_queries else []
    all_queries = base_queries + [q for q in assumption_queries if q not in base_queries]

    for query in all_queries:
        works: List[Work] = []
        for page in range(1, cfg.max_pages + 1):
            payload = collector.client.get(
                {"search": query, "per-page": cfg.per_page, "page": page}
            )
            works.extend(normalize_results(payload))
        works = filter_retracted(works)
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


_TRACK_B_DOMAIN_COUNT = 5


def _theme_anchor(theme: ThemeInput) -> str:
    """The theme's core concept used to keep Track B queries 'distant but touchable'."""
    if theme.keywords.include:
        return theme.keywords.include[0]
    if theme.goal:
        return theme.goal
    return theme.scope.field


def generate_track_b_queries(theme: ThemeInput, model: str = "gpt-4o-mini", n: int = _TRACK_B_DOMAIN_COUNT) -> List[str]:
    """Generate N Track B queries, each = (distant domain concept) x (theme anchor term).

    Pure distant-domain search returns generic top-cited reviews (the 'too far' failure
    from the Goldilocks principle). Crossing each distant domain with a theme anchor term
    keeps results in the moderate-distance band: distant in field, but structurally touchable.
    """
    from src.openai_client import OpenAIError, extract_output_text, responses_create

    anchor = _theme_anchor(theme)
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    f"You generate {n} OpenAlex academic search queries for finding papers that are in a "
                    "DISTANT domain from the research theme but share a transferable RELATIONAL STRUCTURE "
                    "(e.g. a feedback loop, a recovery-from-failure mechanism, a difficulty-progression curve) "
                    "rather than surface keywords. "
                    f"Each query MUST combine (a) a concept term from a distinct distant domain with "
                    f"(b) an anchoring term tied to the theme's core (e.g. '{anchor}'), so results stay "
                    "structurally connectable instead of generic. "
                    f"Use {n} DIFFERENT distant domains. "
                    "AVOID domains that are merely ADJACENT to the theme: any field that studies the SAME "
                    "phenomenon, problem, or population the theme names (even in a different application "
                    "context) is too near and yields obvious connections — do not use it. A genuinely "
                    "distant domain shares only an abstract relational structure, not the theme's topic. "
                    "Also avoid the theme's own field and keywords (given below). "
                    "Each query is 3-5 keywords. "
                    f"Return exactly {n} lines, one query per line, no numbering or extra text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research theme: {theme.theme_overview[:300]}\n"
                    f"Theme's own field (too near, avoid): {theme.scope.field}\n"
                    f"Theme's keywords / phenomenon (too near, avoid as domains): {', '.join(theme.keywords.include)}\n"
                    f"Theme anchor term (use as the (b) cross term): {anchor}\n\n"
                    f"Generate {n} cross-product queries (distant domain concept x theme anchor), "
                    "each targeting a different distant domain that shares a relational structure with the theme "
                    "but does NOT study the theme's own phenomenon. Do not repeat domains."
                ),
            },
        ],
        "temperature": 0.9,
    }
    try:
        response = responses_create(payload)
        text = extract_output_text(response).strip()
        queries = [q.strip().strip('"').strip("'") for q in text.splitlines() if q.strip()]
        queries = [q for q in queries if q]
        if queries:
            return queries[:n]
    except OpenAIError:
        pass
    return [
        f"{anchor} feedback loop",
        f"{anchor} habit formation",
        f"{anchor} recovery from failure",
        f"{anchor} foraging behavior",
        f"{anchor} skill acquisition curve",
    ]


def generate_track_b_query(theme: ThemeInput, model: str = "gpt-4o-mini") -> str:
    """Generate a single cross-domain query (kept for backward compatibility)."""
    queries = generate_track_b_queries(theme, model, n=1)
    return queries[0] if queries else (theme.keywords.include[0] if theme.keywords.include else theme.scope.field)


def generate_assumption_queries(theme: ThemeInput, model: str = "gpt-4o-mini") -> List[str]:
    """Generate one OpenAlex search query per assumption in the theme input."""
    from src.openai_client import OpenAIError, extract_output_text, responses_create

    if not theme.assumptions:
        return []

    assumptions_text = "\n".join(f"- {a}" for a in theme.assumptions)
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You convert research assumptions into concise OpenAlex academic search queries. "
                    "Return exactly one query per assumption, one per line, 3-6 keywords each. "
                    "No numbering, no extra text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research theme: {theme.theme_overview[:200]}\n"
                    f"Domain: {theme.scope.field}\n\n"
                    f"Assumptions:\n{assumptions_text}\n\n"
                    "Convert each assumption into a focused OpenAlex search query."
                ),
            },
        ],
        "temperature": 0.3,
    }
    try:
        response = responses_create(payload)
        text = extract_output_text(response).strip()
        queries = [q.strip().strip('"').strip("'") for q in text.splitlines() if q.strip()]
        return [q for q in queries if q][: len(theme.assumptions)]
    except OpenAIError:
        return []


def collect_track_b(
    theme: ThemeInput,
    config: Optional[CollectConfig] = None,
    model: str = "gpt-4o-mini",
    *,
    max_count: int = 60,
    used_ids: Optional[Set[str]] = None,
) -> List[Work]:
    """Collect Track B candidates from multiple distinct domains using LLM-generated queries."""
    cfg = config or CollectConfig()
    queries = generate_track_b_queries(theme, model)
    collector = Collector(cfg)
    works: List[Work] = []
    seen_ids: Set[str] = set(used_ids or set())
    per_query = max(max_count // len(queries), 5)
    for query in queries:
        count = 0
        for page in range(1, cfg.max_pages + 1):
            payload = collector.client.get(
                {"search": query, "per-page": cfg.per_page, "page": page}
            )
            for w in filter_retracted(normalize_results(payload)):
                if w.id not in seen_ids and w.abstract:
                    seen_ids.add(w.id)
                    works.append(w)
                    count += 1
            if count >= per_query:
                break
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
    "generate_track_b_queries",
    "generate_assumption_queries",
]
