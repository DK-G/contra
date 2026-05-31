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


def filter_by_used_ids(
    works: List[Work],
    used_ids: Set[str],
    used_titles: Optional[Set[str]] = None,
    used_dois: Optional[Set[str]] = None,
) -> List[Work]:
    """Drop works already surfaced in a prior run, matching on id OR norm_title OR DOI."""
    titles = used_titles or set()
    dois = used_dois or set()
    out: List[Work] = []
    for w in works:
        if w.id in used_ids:
            continue
        nt = _norm_title(w.title)
        if nt and nt in titles:
            continue
        nd = _norm_doi(w.doi)
        if nd and nd in dois:
            continue
        out.append(w)
    return out


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


def _norm_doi(doi: Optional[str]) -> str:
    """Normalise a DOI for cross-run dedup: lowercase, strip the resolver URL prefix."""
    if not doi:
        return ""
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if d.startswith(prefix):
            return d[len(prefix):]
    return d


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


def _strip_openalex_id(raw: Optional[str]) -> str:
    """Reduce a full OpenAlex id URL to its bare id ('https://openalex.org/C1' -> 'C1')."""
    if not raw:
        return ""
    return str(raw).rsplit("/", 1)[-1]


def _bridge_pool_from_seeds(seeds: List[Work], cap: int = 50) -> List[str]:
    """Pick up to `cap` bridge works (the referenced_works of the near-field seeds).

    Bridges are the shared references through which a 2-hop citation scan crosses field
    boundaries. References cited by MULTIPLE seeds rank first (a stronger bridge); the
    remaining refs are then taken round-robin across seeds so every seed contributes
    bridges (diversity), instead of one reference-heavy seed dominating the pool.
    """
    counts: dict = {}
    per_seed: List[List[str]] = []
    first_seen: List[str] = []
    fs_set: Set[str] = set()
    for seed in seeds:
        refs: List[str] = []
        for r in (seed.referenced_works or []):
            if r and r not in refs:  # dedupe within a single seed, keep order
                refs.append(r)
        per_seed.append(refs)
        for r in refs:
            counts[r] = counts.get(r, 0) + 1
            if r not in fs_set:
                fs_set.add(r)
                first_seen.append(r)

    selected: List[str] = []
    seen: Set[str] = set()
    # 1) shared refs first (cited by >=2 seeds), most-shared first, ties by first-seen order
    for r in sorted((x for x in first_seen if counts[x] >= 2), key=lambda x: -counts[x]):
        if len(selected) >= cap:
            break
        if r not in seen:
            seen.add(r)
            selected.append(r)
    # 2) remaining refs round-robin across seeds
    idxs = [0] * len(per_seed)
    while len(selected) < cap:
        progressed = False
        for i, refs in enumerate(per_seed):
            while idxs[i] < len(refs):
                r = refs[idxs[i]]
                idxs[i] += 1
                if r not in seen:
                    seen.add(r)
                    selected.append(r)
                    progressed = True
                    break
            if len(selected) >= cap:
                break
        if not progressed:
            break
    return selected


def _seed_l0_concept_ids(seeds: List[Work]) -> List[str]:
    """Bare L0 (root-domain) concept ids of the seeds, deduped — the home domain to exclude."""
    out: List[str] = []
    seen: Set[str] = set()
    for seed in seeds:
        for tag in seed.concept_tags:
            if tag.level == 0:
                cid = _strip_openalex_id(tag.id)
                if cid and cid not in seen:
                    seen.add(cid)
                    out.append(cid)
    return out


def collect_citation_candidates(
    seeds: List[Work],
    config: Optional[CollectConfig] = None,
    *,
    max_count: int = 60,
    used_ids: Optional[Set[str]] = None,
    bridge_cap: int = 50,
    max_refs: int = 100,
) -> List[Work]:
    """Citation 2-hop scan: papers citing the seeds' references but OUTSIDE the seeds' domain.

    seed --cites--> bridge (shared reference) <--cites-- candidate. Candidates that cite the
    same foundational works as the near-field seeds, yet carry none of the seeds' L0 root
    concepts, are structurally linked yet cross-domain — exactly what surface keyword search
    misses. `type:article` and `referenced_works_count:<max_refs` drop reviews / intro-citation
    dumps (the false-bridge traps). Seeds and `used_ids` are never returned.
    """
    cfg = config or CollectConfig()
    bridges = _bridge_pool_from_seeds(seeds, cap=bridge_cap)
    if not bridges:
        return []

    exclude: Set[str] = {s.id for s in seeds} | set(used_ids or set())
    filter_parts = ["cites:" + "|".join(bridges)]
    for cid in _seed_l0_concept_ids(seeds):
        filter_parts.append(f"concepts.id:!{cid}")
    filter_parts.append("type:article")
    filter_parts.append(f"referenced_works_count:<{max_refs}")
    filter_str = ",".join(filter_parts)

    collector = Collector(cfg)
    out: List[Work] = []
    seen: Set[str] = set()
    for page in range(1, cfg.max_pages + 1):
        payload = collector.client.get(
            {"filter": filter_str, "per-page": cfg.per_page, "page": page}
        )
        new = 0
        for w in filter_retracted(normalize_results(payload)):
            if w.id in exclude or w.id in seen:
                continue
            seen.add(w.id)
            out.append(w)
            new += 1
            if len(out) >= max_count:
                return out
        if new == 0:
            break
    return out


def collect_track_b(
    theme: ThemeInput,
    config: Optional[CollectConfig] = None,
    model: str = "gpt-4o-mini",
    *,
    max_count: int = 60,
    used_ids: Optional[Set[str]] = None,
    used_titles: Optional[Set[str]] = None,
    used_dois: Optional[Set[str]] = None,
) -> List[Work]:
    """Collect Track B candidates from multiple distinct domains using LLM-generated queries.

    Excludes papers already surfaced in a prior run on id / norm_title / DOI (the title and
    DOI sets, seeded from history, catch the same paper recurring under a different OpenAlex id).
    """
    cfg = config or CollectConfig()
    queries = generate_track_b_queries(theme, model)
    collector = Collector(cfg)
    works: List[Work] = []
    seen_ids: Set[str] = set(used_ids or set())
    seen_titles: Set[str] = set(used_titles or set())
    seen_dois: Set[str] = set(used_dois or set())
    per_query = max(max_count // len(queries), 5)
    for query in queries:
        count = 0
        for page in range(1, cfg.max_pages + 1):
            payload = collector.client.get(
                {"search": query, "per-page": cfg.per_page, "page": page}
            )
            for w in filter_retracted(normalize_results(payload)):
                norm_title = _norm_title(w.title)
                norm_doi = _norm_doi(w.doi)
                if (w.id not in seen_ids and w.abstract
                        and not (norm_title and norm_title in seen_titles)
                        and not (norm_doi and norm_doi in seen_dois)):
                    seen_ids.add(w.id)
                    if norm_title:
                        seen_titles.add(norm_title)
                    if norm_doi:
                        seen_dois.add(norm_doi)
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
    "collect_citation_candidates",
    "filter_by_used_ids",
    "generate_track_b_query",
    "generate_track_b_queries",
    "generate_assumption_queries",
]
