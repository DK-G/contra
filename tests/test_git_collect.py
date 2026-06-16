"""Tests for Track A Git practical-anchor collection."""

from __future__ import annotations

import base64

from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.git_collect import (
    GitCollectConfig,
    _decode_readme,
    build_track_a_git_query,
    build_track_a_gitlab_query,
    collect_track_a_gitlab_repos,
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


def test_build_track_a_gitlab_query_uses_plain_search_terms():
    query = build_track_a_gitlab_query(_theme())
    assert query == "digital twin"
    assert "pushed:" not in query
    assert "in:readme" not in query




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


class _FakeGitLabClient:
    def __init__(self) -> None:
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        if path == "/projects":
            return [
                {
                    "id": 42,
                    "path_with_namespace": "lab/grid-twin",
                    "web_url": "https://gitlab.com/lab/grid-twin",
                    "description": "digital twin grid toolkit",
                    "star_count": 80,
                    "forks_count": 8,
                    "open_issues_count": 2,
                    "license": {"key": "apache-2.0"},
                    "default_branch": "main",
                    "last_activity_at": "2026-06-02T00:00:00Z",
                    "topics": ["digital-twin", "grid"],
                }
            ]
        if path == "/projects/42/issues":
            return [
                {"state": "closed", "body": "documented setup failure", "labels": [{"name": "docs"}]},
            ]
        raise AssertionError(path)

    def get_text(self, path, params=None):
        self.calls.append((path, params))
        if path == "/projects/42/repository/files/README.md/raw":
            return "# Grid Twin\nInstall and usage\n```bash\nrun\n```"
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
    assert "problem_solution_fit_score" in work.source_meta


def test_collect_track_a_gitlab_repos_maps_project_fields():
    client = _FakeGitLabClient()
    repos = collect_track_a_gitlab_repos(
        _theme(),
        config=GitCollectConfig(per_page=5, max_repos=3, include_readme=True),
        client=client,
    )
    assert len(repos) == 1
    repo = repos[0]
    assert repo.provider == "gitlab"
    assert repo.full_name == "lab/grid-twin"
    assert repo.license_name == "apache-2.0"
    assert repo.issue_score > 0
    work = repository_to_work(repo)
    assert work.venue == "GitLab"
    assert work.publication_type == "gitlab_repository"
    assert work.source_meta["provider"] == "gitlab"
    assert "problem_solution_fit_score" in work.source_meta


def test_collect_track_a_git_repos_can_use_problem_search_queries():
    client = _FakeGitHubClient()
    repos = collect_track_a_git_repos(
        _theme(),
        config=GitCollectConfig(per_page=5, max_repos=1, include_readme=True, use_problem_search=True),
        client=client,
    )
    assert len(repos) == 1
    assert repos[0].problem_solution_fit_score >= 0


def test_problem_search_queries_are_not_stopped_by_first_full_page():
    client = _FakeGitHubClient()
    collect_track_a_git_repos(
        _theme(),
        config=GitCollectConfig(
            per_page=1,
            max_repos=1,
            include_readme=False,
            include_issues=False,
            use_problem_search=True,
        ),
        client=client,
    )
    search_calls = [params for path, params in client.calls if path == "/search/repositories"]
    assert len(search_calls) > 1
    assert len({params["q"] for params in search_calls}) > 1


def test_collect_track_a_git_works_returns_work_objects():
    client = _FakeGitHubClient()
    works = collect_track_a_git_works(_theme(), client=client)
    assert len(works) == 1
    assert works[0].publication_type == "github_repository"
