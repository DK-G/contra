"""Track A Git practical-anchor collection."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

from src.core.models import GitRepository, ThemeInput, Work
from src.github.client import GitHubClient

_RESEARCH_TASK_TERMS = [
    "benchmark",
    "dataset",
    "training",
    "simulation",
    "inference",
    "evaluation",
    "pipeline",
]

_IMPLEMENTATION_TERMS = [
    "implementation",
    "toolkit",
    "framework",
    "code",
]


def _is_ascii_text(text: str) -> bool:
    return text.isascii()


@dataclass
class GitCollectConfig:
    per_page: int = 10
    max_repos: int = 5
    include_readme: bool = True
    include_issues: bool = True
    issue_sample_size: int = 5
    pool_relative_lma: bool = True
    # A-RS2: release-cadence + CI-health signals add ~2 REST calls per repo and
    # blow the unauthenticated 60 req/h budget, so default to auto: enabled only
    # when the client carries a token. Set True/False to force.
    include_rich_signals: Optional[bool] = None
    rich_sample_size: int = 10


def _clean_token(token: str) -> str:
    text = token.strip().strip('"').strip("'")
    if ":" in text or ">" in text or "<" in text:
        return text
    return f'"{text}"' if " " in text else text


def build_track_a_git_query(theme: ThemeInput, extra_terms: Optional[Sequence[str]] = None) -> str:
    tokens: List[str] = []
    # To avoid 0 hits due to too many AND terms, only use the first include keyword
    if theme.keywords.include:
        tokens.append(theme.keywords.include[0])
    elif theme.scope.field:
        tokens.append(theme.scope.field)
        
    # Limit goal text in query to avoid overly specific queries
    if theme.goal and _is_ascii_text(theme.goal) and len(theme.goal) < 60:
        tokens.append(theme.goal)
        
    # Discovery Scoping: target demos/examples in README
    tokens.append("demo in:readme")
    
    if extra_terms:
        tokens.extend(extra_terms)

    unique_tokens: List[str] = []
    seen = set()
    for token in tokens:
        cleaned = _clean_token(token)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique_tokens.append(cleaned)
            
    exclude_tokens: List[str] = []
    for token in theme.keywords.exclude:
        if token.strip():
            cleaned = _clean_token(token.strip())
            if cleaned:
                exclude_tokens.append(f"NOT {cleaned}")
            
    # Activity filtering: target repos pushed since 2025-01-01 to avoid stale code bases
    all_parts = unique_tokens + exclude_tokens
    all_parts.append("pushed:>2025-01-01")
    return " ".join(all_parts)




def _decode_readme(payload: dict) -> str:
    if payload.get("encoding") != "base64":
        return ""
    content = payload.get("content", "")
    if not content:
        return ""
    raw = base64.b64decode(content.encode("utf-8"))
    return raw.decode("utf-8", errors="replace")


def _normalize_repo(item: dict, readme_text: str = "") -> GitRepository:
    license_info = item.get("license") or {}
    return GitRepository(
        full_name=str(item.get("full_name", "")),
        html_url=str(item.get("html_url", "")),
        description=str(item.get("description") or ""),
        stars=int(item.get("stargazers_count") or 0),
        forks=int(item.get("forks_count") or 0),
        watchers=int(item.get("watchers_count") or 0),
        open_issues=int(item.get("open_issues_count") or 0),
        license_name=str(license_info.get("spdx_id") or license_info.get("name") or ""),
        default_branch=str(item.get("default_branch") or ""),
        updated_at=str(item.get("updated_at") or ""),
        pushed_at=str(item.get("pushed_at") or ""),
        topics=[str(t) for t in (item.get("topics") or []) if t],
        readme_text=readme_text,
    )


def _updated_year(updated_at: str) -> int:
    if not updated_at:
        return 0
    try:
        return datetime.fromisoformat(updated_at.replace("Z", "+00:00")).year
    except ValueError:
        return 0


def _days_since(updated_at: str) -> Optional[int]:
    if not updated_at:
        return None
    try:
        dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return max((datetime.now(dt.tzinfo) - dt).days, 0)
    except ValueError:
        return None


def _theme_fit_score(theme: ThemeInput, repo: GitRepository) -> int:
    text = " ".join(
        [
            repo.full_name,
            repo.description,
            " ".join(repo.topics),
            repo.readme_text[:2000],
        ]
    ).lower()
    include_hits = sum(1 for token in theme.keywords.include if token and token.lower() in text)
    exclude_hits = sum(1 for token in theme.keywords.exclude if token and token.lower() in text)
    score = min(include_hits * 10, 30) - min(exclude_hits * 10, 20)
    return max(score, 0)


def _activity_score(repo: GitRepository) -> int:
    days = _days_since(repo.updated_at)
    if days is None:
        return 0
    if days <= 30:
        return 15
    if days <= 90:
        return 12
    if days <= 180:
        return 8
    if days <= 365:
        return 4
    return 1


def _adoption_score(repo: GitRepository) -> int:
    stars = repo.stars
    if stars >= 500:
        return 15
    if stars >= 100:
        return 12
    if stars >= 30:
        return 8
    if stars >= 5:
        return 4
    return 1 if stars > 0 else 0


def _license_score(repo: GitRepository) -> int:
    if not repo.license_name or repo.license_name == "NOASSERTION":
        return 0
    return 10


def _readme_score(repo: GitRepository) -> int:
    text = repo.readme_text.lower()
    if not text:
        return 0
    score = 3
    for signal in ("install", "usage", "example", "train", "evaluate", "inference", "setup"):
        if signal in text:
            score += 2
    return min(score, 15)


def _research_linkage_score(repo: GitRepository) -> int:
    text = f"{repo.description}\n{repo.readme_text}".lower()
    for signal in ("arxiv", "paper", "citation", "dataset", "benchmark"):
        if signal in text:
            return 5
    return 0


# Refined scoring helpers (Pillars 1 to 4)

def _readme_completeness_and_mature_categories(readme_text: str) -> int:
    """Evaluate README completeness (Max 20pts).
    
    Checks basic content (What/How) and mature sections (Why/When) via heading heuristics.
    """
    text = readme_text.lower()
    if not text:
        return 0
    
    score = 4  # Base score for having a README
    
    # What / How indicators (up to 10pts)
    for signal in ("install", "usage", "setup", "quickstart", "getting started"):
        if signal in text:
            score += 2
    score = min(score, 10)
    
    # Why / When mature indicators (up to 10pts)
    why_signals = ("why ", "purpose", "objective", "advantage", "benefit", "comparison", "features")
    when_signals = ("roadmap", "status", "future plan", "changelog", "version history")
    
    has_why = any(sig in text for sig in why_signals)
    has_when = any(sig in text for sig in when_signals)
    
    if has_why:
        score += 5
    if has_when:
        score += 5
        
    return min(score, 20)


def _code_examples_density(readme_text: str) -> int:
    """Evaluate code examples density in README (Max 10pts)."""
    if not readme_text:
        return 0
    code_blocks = readme_text.count("```") // 2
    if code_blocks >= 3:
        return 10
    if code_blocks >= 1:
        return 5
    return 0


# Completed-state floor thresholds (A-RS1, DECISION_LOG 2026-06-12).
# A stale but *finished* library (small, perfect, needs no changes) must be
# distinguished from an abandoned/unused one before its maintenance score is
# floored. Requires an adoption signal AND past issue activity with a high
# close rate, mirroring the "Zero Issues Trap" logic in Pillar 3.
_LMA_COMPLETED_FLOOR = 12
_LMA_COMPLETED_FLOOR_STRONG = 15
_LMA_ADOPT_STARS = 50
_LMA_ADOPT_FORKS = 10
_LMA_ADOPT_STARS_STRONG = 200


def _is_completed_stable(repo: GitRepository) -> bool:
    """Stale repo that looks finished + adopted + historically maintained.

    "push is old + few open issues" alone cannot tell "finished, needs no
    changes" apart from "nobody uses it". We require BOTH an adoption signal
    (stars/forks) AND evidence of past issue activity with a high close rate
    (people used it and issues got resolved).
    """
    adopted = repo.stars >= _LMA_ADOPT_STARS or repo.forks >= _LMA_ADOPT_FORKS
    has_issue_history = (repo.issue_open_count + repo.issue_closed_count) > 0
    high_close_rate = (
        repo.issue_closed_count > 0
        and repo.issue_closed_count >= repo.issue_open_count
    )
    return adopted and has_issue_history and high_close_rate


def _lma_score(repo: GitRepository) -> int:
    """Evaluate Level of Maintenance Activity (LMA) (Max 25pts)."""
    days = _days_since(repo.pushed_at or repo.updated_at)
    if days is None:
        return 0

    # Recency-based freshness (an active-ecosystem proxy).
    if days <= 14:
        freshness = 25
    elif days <= 45:
        freshness = 20
    elif days <= 90:
        freshness = 15
    elif days <= 180:
        freshness = 10
    elif days <= 365:
        freshness = 5
    else:
        freshness = 1

    # Completed-state floor: do not punish a finished, adopted, historically
    # maintained library as hard as an abandoned/unused one (A-RS1).
    if _is_completed_stable(repo):
        floor = (
            _LMA_COMPLETED_FLOOR_STRONG
            if repo.stars >= _LMA_ADOPT_STARS_STRONG
            else _LMA_COMPLETED_FLOOR
        )
        return max(freshness, floor)

    return freshness


# Pool-relative LMA normalization (A-RS1 remedy 2, DECISION_LOG 2026-06-12).
# Treat the candidate pool itself as a domain sample: when an entire mature
# domain is stale, the absolute recency tiers crush every repo to the bottom,
# so we additionally credit each repo by its recency *rank within the pool*.
# Applied via max() so it only ever lifts a repo, never lowers a genuinely
# fresh one. The ceiling sits below the completed-state floor so rank alone
# never outranks a maintained + adopted library.
_LMA_POOL_CEILING = 12
_LMA_POOL_BASE = 2
_LMA_POOL_MIN_SIZE = 3


def _apply_pool_relative_lma(repos: Sequence[GitRepository]) -> None:
    """Lift each repo's LMA by its recency rank within the candidate pool.

    Mutates `repo.lma_score` and recomputes `repo.reliability_score` in place.
    No-op for pools smaller than `_LMA_POOL_MIN_SIZE` (rank is uninformative).
    Ties on recency receive equal credit.
    """
    rankable = [
        (repo, days)
        for repo in repos
        if (days := _days_since(repo.pushed_at or repo.updated_at)) is not None
    ]
    if len(rankable) < _LMA_POOL_MIN_SIZE:
        return

    n = len(rankable)
    days_list = [days for _, days in rankable]
    span = _LMA_POOL_CEILING - _LMA_POOL_BASE
    for repo, days in rankable:
        # Fresher (fewer days) ranks higher; ties share a percentile.
        more_stale = sum(1 for other in days_list if other > days)
        percentile = more_stale / (n - 1)
        relative = round(_LMA_POOL_BASE + percentile * span)
        if relative > repo.lma_score:
            repo.lma_score = relative
            repo.reliability_score = min(
                repo.impl_doc_score
                + repo.lma_score
                + repo.community_score
                + repo.security_score,
                100,
            )


def _fork_to_star_score(repo: GitRepository) -> int:
    """Evaluate Fork-to-Star ratio (Max 10pts)."""
    if repo.stars < 10:
        return 5 if repo.forks > 0 else 0
        
    ratio = repo.forks / repo.stars
    if ratio >= 0.10:
        return 10
    if ratio >= 0.05:
        return 7
    if ratio >= 0.02:
        return 4
    return 1


def _security_and_practices_score(repo: GitRepository) -> int:
    """Evaluate Security & Enterprise Practices (Max 25pts)."""
    score = 0
    
    # License Clarity (10pts)
    if repo.license_name and repo.license_name != "NOASSERTION":
        score += 10
        
    # Heuristics for Security, CI, Testing (Max 10pts)
    text = f"{repo.description}\n{repo.readme_text}".lower()
    security_ci_signals = (
        "security", "vulnerability", "lts", "github actions", "ci/cd", 
        "workflow", "pytest", "travis", "circleci"
    )
    heur_score = min(sum(2 for sig in security_ci_signals if sig in text), 10)
    
    # Research linkage / citation (Max 5pts)
    has_research = 0
    for signal in ("arxiv", "paper", "citation", "dataset", "benchmark"):
        if signal in text:
            has_research = 5
            break

    return score + heur_score + has_research


# A-RS2 (DECISION_LOG 2026-06-12 concern 2): in the vibe-coding era a complete
# README (and the mere existence of a workflow file) is cheap to generate, so
# Pillar 1 shifts weight off README heuristics onto "time" signals that cannot
# be faked by scaffolding: real release cadence and CI that actually runs and
# passes. These need extra REST calls and are gated on a token being present.

def _release_cadence_score(repo: GitRepository) -> int:
    """Versioning discipline from tagged releases (Max 6pts).

    Counts published releases — a generator can scaffold a README but not a
    history of cut releases. Recency itself is Pillar 2's job, not cadence's.
    """
    n = repo.release_count
    if n <= 0:
        return 0
    score = 2  # at least one real release
    if n >= 3:
        score += 2
    if n >= 6:
        score += 2
    return min(score, 6)


def _ci_health_score(repo: GitRepository) -> int:
    """CI that actually runs and passes (Max 6pts).

    Distinct from the Pillar 4 heuristic (which only sees a workflow file
    mentioned in text): this scores the *fact* of recent runs and their
    success, which scaffolding cannot manufacture.
    """
    if repo.ci_runs_sampled <= 0:
        return 0
    score = 3  # CI executes at all
    ratio = repo.ci_recent_success / repo.ci_runs_sampled
    if ratio >= 0.8:
        score += 3
    elif ratio >= 0.5:
        score += 1
    return min(score, 6)


def _verified_maturity_score(repo: GitRepository) -> int:
    """Pillar 1 "time" sub-score: release cadence + CI health (Max 12pts)."""
    return _release_cadence_score(repo) + _ci_health_score(repo)


def _fetch_issue_signal(
    client: GitHubClient, full_name: str, sample_size: int, repo_stars: int = 0
) -> tuple[int, str, int, int]:
    """Return (issue_score, summary, open_count, closed_count) from an issue sample."""
    payload = client.get(
        f"/repos/{full_name}/issues",
        {"state": "all", "per_page": sample_size},
    )
    issues = [item for item in payload if "pull_request" not in item]
    if not issues:
        # Zero Issues Trap check
        if repo_stars >= 50:
            return 0, "issuesなし (警告: ゼロIssueの罠)", 0, 0
        return 3, "issuesなし (小規模または新規)", 0, 0

    open_count = sum(1 for item in issues if item.get("state") == "open")
    closed_count = sum(1 for item in issues if item.get("state") == "closed")
    body_rich = any((item.get("body") or "").strip() for item in issues)
    labels = sorted(
        {
            str(label.get("name", "")).strip()
            for item in issues
            for label in (item.get("labels") or [])
            if str(label.get("name", "")).strip()
        }
    )
    score = 3
    if body_rich:
        score += 3
    if closed_count > 0:
        score += 3
    if labels:
        score += 1

    summary = f"issues {len(issues)}件 / open {open_count} / closed {closed_count}"
    if labels:
        summary += f" / labels: {', '.join(labels[:3])}"
    return min(score, 10), summary, open_count, closed_count


def _apply_reliability(theme: ThemeInput, repo: GitRepository) -> GitRepository:
    # Pillar 1 (Max 30). When harder-to-fake "time" signals are available
    # (A-RS2), migrate weight: README heuristics are scaled to 0.6 (max 12 + 6)
    # and the freed 12pts go to verified maturity (release cadence + CI health).
    # Without rich signals we keep the original README-heavy scoring (no
    # regression for unauthenticated runs).
    if repo.has_rich_signals:
        readme_comp = round(_readme_completeness_and_mature_categories(repo.readme_text) * 12 / 20)
        code_dens = round(_code_examples_density(repo.readme_text) * 6 / 10)
        verified = _verified_maturity_score(repo)
        repo.verified_maturity_score = verified
        impl_doc = readme_comp + code_dens + verified
    else:
        readme_comp = _readme_completeness_and_mature_categories(repo.readme_text)
        code_dens = _code_examples_density(repo.readme_text)
        repo.verified_maturity_score = 0
        impl_doc = readme_comp + code_dens

    # Pillar 2 (Max 25)
    lma = _lma_score(repo)
    
    # Pillar 3 (Max 20)
    fork_star = _fork_to_star_score(repo)
    community = fork_star + repo.issue_score
    
    # Pillar 4 (Max 25)
    security = _security_and_practices_score(repo)
    
    total = impl_doc + lma + community + security
    
    repo.impl_doc_score = impl_doc
    repo.lma_score = lma
    repo.community_score = community
    repo.security_score = security
    
    # Backwards compatibility metrics
    repo.theme_fit_score = _theme_fit_score(theme, repo)
    repo.activity_score = _activity_score(repo)
    repo.adoption_score = _adoption_score(repo)
    repo.license_score = _license_score(repo)
    repo.readme_score = _readme_score(repo)
    repo.research_linkage_score = _research_linkage_score(repo)
    
    repo.reliability_score = min(total, 100)
    return repo


def repository_to_work(repo: GitRepository) -> Work:
    abstract_parts = [repo.description.strip()]
    if repo.readme_text.strip():
        abstract_parts.append(repo.readme_text.strip()[:2000])
    abstract = "\n\n".join(part for part in abstract_parts if part) or None
    return Work(
        id=repo.html_url,
        title=repo.full_name,
        year=_updated_year(repo.updated_at),
        venue="GitHub",
        doi=None,
        cited_by_count=repo.stars,
        abstract=abstract,
        concepts=list(repo.topics),
        publication_type="github_repository",
        source_meta={
            "license_name": repo.license_name,
            "updated_at": repo.updated_at,
            "open_issues": repo.open_issues,
            "watchers": repo.watchers,
            "forks": repo.forks,
            "issue_signal_summary": repo.issue_signal_summary,
            "reliability_score": repo.reliability_score,
            "theme_fit_score": repo.theme_fit_score,
            "activity_score": repo.activity_score,
            "adoption_score": repo.adoption_score,
            "license_score": repo.license_score,
            "readme_score": repo.readme_score,
            "issue_score": repo.issue_score,
            "research_linkage_score": repo.research_linkage_score,
            "impl_doc_score": repo.impl_doc_score,
            "lma_score": repo.lma_score,
            "community_score": repo.community_score,
            "security_score": repo.security_score,
            "issue_open_count": repo.issue_open_count,
            "issue_closed_count": repo.issue_closed_count,
            "has_rich_signals": repo.has_rich_signals,
            "verified_maturity_score": repo.verified_maturity_score,
            "release_count": repo.release_count,
            "latest_release_at": repo.latest_release_at,
            "ci_runs_sampled": repo.ci_runs_sampled,
            "ci_recent_success": repo.ci_recent_success,
        },
    )


def _fetch_readme_text(client: GitHubClient, full_name: str) -> str:
    payload = client.get(f"/repos/{full_name}/readme")
    return _decode_readme(payload)


def _fetch_release_signal(client: GitHubClient, full_name: str, sample_size: int) -> tuple[int, str]:
    """Return (release_count, latest_published_at) from a releases sample."""
    payload = client.get(f"/repos/{full_name}/releases", {"per_page": sample_size})
    releases = payload if isinstance(payload, list) else []
    count = len(releases)
    latest = str(releases[0].get("published_at") or "") if releases else ""
    return count, latest


def _fetch_ci_signal(client: GitHubClient, full_name: str, sample_size: int) -> tuple[int, int]:
    """Return (runs_sampled, recent_success_count) from the Actions runs sample."""
    payload = client.get(f"/repos/{full_name}/actions/runs", {"per_page": sample_size})
    runs = payload.get("workflow_runs") or [] if isinstance(payload, dict) else []
    sampled = len(runs)
    success = sum(1 for run in runs if run.get("conclusion") == "success")
    return sampled, success


def _resolve_rich_signals(cfg: GitCollectConfig, client: GitHubClient) -> bool:
    """Auto-enable rich signals only when a token is present (rate-limit guard)."""
    if cfg.include_rich_signals is not None:
        return cfg.include_rich_signals
    token = getattr(getattr(client, "config", None), "token", None)
    return bool(token)


def _attach_rich_signals(client: GitHubClient, repo: GitRepository, sample_size: int) -> None:
    """Fetch release-cadence + CI-health signals; degrade gracefully on error."""
    try:
        repo.release_count, repo.latest_release_at = _fetch_release_signal(
            client, repo.full_name, sample_size
        )
    except Exception:
        repo.release_count, repo.latest_release_at = 0, ""
    try:
        repo.ci_runs_sampled, repo.ci_recent_success = _fetch_ci_signal(
            client, repo.full_name, sample_size
        )
    except Exception:
        repo.ci_runs_sampled, repo.ci_recent_success = 0, 0
    repo.has_rich_signals = True


def collect_track_a_git_repos(
    theme: ThemeInput,
    config: Optional[GitCollectConfig] = None,
    client: Optional[GitHubClient] = None,
) -> List[GitRepository]:
    cfg = config or GitCollectConfig()
    gh = client or GitHubClient()
    include_rich = _resolve_rich_signals(cfg, gh)
    query = build_track_a_git_query(theme)
    payload = gh.get(
        "/search/repositories",
        {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": cfg.per_page,
        },
    )
    items = payload.get("items") or []
    repos: List[GitRepository] = []
    for item in items:
        readme_text = ""
        issue_score = 0
        issue_signal_summary = ""
        if cfg.include_readme and item.get("full_name"):
            try:
                readme_text = _fetch_readme_text(gh, str(item["full_name"]))
            except Exception:
                readme_text = ""
        repo = _normalize_repo(item, readme_text=readme_text)
        issue_open_count = 0
        issue_closed_count = 0
        if cfg.include_issues and repo.full_name:
            try:
                (
                    issue_score,
                    issue_signal_summary,
                    issue_open_count,
                    issue_closed_count,
                ) = _fetch_issue_signal(
                    gh, repo.full_name, cfg.issue_sample_size, repo.stars
                )
            except Exception:
                issue_score, issue_signal_summary = 0, "issue取得失敗"
        repo.issue_score = issue_score
        repo.issue_signal_summary = issue_signal_summary
        repo.issue_open_count = issue_open_count
        repo.issue_closed_count = issue_closed_count
        if include_rich and repo.full_name:
            _attach_rich_signals(gh, repo, cfg.rich_sample_size)
        repos.append(_apply_reliability(theme, repo))
        if len(repos) >= cfg.max_repos:
            break
    if cfg.pool_relative_lma:
        _apply_pool_relative_lma(repos)
    repos.sort(key=lambda repo: repo.reliability_score, reverse=True)
    return repos


def collect_track_a_git_works(
    theme: ThemeInput,
    config: Optional[GitCollectConfig] = None,
    client: Optional[GitHubClient] = None,
) -> List[Work]:
    repos = collect_track_a_git_repos(theme, config=config, client=client)
    return [repository_to_work(repo) for repo in repos]
