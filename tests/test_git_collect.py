"""Tests for Track A Git practical-anchor collection."""

from __future__ import annotations

import base64

from src.core.models import GitRepository, Keywords, Scope, ThemeInput
from src.pipeline.git_collect import (
    GitCollectConfig,
    _apply_pool_relative_lma,
    _apply_reliability,
    _ci_health_score,
    _decode_readme,
    _is_completed_stable,
    _lma_score,
    _release_cadence_score,
    _resolve_rich_signals,
    _third_party_score,
    _verified_maturity_score,
    build_track_a_git_query,
    collect_track_a_git_repos,
    collect_track_a_git_works,
    repository_to_work,
)


def _theme() -> ThemeInput:
    return ThemeInput(
        theme_overview="Use digital twins to improve power-grid fault recovery.",
        goal="Find practical implementations and evaluation code.",
        why_problem="Operating constraints block deployment.",
        approach_type="system-building",
        assumptions=[],
        scope=Scope(field="energy systems", scale="grid", time_range="recent"),
        keywords=Keywords(
            include=["digital twin", "power grid", "fault recovery"],
            exclude=["gamification"],
        ),
    )


def test_build_track_a_git_query_includes_theme_and_exclude_terms():
    query = build_track_a_git_query(_theme())
    assert "digital twin" in query
    assert "NOT gamification" in query
    assert "demo in:readme" in query
    assert "pushed:>2025-01-01" in query




def test_decode_readme_handles_base64_payload():
    payload = {
        "encoding": "base64",
        "content": base64.b64encode(b"# Title\nsetup instructions").decode("utf-8"),
    }
    assert "setup instructions" in _decode_readme(payload)


class _FakeGitHubClient:
    def __init__(self) -> None:
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        if path == "/search/repositories":
            return {
                "items": [
                    {
                        "full_name": "acme/grid-twin",
                        "html_url": "https://github.com/acme/grid-twin",
                        "description": "grid twin toolkit",
                        "stargazers_count": 120,
                        "forks_count": 20,
                        "watchers_count": 10,
                        "open_issues_count": 4,
                        "license": {"spdx_id": "MIT"},
                        "default_branch": "main",
                        "updated_at": "2026-06-01T00:00:00Z",
                        "pushed_at": "2026-06-01T00:00:00Z",
                        "topics": ["digital-twin", "power-grid"],
                    }
                ]
            }
        if path == "/repos/acme/grid-twin/readme":
            return {
                "encoding": "base64",
                "content": base64.b64encode(b"# Grid Twin\nRun this toolkit\n```python\nimport twin\n```").decode("utf-8"),
            }
        if path == "/repos/acme/grid-twin/issues":
            return [
                {
                    "state": "open",
                    "body": "GPU setup fails on Windows",
                    "labels": [{"name": "bug"}],
                },
                {
                    "state": "closed",
                    "body": "Evaluation pipeline fixed",
                    "labels": [{"name": "question"}],
                },
            ]
        raise AssertionError(path)


def test_collect_track_a_git_repos_fetches_search_and_readme():
    client = _FakeGitHubClient()
    repos = collect_track_a_git_repos(
        _theme(),
        config=GitCollectConfig(per_page=5, max_repos=3, include_readme=True),
        client=client,
    )
    assert len(repos) == 1
    repo = repos[0]
    assert repo.full_name == "acme/grid-twin"
    assert repo.license_name == "MIT"
    assert "Run this toolkit" in repo.readme_text
    assert repo.issue_score > 0
    assert repo.reliability_score > 0
    
    # 4-pillar scoring assertions
    assert repo.impl_doc_score > 0
    assert repo.lma_score > 0
    assert repo.community_score > 0
    assert repo.security_score > 0
    
    assert client.calls[0][0] == "/search/repositories"
    assert client.calls[1][0] == "/repos/acme/grid-twin/readme"
    assert client.calls[2][0] == "/repos/acme/grid-twin/issues"


def test_repository_to_work_maps_repo_fields():
    client = _FakeGitHubClient()
    repo = collect_track_a_git_repos(_theme(), client=client)[0]
    work = repository_to_work(repo)
    assert work.id == "https://github.com/acme/grid-twin"
    assert work.title == "acme/grid-twin"
    assert work.venue == "GitHub"
    assert work.cited_by_count == 120
    assert work.publication_type == "github_repository"
    assert "Run this toolkit" in (work.abstract or "")
    assert work.source_meta["reliability_score"] > 0
    assert "issues 2件" in work.source_meta["issue_signal_summary"]
    
    # Refined scoring pillars mapping verification
    assert work.source_meta["impl_doc_score"] > 0
    assert work.source_meta["lma_score"] > 0
    assert work.source_meta["community_score"] > 0
    assert work.source_meta["security_score"] > 0


def test_collect_track_a_git_works_returns_work_objects():
    client = _FakeGitHubClient()
    works = collect_track_a_git_works(_theme(), client=client)
    assert len(works) == 1
    assert works[0].publication_type == "github_repository"


def _stale_repo(**overrides) -> GitRepository:
    base = dict(
        full_name="acme/finished-util",
        html_url="https://github.com/acme/finished-util",
        stars=300,
        forks=40,
        pushed_at="2023-01-01T00:00:00Z",  # >365 days stale
        issue_open_count=1,
        issue_closed_count=8,
    )
    base.update(overrides)
    return GitRepository(**base)


def test_lma_floor_protects_finished_adopted_library():
    # Stale but adopted + high close rate: must not drop to the abandoned floor (1).
    repo = _stale_repo()
    assert _is_completed_stable(repo) is True
    assert _lma_score(repo) == 15  # strong adoption (stars >= 200) -> 15


def test_lma_floor_moderate_adoption_uses_base_floor():
    repo = _stale_repo(stars=60)
    assert _is_completed_stable(repo) is True
    assert _lma_score(repo) == 12


def test_lma_no_floor_for_abandoned_unused_repo():
    # Stale, no adoption, no issue history: stays at the abandoned floor (1).
    repo = _stale_repo(stars=3, forks=0, issue_open_count=0, issue_closed_count=0)
    assert _is_completed_stable(repo) is False
    assert _lma_score(repo) == 1


def test_lma_no_floor_when_issues_pile_up_unresolved():
    # Adopted but low close rate (open >> closed) signals neglect, not completion.
    repo = _stale_repo(issue_open_count=9, issue_closed_count=1)
    assert _is_completed_stable(repo) is False
    assert _lma_score(repo) == 1


def test_lma_floor_never_lowers_a_fresh_score():
    # pushed_at must be RELATIVE to now: a hardcoded date silently ages past the freshness
    # tiers, and once freshness drops to the completed-stable floor (15) this test stops
    # verifying anything (it sat red for weeks exactly that way — see Changelog 2026-08-21).
    from datetime import datetime, timedelta, timezone

    five_days_ago = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    repo = _stale_repo(pushed_at=five_days_ago)
    assert _is_completed_stable(repo) is True     # the floor (15) is in play...
    assert _lma_score(repo) == 25                 # ...yet max(freshness, floor) keeps the fresh 25


def _scored_repo(name: str, pushed_at: str, lma: int) -> GitRepository:
    return GitRepository(
        full_name=name,
        html_url=f"https://github.com/{name}",
        pushed_at=pushed_at,
        lma_score=lma,
        impl_doc_score=20,
        community_score=10,
        security_score=15,
        reliability_score=20 + lma + 10 + 15,
    )


def test_pool_relative_lma_lifts_freshest_among_stale_domain():
    # A mature domain where every repo is stale (absolute LMA would be 1).
    most_stale = _scored_repo("acme/old", "2023-01-01T00:00:00Z", lma=1)
    mid = _scored_repo("acme/mid", "2024-01-01T00:00:00Z", lma=1)
    freshest = _scored_repo("acme/new", "2025-01-01T00:00:00Z", lma=1)
    pool = [most_stale, mid, freshest]

    _apply_pool_relative_lma(pool)

    # Rank-based credit: freshest -> ceiling, mid -> midpoint, most stale -> base.
    assert freshest.lma_score == 12
    assert mid.lma_score == 7
    assert most_stale.lma_score == 2
    # reliability_score is recomputed from the four pillars.
    assert freshest.reliability_score == 20 + 12 + 10 + 15


def test_pool_relative_lma_never_lowers_a_fresh_repo():
    fresh = _scored_repo("acme/fresh", "2026-06-10T00:00:00Z", lma=25)
    stale_a = _scored_repo("acme/s1", "2024-01-01T00:00:00Z", lma=1)
    stale_b = _scored_repo("acme/s2", "2023-01-01T00:00:00Z", lma=1)
    before = fresh.reliability_score

    _apply_pool_relative_lma([fresh, stale_a, stale_b])

    assert fresh.lma_score == 25  # rank credit (12) < absolute (25) -> unchanged
    assert fresh.reliability_score == before
    assert stale_a.lma_score > 1  # stale repos still get lifted


def test_pool_relative_lma_noop_for_small_pool():
    a = _scored_repo("acme/a", "2023-01-01T00:00:00Z", lma=1)
    b = _scored_repo("acme/b", "2024-01-01T00:00:00Z", lma=1)

    _apply_pool_relative_lma([a, b])

    assert a.lma_score == 1
    assert b.lma_score == 1


def test_pool_relative_lma_ties_share_credit():
    a = _scored_repo("acme/a", "2023-01-01T00:00:00Z", lma=1)
    b = _scored_repo("acme/b", "2023-01-01T00:00:00Z", lma=1)
    c = _scored_repo("acme/c", "2025-01-01T00:00:00Z", lma=1)

    _apply_pool_relative_lma([a, b, c])

    # a and b share the same recency -> identical credit.
    assert a.lma_score == b.lma_score
    assert c.lma_score == 12  # freshest of the three


# --- A-RS2: Pillar 1 weight migration to verified "time" signals -------------

def _repo(**overrides) -> GitRepository:
    base = dict(full_name="acme/x", html_url="https://github.com/acme/x")
    base.update(overrides)
    return GitRepository(**base)


def test_release_cadence_tiers():
    assert _release_cadence_score(_repo(release_count=0)) == 0
    assert _release_cadence_score(_repo(release_count=1)) == 2
    assert _release_cadence_score(_repo(release_count=3)) == 4
    assert _release_cadence_score(_repo(release_count=6)) == 6


def test_ci_health_tiers():
    assert _ci_health_score(_repo(ci_runs_sampled=0)) == 0
    assert _ci_health_score(_repo(ci_runs_sampled=10, ci_recent_success=10)) == 6
    assert _ci_health_score(_repo(ci_runs_sampled=10, ci_recent_success=6)) == 4
    assert _ci_health_score(_repo(ci_runs_sampled=10, ci_recent_success=2)) == 3


def test_verified_maturity_is_cadence_plus_ci():
    repo = _repo(release_count=6, ci_runs_sampled=10, ci_recent_success=10)
    assert _verified_maturity_score(repo) == 12


_STRONG_README = (
    "# Tool\ninstall\nusage\nsetup\nwhy this matters\nroadmap\n"
    "```py\na\n```\n```py\nb\n```\n```py\nc\n```"
)


def test_rich_signals_migrate_weight_off_readme():
    # A strong README alone reaches the Pillar 1 ceiling (30) in legacy mode.
    plain = _repo(readme_text=_STRONG_README)
    _apply_reliability(_theme(), plain)
    assert plain.impl_doc_score == 30
    assert plain.verified_maturity_score == 0

    # With rich signals enabled but no releases/CI, README is down-weighted and
    # cannot reach the old ceiling: this is the vibe-coding inflation case.
    rich = _repo(readme_text=_STRONG_README, has_rich_signals=True)
    _apply_reliability(_theme(), rich)
    assert rich.impl_doc_score < plain.impl_doc_score
    assert rich.verified_maturity_score == 0


def test_rich_signals_credit_releases_and_ci():
    rich = _repo(
        readme_text="# t",
        has_rich_signals=True,
        release_count=6,
        ci_runs_sampled=10,
        ci_recent_success=10,
    )
    _apply_reliability(_theme(), rich)
    assert rich.verified_maturity_score == 12
    assert rich.impl_doc_score >= 12  # verified maturity alone contributes 12


def test_resolve_rich_signals_explicit_override():
    assert _resolve_rich_signals(GitCollectConfig(include_rich_signals=True), _FakeGitHubClient()) is True
    assert _resolve_rich_signals(GitCollectConfig(include_rich_signals=False), _FakeGitHubClient()) is False


def test_resolve_rich_signals_auto_requires_token():
    # _FakeGitHubClient has no .config -> treated as unauthenticated.
    assert _resolve_rich_signals(GitCollectConfig(), _FakeGitHubClient()) is False


class _SimpleConfig:
    token = "ghp_test"


class _RichGitHubClient(_FakeGitHubClient):
    def __init__(self) -> None:
        super().__init__()
        self.config = _SimpleConfig()

    def get(self, path, params=None):
        if path.endswith("/releases"):
            self.calls.append((path, params))
            return [{"published_at": f"202{i}-01-01T00:00:00Z"} for i in range(6)]
        if path.endswith("/actions/runs"):
            self.calls.append((path, params))
            return {"workflow_runs": [{"conclusion": "success"} for _ in range(8)]}
        return super().get(path, params)


def test_collect_with_rich_signals_exposes_verified_maturity():
    client = _RichGitHubClient()
    repos = collect_track_a_git_repos(
        _theme(),
        config=GitCollectConfig(include_rich_signals=True),
        client=client,
    )
    repo = repos[0]
    assert repo.has_rich_signals is True
    assert repo.release_count == 6
    assert repo.ci_runs_sampled == 8
    assert repo.verified_maturity_score == 12  # 6 cadence + 6 ci (8/8 success)

    work = repository_to_work(repo)
    assert work.source_meta["has_rich_signals"] is True
    assert work.source_meta["verified_maturity_score"] == 12
    assert work.source_meta["release_count"] == 6


# --- A-RS2 follow-up: "third-party" (people) signals -------------------------

def test_third_party_score_tiers():
    assert _third_party_score(_repo()) == 0
    assert _third_party_score(_repo(external_contributor_count=1)) == 1
    assert _third_party_score(_repo(external_contributor_count=8)) == 3
    assert _third_party_score(_repo(non_owner_issue_reporters=5)) == 3
    # Both classes combine up to the cap.
    assert _third_party_score(
        _repo(external_contributor_count=8, non_owner_issue_reporters=5)
    ) == 6


def test_third_party_contributes_to_pillar_one_in_rich_mode():
    rich = _repo(
        readme_text="# t",
        has_rich_signals=True,
        external_contributor_count=8,
        non_owner_issue_reporters=5,
    )
    _apply_reliability(_theme(), rich)
    assert rich.third_party_score == 6
    assert rich.impl_doc_score >= 6


class _PeopleGitHubClient(_FakeGitHubClient):
    def __init__(self) -> None:
        super().__init__()
        self.config = _SimpleConfig()

    def get(self, path, params=None):
        if path == "/search/repositories":
            payload = super().get(path, params)
            payload["items"][0]["owner"] = {"login": "acme"}
            return payload
        if path.endswith("/issues"):
            self.calls.append((path, params))
            return [
                {"state": "open", "body": "bug", "user": {"login": "alice"}, "labels": []},
                {"state": "closed", "body": "fix", "user": {"login": "bob"}, "labels": []},
                {"state": "closed", "body": "dup", "user": {"login": "acme"}, "labels": []},
            ]
        if path.endswith("/releases"):
            self.calls.append((path, params))
            return [{"published_at": "2026-01-01T00:00:00Z"}]
        if path.endswith("/actions/runs"):
            self.calls.append((path, params))
            return {"workflow_runs": []}
        if path.endswith("/contributors"):
            self.calls.append((path, params))
            return [
                {"login": "acme"},  # owner -> excluded
                {"login": "alice"},
                {"login": "bob"},
                {"login": "carol"},
            ]
        return super().get(path, params)


def test_collect_counts_external_people_signals():
    client = _PeopleGitHubClient()
    repos = collect_track_a_git_repos(
        _theme(),
        config=GitCollectConfig(include_rich_signals=True),
        client=client,
    )
    repo = repos[0]
    assert repo.owner_login == "acme"
    assert repo.external_contributor_count == 3  # alice, bob, carol (owner excluded)
    assert repo.non_owner_issue_reporters == 2  # alice, bob (owner's issue excluded)
    assert repo.third_party_score == 3  # contributors>=3 (2) + reporters>=1 (1)

    work = repository_to_work(repo)
    assert work.source_meta["third_party_score"] == 3
    assert work.source_meta["external_contributor_count"] == 3
    assert work.source_meta["non_owner_issue_reporters"] == 2
