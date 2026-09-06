"""Problem-solution search planning and fit scoring for Track A anchors."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Sequence

from src.core.models import ThemeInput


_CAPABILITY_VOCAB = [
    "benchmark",
    "dataset",
    "training",
    "simulation",
    "inference",
    "evaluation",
    "pipeline",
    "detection",
    "classification",
    "segmentation",
    "retrieval",
    "monitoring",
    "forecasting",
    "optimization",
    "analysis",
]

_ARTIFACT_VOCAB = [
    "implementation",
    "toolkit",
    "framework",
    "library",
    "model",
    "dataset",
    "demo",
    "space",
    "software",
    "package",
    "replication",
    "reproducibility",
]

_EVIDENCE_VOCAB = [
    "demo",
    "example",
    "quickstart",
    "notebook",
    "benchmark",
    "metric",
    "baseline",
    "leaderboard",
    "evaluation",
    "ablation",
    "paper",
    "citation",
]

_CONSTRAINT_VOCAB = [
    "limitation",
    "caveat",
    "known issue",
    "requirements",
    "dependency",
    "license",
    "security",
    "deprecated",
    "gated",
]

_ECOSYSTEM_VOCAB = [
    "python",
    "pytorch",
    "tensorflow",
    "transformers",
    "scikit",
    "javascript",
    "typescript",
    "react",
    "node",
    "docker",
    "rust",
    "go",
]


@dataclass
class QuerySpec:
    source_type: str
    intent: str
    query: str


@dataclass
class ProblemSearchPlan:
    problem_terms: List[str] = field(default_factory=list)
    capability_terms: List[str] = field(default_factory=list)
    artifact_terms: List[str] = field(default_factory=list)
    evidence_terms: List[str] = field(default_factory=list)
    constraint_terms: List[str] = field(default_factory=list)
    ecosystem_terms: List[str] = field(default_factory=list)


@dataclass
class ProblemSolutionFit:
    score: int
    problem_score: int
    solution_score: int
    execution_score: int
    evaluation_score: int
    constraint_score: int
    matched_problem: str = ""
    solution_mechanism: str = ""
    usable_artifact: str = ""
    visible_constraint: str = ""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9_+.-]+", _norm(text)) if len(t) >= 3]


def _unique(seq: Iterable[str], limit: int) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for item in seq:
        cleaned = _norm(item)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def _vocab_hits(text: str, vocab: Sequence[str], limit: int) -> List[str]:
    lowered = _norm(text)
    hits = []
    for term in vocab:
        plural = "s?" if re.fullmatch(r"[a-zA-Z]+", term) and not term.endswith("s") else ""
        pattern = r"(?<![a-zA-Z0-9_+.-])" + re.escape(term) + plural + r"(?![a-zA-Z0-9_+.-])"
        if re.search(pattern, lowered):
            hits.append(term)
    return _unique(hits, limit)


def _build_heuristic_problem_search_plan(theme: ThemeInput) -> ProblemSearchPlan:
    joined = " ".join(
        [
            theme.theme_overview,
            theme.goal,
            theme.why_problem,
            theme.concern or "",
            " ".join(theme.assumptions),
            theme.scope.field,
            theme.scope.scale,
        ]
    )
    problem_seed = list(theme.keywords.include) + _tokens(theme.concern or "")
    if not theme.keywords.include:
        problem_seed.extend(_tokens(theme.scope.field))
        problem_seed.extend(_tokens(theme.why_problem))
    problem_terms = _unique(problem_seed, 6)
    capability_terms = _vocab_hits(joined, _CAPABILITY_VOCAB, 5)
    if not capability_terms:
        capability_terms = ["evaluation", "pipeline", "benchmark"]
    artifact_terms = _vocab_hits(joined, _ARTIFACT_VOCAB, 5)
    if not artifact_terms:
        artifact_terms = ["implementation", "toolkit", "dataset"]
    evidence_terms = _vocab_hits(joined, _EVIDENCE_VOCAB, 5)
    if not evidence_terms:
        evidence_terms = ["demo", "example", "benchmark"]
    constraint_terms = _vocab_hits(joined, _CONSTRAINT_VOCAB, 5)
    if theme.keywords.exclude:
        constraint_terms.extend(theme.keywords.exclude[:2])
    constraint_terms = _unique(constraint_terms or ["limitation", "requirements"], 5)
    ecosystem_terms = _vocab_hits(joined, _ECOSYSTEM_VOCAB, 5)
    return ProblemSearchPlan(
        problem_terms=problem_terms,
        capability_terms=capability_terms,
        artifact_terms=artifact_terms,
        evidence_terms=evidence_terms,
        constraint_terms=constraint_terms,
        ecosystem_terms=ecosystem_terms,
    )


def _plan_field(value: Any, limit: int) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return _unique([str(item) for item in value if str(item).strip()], limit)


def _merge_problem_search_plans(primary: ProblemSearchPlan, fallback: ProblemSearchPlan) -> ProblemSearchPlan:
    return ProblemSearchPlan(
        problem_terms=_unique(primary.problem_terms + fallback.problem_terms, 6),
        capability_terms=_unique(primary.capability_terms + fallback.capability_terms, 5),
        artifact_terms=_unique(primary.artifact_terms + fallback.artifact_terms, 5),
        evidence_terms=_unique(primary.evidence_terms + fallback.evidence_terms, 5),
        constraint_terms=_unique(primary.constraint_terms + fallback.constraint_terms, 5),
        ecosystem_terms=_unique(primary.ecosystem_terms + fallback.ecosystem_terms, 5),
    )


def _json_object_from_text(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("LLM plan output must be a JSON object")
    return data


def _problem_search_plan_from_json(text: str, fallback: ProblemSearchPlan) -> ProblemSearchPlan:
    data = _json_object_from_text(text)
    candidate = ProblemSearchPlan(
        problem_terms=_plan_field(data.get("problem_terms"), 6),
        capability_terms=_plan_field(data.get("capability_terms"), 5),
        artifact_terms=_plan_field(data.get("artifact_terms"), 5),
        evidence_terms=_plan_field(data.get("evidence_terms"), 5),
        constraint_terms=_plan_field(data.get("constraint_terms"), 5),
        ecosystem_terms=_plan_field(data.get("ecosystem_terms"), 5),
    )
    return _merge_problem_search_plans(candidate, fallback)


def _call_llm_problem_search_plan(theme: ThemeInput, fallback: ProblemSearchPlan, model: str) -> str:
    from src.openai_client import extract_output_text, responses_create

    theme_payload = {
        "theme_overview": theme.theme_overview,
        "goal": theme.goal,
        "why_problem": theme.why_problem,
        "approach_type": theme.approach_type,
        "assumptions": theme.assumptions,
        "scope": {
            "field": theme.scope.field,
            "scale": theme.scope.scale,
            "time_range": theme.scope.time_range,
        },
        "keywords": {"include": theme.keywords.include, "exclude": theme.keywords.exclude},
        "concern": theme.concern,
        "heuristic_fallback": {
            "problem_terms": fallback.problem_terms,
            "capability_terms": fallback.capability_terms,
            "artifact_terms": fallback.artifact_terms,
            "evidence_terms": fallback.evidence_terms,
            "constraint_terms": fallback.constraint_terms,
            "ecosystem_terms": fallback.ecosystem_terms,
        },
    }
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Extract a compact search plan for finding practical repositories, models, "
                    "datasets, software, and research artifacts that directly help solve the "
                    "user's problem. Return JSON only. Keep terms short and searchable. "
                    "Use these exact keys: problem_terms, capability_terms, artifact_terms, "
                    "evidence_terms, constraint_terms, ecosystem_terms. Limits: problem_terms "
                    "up to 6; all other arrays up to 5. Do not include explanatory text."
                ),
            },
            {"role": "user", "content": json.dumps(theme_payload, ensure_ascii=False)},
        ],
        "temperature": 0.0,
    }
    return extract_output_text(responses_create(payload))


def build_llm_problem_search_plan(
    theme: ThemeInput,
    *,
    model: str = "gpt-4o-mini",
    fallback_plan: ProblemSearchPlan | None = None,
) -> ProblemSearchPlan:
    fallback = fallback_plan or _build_heuristic_problem_search_plan(theme)
    try:
        text = _call_llm_problem_search_plan(theme, fallback, model)
        return _problem_search_plan_from_json(text, fallback)
    except Exception:
        return fallback


def build_problem_search_plan(
    theme: ThemeInput,
    *,
    use_llm: bool = False,
    model: str = "gpt-4o-mini",
) -> ProblemSearchPlan:
    fallback = _build_heuristic_problem_search_plan(theme)
    if not use_llm:
        return fallback
    return build_llm_problem_search_plan(theme, model=model, fallback_plan=fallback)


def _quote_if_needed(term: str) -> str:
    return f'"{term}"' if " " in term and not term.startswith('"') else term


def _anchor_terms(plan: ProblemSearchPlan, fallback: str, limit: int = 2) -> str:
    terms = [term for term in plan.problem_terms if term]
    if len(terms) >= 2:
        return " ".join(terms[:limit]).strip()
    if terms:
        return terms[0]
    return fallback


def build_github_query_specs(theme: ThemeInput, plan: ProblemSearchPlan | None = None) -> List[QuerySpec]:
    p = plan or build_problem_search_plan(theme)
    anchor = p.problem_terms[0] if p.problem_terms else theme.scope.field
    def base(parts: Sequence[str]) -> str:
        return " ".join(_quote_if_needed(part) for part in parts if part)

    specs = [
        QuerySpec("github_repository", "problem_capability", base([anchor, p.capability_terms[0], "in:readme"])),
        QuerySpec("github_repository", "implementation_evidence", base([anchor, p.artifact_terms[0], "demo", "in:readme"])),
        QuerySpec("github_repository", "evaluation_evidence", base([anchor, p.evidence_terms[0], "benchmark", "in:readme"])),
    ]
    if len(p.problem_terms) >= 3:
        specs.append(
            QuerySpec(
                "github_repository",
                "problem_specific_relaxed",
                base([p.problem_terms[0], p.problem_terms[2]]),
            )
        )
    if len(p.problem_terms) >= 2:
        specs.append(
            QuerySpec(
                "github_repository",
                "problem_pair_relaxed",
                base(p.problem_terms[:2]),
            )
        )
    if p.ecosystem_terms:
        specs.append(
            QuerySpec(
                "github_repository",
                "ecosystem_fit",
                base([anchor, p.ecosystem_terms[0], "example", "in:readme"]),
            )
        )
    suffix = "pushed:>2025-01-01 archived:false"
    excludes = " ".join(f"NOT {_quote_if_needed(term)}" for term in theme.keywords.exclude if term.strip())
    out = []
    for spec in specs:
        relaxed = spec.intent.endswith("_relaxed")
        query = " ".join([spec.query] + ([excludes] if excludes else []) + ([] if relaxed else [suffix]))
        out.append(QuerySpec(spec.source_type, spec.intent, query))
    return out


def build_github_code_query_specs(theme: ThemeInput, plan: ProblemSearchPlan | None = None) -> List[QuerySpec]:
    p = plan or build_problem_search_plan(theme)
    focused_anchor = _anchor_terms(p, theme.scope.field, limit=2)
    fallback_anchor = p.problem_terms[0] if p.problem_terms else theme.scope.field

    def base(parts: Sequence[str]) -> str:
        return " ".join(_quote_if_needed(part) for part in parts if part)

    excludes = " ".join(f"NOT {_quote_if_needed(term)}" for term in theme.keywords.exclude if term.strip())
    specs = [
        QuerySpec("github_code", "code_example_path", base([focused_anchor, "path:examples"])),
        QuerySpec("github_code", "code_notebook", base([focused_anchor, "extension:ipynb"])),
        QuerySpec("github_code", "code_package", base([focused_anchor, "filename:pyproject.toml"])),
        QuerySpec("github_code", "code_fallback", base([fallback_anchor, p.artifact_terms[0]])),
    ]
    out = []
    for spec in specs:
        query = " ".join([spec.query] + ([excludes] if excludes else []))
        out.append(QuerySpec(spec.source_type, spec.intent, query))
    return out


def build_plain_query_specs(
    source_type: str,
    theme: ThemeInput,
    plan: ProblemSearchPlan | None = None,
) -> List[QuerySpec]:
    p = plan or build_problem_search_plan(theme)
    focused_anchor = _anchor_terms(p, theme.scope.field, limit=3)
    fallback_anchor = _anchor_terms(p, theme.scope.field, limit=2)
    return [
        QuerySpec(source_type, "problem_capability", " ".join([focused_anchor, p.capability_terms[0]]).strip()),
        QuerySpec(source_type, "artifact_evidence", " ".join([focused_anchor, p.artifact_terms[0]]).strip()),
        QuerySpec(source_type, "evaluation_evidence", " ".join([focused_anchor, p.evidence_terms[0]]).strip()),
        QuerySpec(source_type, "problem_only", fallback_anchor.strip()),
    ]


def _term_hits(terms: Sequence[str], text: str) -> List[str]:
    lowered = _norm(text)
    hits = []
    for term in terms:
        cleaned = _norm(term)
        if not cleaned:
            continue
        if " " in cleaned:
            pieces = [re.escape(piece) for piece in cleaned.split() if piece]
            pattern = r"(?<![a-zA-Z0-9])" + r"[^a-zA-Z0-9]+".join(pieces) + r"(?![a-zA-Z0-9])"
            matched = bool(re.search(pattern, lowered))
        else:
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(cleaned) + r"(?![a-zA-Z0-9])"
            matched = bool(re.search(pattern, lowered))
        if matched:
            hits.append(term)
    return _unique(hits, 5)


def _score_hits(hits: Sequence[str], max_score: int, per_hit: int) -> int:
    return min(len(hits) * per_hit, max_score)


def score_problem_solution_fit(
    theme: ThemeInput,
    *,
    text: str,
    source_type: str,
    tags: Sequence[str] | None = None,
    metadata_text: str = "",
    plan: ProblemSearchPlan | None = None,
) -> ProblemSolutionFit:
    p = plan or build_problem_search_plan(theme)
    haystack = _norm(" ".join([text, " ".join(tags or []), metadata_text, source_type]))
    problem_hits = _term_hits(p.problem_terms, haystack)
    capability_hits = _term_hits(p.capability_terms, haystack)
    artifact_hits = _term_hits(p.artifact_terms, haystack)
    evidence_hits = _term_hits(p.evidence_terms, haystack)
    constraint_hits = _term_hits(p.constraint_terms, haystack)
    exclude_hits = _term_hits(theme.keywords.exclude, haystack)

    problem_score = _score_hits(problem_hits, 25, 9)
    solution_score = min(_score_hits(capability_hits, 15, 6) + _score_hits(artifact_hits, 10, 5), 25)
    execution_score = min(_score_hits(evidence_hits, 16, 5) + (4 if "demo" in haystack or "example" in haystack else 0), 20)
    evaluation_score = min(
        _score_hits(_term_hits(["benchmark", "metric", "baseline", "evaluation", "paper", "citation"], haystack), 20, 5),
        20,
    )
    constraint_score = min(_score_hits(constraint_hits, 10, 4), 10)
    total = problem_score + solution_score + execution_score + evaluation_score + constraint_score
    if problem_score == 0:
        total = min(total, 15)
    if exclude_hits:
        total = min(total, 25)
    if "awesome" in haystack:
        total = min(total, 30)
    elif any(noise in haystack for noise in (" tutorial", " course", " curated list", " link list")):
        total = min(total, 45)

    return ProblemSolutionFit(
        score=min(total, 100),
        problem_score=problem_score,
        solution_score=solution_score,
        execution_score=execution_score,
        evaluation_score=evaluation_score,
        constraint_score=constraint_score,
        matched_problem=", ".join(problem_hits[:3]),
        solution_mechanism=", ".join((capability_hits + artifact_hits)[:3]),
        usable_artifact=", ".join((artifact_hits + evidence_hits)[:3]),
        visible_constraint=", ".join(constraint_hits[:3]),
    )
