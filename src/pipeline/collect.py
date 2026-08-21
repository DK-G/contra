"""Collection pipeline."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set

from src.core.models import ThemeInput, Work
from src.openalex.client import OpenAlexClient, OpenAlexConfig, OpenAlexError
from src.openalex.parser import normalize_results
from src.pipeline.filter import filter_retracted, filter_has_abstract, limit_count
from src.pipeline.bridges import annotate_bridge_signals
from src.pipeline.query import (
    ROUTE_FILTER,
    ROUTE_SEARCH,
    StructuredQuery,
    dominant_field_ids,
    resolve_field_ids,
    structured_query_from_theme,
    structured_query_variants,
)
from src.pipeline.serendipity_query import (
    SerendipitySpec,
    build_semantic_query,
    exclude_home_field,
    generate_serendipity_facets,
    validate_semantic_results,
)


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

    def collect(self, theme: ThemeInput) -> List[Work]:
        sq = structured_query_from_theme(theme)
        return _collect_with_fallback(
            self.client, sq, per_page=self.config.per_page, max_pages=self.config.max_pages
        )


def _page_through(client, sq: StructuredQuery, *, per_page: int, max_pages: int) -> List[Work]:
    """Page through one StructuredQuery, stopping at the first empty page."""
    works: List[Work] = []
    for page in range(1, max_pages + 1):
        payload = client.get(sq.to_params(per_page=per_page, page=page))
        page_works = normalize_results(payload)
        works.extend(page_works)
        if not page_works:
            break
    return works


def _collect_with_fallback(client, sq: StructuredQuery, *, per_page: int, max_pages: int) -> List[Work]:
    """Run a field-scoped query; if a ``filter`` route returns nothing, retry as generic search.

    This is the recall floor: a precise ``title_and_abstract.search`` can legitimately miss a
    thin theme, so an empty filter result transparently falls back to the legacy generic-search
    behaviour instead of returning zero candidates.
    """
    works = _page_through(client, sq, per_page=per_page, max_pages=max_pages)
    if not works and sq.route == ROUTE_FILTER:
        works = _page_through(client, sq.fallback(), per_page=per_page, max_pages=max_pages)
    return works


def collect_candidates(theme: ThemeInput, config: Optional[CollectConfig] = None) -> List[Work]:
    collector = Collector(config)
    return collector.collect(theme)


# --- Pseudo-relevance feedback (PRF) for near-field seed collection ---------
# PRF research selects feedback terms by dropping CORPUS-common terms (those in >10% of documents)
# then ranking the rest. contra has no corpus document-frequency index, so this static list of
# high-frequency, low-information English + academic-boilerplate words is the precision guard that
# keeps the mined expansion anchored to the topic's distinctive vocabulary instead of generic noise.
_PRF_STOPWORDS = frozenset("""
a an the of in on at to for from by with without within into over under between among and or not
but as is are was were be been being this that these those it its their our your we they he she his
her them us you which who whom whose what when where why how can could may might will would shall
should must do does did done has have had having than then so such both each any all some no nor
only own same other another more most much many few less least very too also however therefore thus
hence moreover furthermore using used use based via per across about above after before during while
study studies paper papers result results method methods methodology approach approaches model
models framework frameworks analysis analyses data dataset datasets propose proposed novel new
performance evaluation evaluate experiment experiments experimental research problem problems system
systems application applications technique techniques work works present presents introduce
introduced provide provides show shows shown demonstrate high low large small significant
significantly effect effects different various recent state art toward towards
""".split())

_PRF_TOKEN_RE = re.compile(r"[a-z][a-z\-]{2,}")   # >=3 alpha chars, internal hyphen ok, drop numbers
_PRF_MIN_SEEDS = 5     # need enough relevance-set docs for the seed-DF signal to be stable
_PRF_SEED_POOL = 20    # mine salient terms from at most this many top seeds
_PRF_TOP_K = 6         # expansion terms to add (kept small: reformulation, not blind expansion)


def _salient_terms(
    seeds: List[Work],
    existing_terms: Iterable[str],
    *,
    top_k: int = _PRF_TOP_K,
    min_seed_df: int = 2,
) -> List[str]:
    """Mine salient home-domain terms from the top seeds (Rocchio/RM3-style relevance feedback).

    Treats the top seeds as the relevance set: a term recurring across MANY seeds (high in-set
    document frequency) is salient to the topic. Ranks by seed-DF (then total frequency), dropping
    stopwords/boilerplate, terms already in the query, and singletons (seed_df < ``min_seed_df``),
    and returns the top ``top_k``. Pure/deterministic — no LLM, no network.
    """
    have: Set[str] = set()
    for t in existing_terms:
        have.update(_PRF_TOKEN_RE.findall((t or "").lower()))
    seed_df: Counter = Counter()
    total_tf: Counter = Counter()
    for w in seeds:
        toks = _PRF_TOKEN_RE.findall(f"{w.title or ''} {w.abstract or ''}".lower())
        for tok in toks:
            total_tf[tok] += 1
        for tok in set(toks):
            seed_df[tok] += 1
    ranked = [
        (df, total_tf[tok], tok)
        for tok, df in seed_df.items()
        if df >= min_seed_df and tok not in _PRF_STOPWORDS and tok not in have
    ]
    ranked.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return [tok for _, _, tok in ranked[:top_k]]


def collect_and_filter(
    theme: ThemeInput,
    config: Optional[CollectConfig] = None,
    *,
    max_count: int = 500,
    require_abstract: bool = True,
    use_assumption_queries: bool = True,
    use_prf: bool = True,
) -> List[Work]:
    cfg = config or CollectConfig()
    collector = Collector(cfg)
    collected: List[Work] = []
    seen_ids: Set[str] = set()

    def _absorb(sq: StructuredQuery, *, fallback: bool = True) -> bool:
        """Collect one query, filter, dedup into `collected`. Returns True when max_count reached.

        ``fallback=False`` skips the generic-search recall floor: a too-narrow query then yields
        nothing instead of degrading to a loose full-text match (used for PRF, where the
        generic-search fallback on an over-constrained expansion is the source of topic drift).
        """
        runner = _collect_with_fallback if fallback else _page_through
        works = runner(collector.client, sq, per_page=cfg.per_page, max_pages=cfg.max_pages)
        works = filter_retracted(works)
        if require_abstract:
            works = filter_has_abstract(works)
        for w in works:
            if w.id in seen_ids:
                continue
            seen_ids.add(w.id)
            collected.append(w)
            if len(collected) >= max_count:
                return True
        return False

    base_variants = (
        structured_query_variants(theme) if cfg.relax_search
        else [structured_query_from_theme(theme)]
    )
    # Assumption queries are sentence-like LLM output, so they run as generic full-text
    # (route="search") rather than being squeezed into a field-scoped phrase filter.
    base_anchors = {sq.anchor_string() for sq in base_variants}
    assumption_queries = generate_assumption_queries(theme) if use_assumption_queries else []
    assumption_variants = [
        StructuredQuery(anchor_terms=[q], route=ROUTE_SEARCH)
        for q in assumption_queries
        if q and q not in base_anchors
    ]

    for sq in base_variants + assumption_variants:
        if _absorb(sq):
            return collected

    # Pseudo-relevance feedback (PRF): the user's keywords are an incomplete description of the
    # topic, so when the initial near-field retrieval is THIN, mine the top seeds for salient
    # home-domain vocabulary the keywords missed and run anchored expansion queries to lift recall.
    # This is the home-vocabulary expansion PRF was reassigned to — away from bybridge, whose
    # cross-domain goal it conflicts with (DECISION_LOG 2026-06-23 Phase 2). Each expansion stays
    # anchored to the primary keyword so it REFORMULATES toward the topic rather than drifting
    # (strategy §1.3: reformulation over blind expansion). It only fires below max_count, so broad
    # themes that already fill the pool pay nothing.
    if use_prf and _PRF_MIN_SEEDS <= len(collected) < max_count:
        # Anchor each expansion on the SINGLE head keyword (the topic's most precise term), not the
        # full keyword conjunction: head+salient stays on-topic and returns real field-scoped hits,
        # whereas anchoring on every keyword over-constrains the filter and forces the drift-prone
        # generic fallback (which is disabled here via fallback=False).
        head = next((t for t in theme.keywords.include if t), None)
        primary_anchor = [head] if head else [theme.scope.field]
        existing = list(theme.keywords.include) + [theme.scope.field, theme.goal]
        for term in _salient_terms(collected[:_PRF_SEED_POOL], existing):
            if _absorb(StructuredQuery(anchor_terms=primary_anchor + [term]), fallback=False):
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


_BRIDGE_SEED_SHARE = 4          # a single seed may claim at most cap // 4 of the bridge pool
_DUP_REF_JACCARD = 0.9          # ref-set overlap above which two seed records are the same work
_DUP_REF_MIN = 10               # ...but only when both sides cite enough refs for that to mean something


def _norm_title_key(title: Optional[str]) -> str:
    """Case/punctuation/entity-insensitive title key ('A&amp;B: x!' -> 'a b x')."""
    t = re.sub(r"&[a-z]+;", " ", str(title or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _norm_doi_key(doi: Optional[str]) -> str:
    d = str(doi or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if d.startswith(prefix):
            return d[len(prefix):]
    return d


def _seed_group_ids(seeds: List[Work], per_seed_refs: List[List[str]]) -> List[int]:
    """Group index per seed; DUPLICATE RECORDS OF THE SAME WORK SHARE ONE INDEX.

    F-07 (``docs/field_observations_seihai.md``): the same conference proceedings entered the
    seed set twice under two DOIs, so its 150 references were "cited by 2 seeds" and swallowed
    the whole shared-reference tier. "Cited by >=2 seeds = a strong bridge" only holds when the
    seeds are distinct works, so duplicates are folded before anything is counted.

    Folded when any of: identical normalised DOI, identical normalised title, or near-identical
    reference sets (Jaccard >= 0.9 over >= 10 refs each — two records of one work list the same
    bibliography; two genuinely different papers essentially never do).
    """
    n = len(seeds)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)   # keep the earliest seed as representative

    by_doi: dict = {}
    by_title: dict = {}
    for i, seed in enumerate(seeds):
        dk = _norm_doi_key(seed.doi)
        if dk:
            if dk in by_doi:
                union(by_doi[dk], i)
            else:
                by_doi[dk] = i
        tk = _norm_title_key(seed.title)
        if tk:
            if tk in by_title:
                union(by_title[tk], i)
            else:
                by_title[tk] = i

    ref_sets = [set(refs) for refs in per_seed_refs]
    for i in range(n):
        if len(ref_sets[i]) < _DUP_REF_MIN:
            continue
        for j in range(i + 1, n):
            if len(ref_sets[j]) < _DUP_REF_MIN or find(i) == find(j):
                continue
            inter = len(ref_sets[i] & ref_sets[j])
            if not inter:
                continue
            if inter / len(ref_sets[i] | ref_sets[j]) >= _DUP_REF_JACCARD:
                union(i, j)

    roots: dict = {}
    out: List[int] = []
    for i in range(n):
        r = find(i)
        if r not in roots:
            roots[r] = len(roots)
        out.append(roots[r])
    return out


def _bridge_pool_from_seeds(
    seeds: List[Work],
    cap: int = 50,
    *,
    per_seed_share: int = _BRIDGE_SEED_SHARE,
) -> List[str]:
    """Pick up to `cap` bridge works (the referenced_works of the near-field seeds).

    Bridges are the shared references through which a 2-hop citation scan crosses field
    boundaries. References cited by MULTIPLE seeds rank first (a stronger bridge); the
    remaining refs are then taken round-robin across seeds so every seed contributes
    bridges (diversity), instead of one reference-heavy seed dominating the pool.

    Two guards keep that diversity promise honest (F-07):

    * duplicate seed records are folded into one group first (:func:`_seed_group_ids`), so a
      work that appears twice cannot manufacture a "shared" reference tier by itself;
    * each group may claim at most ``cap // per_seed_share`` slots **in both tiers**. Without
      this the shared tier could fill `cap` on its own and the round-robin — the actual
      diversity guarantee — would never run. The quota is a fairness rule, not a ceiling: when
      no other seed has refs left to offer, a final backfill fills the pool as before, so a
      single-seed (or reference-poor) input still yields a full pool.
    """
    per_seed: List[List[str]] = []
    for seed in seeds:
        refs: List[str] = []
        for r in (seed.referenced_works or []):
            if r and r not in refs:  # dedupe within a single seed, keep order
                refs.append(r)
        per_seed.append(refs)

    groups = _seed_group_ids(seeds, per_seed)
    n_groups = (max(groups) + 1) if groups else 0

    # Per-group ordered ref list + per-ref owning group (first group, in seed order, to list it).
    per_group: List[List[str]] = [[] for _ in range(n_groups)]
    owner: dict = {}
    counts: dict = {}
    first_seen: List[str] = []
    fs_set: Set[str] = set()
    for i, refs in enumerate(per_seed):
        g = groups[i]
        for r in refs:
            if r not in per_group[g]:
                per_group[g].append(r)
                counts[r] = counts.get(r, 0) + 1        # counted once per GROUP, not per record
            if r not in fs_set:
                fs_set.add(r)
                owner[r] = g
                first_seen.append(r)

    # One group has nothing to be fair to -> no quota (keeps the legacy single-seed behaviour).
    quota = cap if n_groups <= 1 else max(1, cap // max(1, per_seed_share))
    used = [0] * n_groups

    selected: List[str] = []
    seen: Set[str] = set()

    def take(ref: str, g: int) -> None:
        seen.add(ref)
        used[g] += 1
        selected.append(ref)

    # 1) shared refs first (cited by >=2 distinct seed works), most-shared first, ties by first-seen
    for r in sorted((x for x in first_seen if counts[x] >= 2), key=lambda x: -counts[x]):
        if len(selected) >= cap:
            break
        g = owner[r]
        if r not in seen and used[g] < quota:
            take(r, g)
    # 2) remaining refs round-robin across seed groups
    idxs = [0] * n_groups
    while len(selected) < cap:
        progressed = False
        for g in range(n_groups):
            if used[g] >= quota:
                continue
            while idxs[g] < len(per_group[g]):
                r = per_group[g][idxs[g]]
                idxs[g] += 1
                if r not in seen:
                    take(r, g)
                    progressed = True
                    break
            if len(selected) >= cap:
                break
        if not progressed:
            break
    # 3) backfill — the quota must not shrink the pool when nobody else can fill it
    if len(selected) < cap:
        for r in first_seen:
            if len(selected) >= cap:
                break
            if r not in seen:
                take(r, owner[r])
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
    # Home-domain exclusion (Phase 2): prefer the seeds' dominant primary_topic Field — OpenAlex's
    # active taxonomy and *less* aggressive than L0 concepts (it only drops papers whose PRIMARY
    # field is home, keeping cross-listed cross-domain work). Fall back to L0 concepts when the
    # seeds carry no primary_topic (older data) so exclusion is never silently lost.
    home_field_ids = dominant_field_ids(seeds)
    sq = StructuredQuery(
        cites=bridges,
        exclude_field_ids=home_field_ids,
        exclude_concept_ids=[] if home_field_ids else _seed_l0_concept_ids(seeds),
        work_type="article",
        max_referenced_works=max_refs,
    )

    collector = Collector(cfg)
    out: List[Work] = []
    seen: Set[str] = set()
    for page in range(1, cfg.max_pages + 1):
        payload = collector.client.get(sq.to_params(per_page=cfg.per_page, page=page))
        new = 0
        for w in filter_retracted(normalize_results(payload)):
            if w.id in exclude or w.id in seen:
                continue
            seen.add(w.id)
            out.append(w)
            new += 1
            if len(out) >= max_count:
                annotate_bridge_signals(out, bridges)
                return out
        if new == 0:
            break
    # Stamp co-citation strength + cross-community betweenness (Phase 2) so every consumer
    # ranks bridge candidates off one signal (src/pipeline/bridges.py). Zero extra API cost.
    annotate_bridge_signals(out, bridges)
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
    use_semantic: bool = True,
    home_field_ids: Optional[List[str]] = None,
) -> List[Work]:
    """Collect Track B (serendipity) candidates from multiple distinct distant domains.

    Phase 3: the PRIMARY path generates a targeted abstraction of the theme plus distant-domain
    hypothetical abstracts (HyDE/Query2doc) and retrieves them through OpenAlex's semantic/ANN
    endpoint, then validates each query (non-empty + not home-converged) before keeping it. If the
    semantic path yields nothing valid — every facet failed validation, or generation failed
    offline — it falls back to the Phase 1 lexical baseline (a Corrective-RAG quality gate), so
    downstream selection never starves. ``use_semantic=False`` forces the legacy lexical path.

    Excludes papers already surfaced in a prior run on id / norm_title / DOI (the title and DOI
    sets, seeded from history, catch the same paper recurring under a different OpenAlex id).
    """
    cfg = config or CollectConfig()
    collector = Collector(cfg)

    if use_semantic:
        # Home Fields to exclude / measure convergence against: caller-supplied (e.g. derived from
        # near-field seeds via dominant_field_ids) or resolved statically from the declared field.
        home_ids = home_field_ids if home_field_ids is not None else resolve_field_ids(theme.scope.field)
        works = _collect_track_b_semantic(
            theme, collector, model, max_count, used_ids, used_titles, used_dois, home_ids, cfg
        )
        if works:
            return works[:max_count]
        print("[info] Track B: semantic 経路が全滅 → 語彙ベースラインへフォールバック (quality-gate)")

    return _collect_track_b_lexical(
        theme, collector, model, max_count, used_ids, used_titles, used_dois, cfg
    )


def collect_track_b_from_spec(
    theme: ThemeInput,
    spec: SerendipitySpec,
    config: Optional[CollectConfig] = None,
    *,
    max_count: int = 60,
    used_ids: Optional[Set[str]] = None,
    used_titles: Optional[Set[str]] = None,
    used_dois: Optional[Set[str]] = None,
    home_field_ids: Optional[List[str]] = None,
) -> List[Work]:
    """Key-free semantic Track B collection from an agent-supplied SerendipitySpec (no LLM).

    The delegation entry point (zero metered cost): the calling agent supplies the targeted-
    abstraction structure + distant-domain HyDE pseudo-abstracts with its OWN inference, and contra
    runs only the OpenAlex ``search.semantic`` retrieval + validation + client-side home-domain
    exclusion — no LLM, no API key. Unlike :func:`collect_track_b` there is NO lexical fallback
    (that path calls the LLM); an empty result simply means the agent should revise the facets.
    """
    cfg = config or CollectConfig()
    collector = Collector(cfg)
    home_ids = home_field_ids if home_field_ids is not None else resolve_field_ids(theme.scope.field)
    return _collect_track_b_semantic(
        theme, collector, "", max_count, used_ids, used_titles, used_dois, home_ids, cfg, spec=spec
    )


def _collect_track_b_semantic(
    theme: ThemeInput,
    collector: "Collector",
    model: str,
    max_count: int,
    used_ids: Optional[Set[str]],
    used_titles: Optional[Set[str]],
    used_dois: Optional[Set[str]],
    home_field_ids: List[str],
    cfg: CollectConfig,
    *,
    spec: Optional[SerendipitySpec] = None,
) -> List[Work]:
    """HyDE/semantic Track B collection: targeted-abstraction facets -> search.semantic -> validate.

    ``spec`` lets a caller pass agent-supplied facets (key-free delegation); when None the facets
    are generated via the LLM. Returns [] (so a self-contained caller falls back to lexical) when
    no facets exist or every facet's query fails the non-empty / home-convergence gate. The
    semantic endpoint returns up to 50 works in a single page (no pagination), so each facet is one
    request.
    """
    if spec is None:
        spec = generate_serendipity_facets(theme, model)
    if spec.is_empty():
        return []

    works: List[Work] = []
    seen_ids: Set[str] = set(used_ids or set())
    seen_titles: Set[str] = set(used_titles or set())
    seen_dois: Set[str] = set(used_dois or set())
    valid_facets = 0
    for facet in spec.facets:
        sq = build_semantic_query(spec.structure, facet.pseudo_abstract)
        try:
            payload = collector.client.get(sq.to_params(per_page=min(cfg.per_page, 50), page=1))
        except OpenAlexError as exc:
            # OpenAlex's semantic (search.semantic) endpoint is experimental and intermittently
            # returns 5xx; one flaky facet must not abort the whole collection, so skip it and let
            # the remaining facets contribute (each facet is an independent semantic query).
            print(f"[info] Track B semantic facet '{facet.domain}' 取得失敗 ({exc}) — スキップ")
            continue
        raw = filter_retracted(normalize_results(payload))
        ok, reason = validate_semantic_results(raw, home_field_ids)
        if not ok:
            print(f"[info] Track B semantic facet '{facet.domain}' 棄却 ({reason})")
            continue
        valid_facets += 1
        for w in exclude_home_field(raw, home_field_ids):
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
        if len(works) >= max_count:
            break
    if valid_facets:
        print(f"[info] Track B semantic: {valid_facets}/{len(spec.facets)} facet 採用 -> {len(works)} 候補")
    return works[:max_count]


def _collect_track_b_lexical(
    theme: ThemeInput,
    collector: "Collector",
    model: str,
    max_count: int,
    used_ids: Optional[Set[str]],
    used_titles: Optional[Set[str]],
    used_dois: Optional[Set[str]],
    cfg: CollectConfig,
) -> List[Work]:
    """Phase 1 lexical Track B baseline (the pre-Phase-3 behaviour, now the quality-gate fallback)."""
    queries = generate_track_b_queries(theme, model)
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
    "collect_track_b_from_spec",
    "collect_citation_candidates",
    "filter_by_used_ids",
    "generate_track_b_query",
    "generate_track_b_queries",
    "generate_assumption_queries",
]
