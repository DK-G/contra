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
    """The theme's core concept, used only by the LLM-failure fallback queries."""
    if theme.keywords.include:
        return theme.keywords.include[0]
    if theme.goal:
        return theme.goal
    return theme.scope.field


def _clean_query(q: str) -> str:
    """Strip quotes and the literal cross-product token ('x'/'X'/'×') the LLM may emit.

    The LLM sometimes verbalises 'combine (a) with (b)' as 'a x b'; that literal 'x'
    leaks into the OpenAlex search and skews results, so remove it (Step 9 Phase 2, B-1a).
    """
    q = q.strip().strip('"').strip("'")
    for sep in (" x ", " X ", " × "):
        q = q.replace(sep, " ")
    q = q.replace("×", " ")
    return " ".join(q.split())


def _norm_title(title: Optional[str]) -> str:
    """Normalise a title for near-duplicate detection: lowercase, take text before ':'.

    Catches conference/journal variants like 'COEVOLVE' vs 'COEVOLVE: a joint point
    process model ...' that carry different OpenAlex IDs (Step 9 Phase 2, B-2).
    """
    t = (title or "").lower().split(":")[0]
    return " ".join(t.split())


def generate_track_b_queries(theme: ThemeInput, model: str = "gpt-4o-mini", n: int = _TRACK_B_DOMAIN_COUNT) -> List[str]:
    """Generate N Track B queries that target a STRUCTURAL analog, not the theme's topic.

    The earlier design crossed each distant domain with the theme's surface keyword
    (e.g. 'information diffusion'). But that keyword is the theme's OWN central
    phenomenon, so OpenAlex full-text search dragged results back into the home domain
    (or into generic papers sharing the polysemous word). Instead we ask the model to
    first infer the theme's ABSTRACT RELATIONAL STRUCTURE (a bifurcation/threshold/
    feedback/rate-limiting dynamic) and cross each distant domain with THAT structural
    aspect — never with the theme's surface topic words (Step 9 Phase 2, B-1b).
    Queries are plain keyword strings; any literal 'x'/'×' cross token is stripped.
    """
    from src.openai_client import OpenAIError, extract_output_text, responses_create

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    f"You generate {n} OpenAlex academic search queries for finding papers in a "
                    "DISTANT domain that share a transferable RELATIONAL STRUCTURE with a research "
                    "theme (a feedback loop, a branching/bifurcation condition, a threshold/contagion "
                    "dynamic, a rate-limiting-under-constraints mechanism) — NOT surface keywords.\n"
                    "STEP 1 (internal): infer the theme's ABSTRACT relational structure — the shape "
                    "of its problem, stripped of its topic words.\n"
                    f"STEP 2: write {n} queries, each combining (a) a concept from a DISTINCT distant "
                    f"domain with (b) a term naming that abstract structural aspect. Use {n} DIFFERENT "
                    "distant domains.\n"
                    "HARD CONSTRAINTS:\n"
                    "- NEVER put the theme's own field or surface keywords (given below) in any query.\n"
                    "- Do NOT target the theme's own phenomenon or population — that is too near.\n"
                    "- Each query is 3-5 plain keywords. Do NOT write a literal 'x', 'X', or '×' "
                    "between terms — just separate keywords with spaces.\n"
                    f"Return exactly {n} lines, one query per line, no numbering or extra text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research theme: {theme.theme_overview[:300]}\n"
                    f"Theme's goal: {theme.goal}\n"
                    f"Theme's own field (too near, avoid): {theme.scope.field}\n"
                    f"Theme's surface keywords (too near, NEVER put in a query): "
                    f"{', '.join(theme.keywords.include)}\n\n"
                    f"Infer the theme's abstract relational structure, then generate {n} queries "
                    "(distant domain concept + that structural aspect), each in a different distant "
                    "domain that does NOT study the theme's own phenomenon. Plain keywords only, "
                    "no 'x' token, do not repeat domains."
                ),
            },
        ],
        "temperature": 0.9,
    }
    try:
        response = responses_create(payload)
        text = extract_output_text(response).strip()
        queries = [_clean_query(q) for q in text.splitlines() if q.strip()]
        queries = [q for q in queries if q]
        if queries:
            return queries[:n]
    except OpenAIError:
        pass
    anchor = _theme_anchor(theme)
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
    seen_titles: Set[str] = set()
    per_query = max(max_count // len(queries), 5)
    for query in queries:
        count = 0
        for page in range(1, cfg.max_pages + 1):
            payload = collector.client.get(
                {"search": query, "per-page": cfg.per_page, "page": page}
            )
            for w in filter_retracted(normalize_results(payload)):
                norm_title = _norm_title(w.title)
                if w.id not in seen_ids and norm_title not in seen_titles and w.abstract:
                    seen_ids.add(w.id)
                    if norm_title:
                        seen_titles.add(norm_title)
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
