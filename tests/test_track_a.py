"""Tests for the unified Track A collector (github + huggingface merge)."""

from __future__ import annotations

from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.git_collect import GitCollectConfig
from src.pipeline.hf_collect import HFCollectConfig
from src.pipeline.track_a import (
    DEFAULT_SOURCES,
    collect_track_a_works,
    normalize_sources,
)


def _theme() -> ThemeInput:
    return ThemeInput(
        theme_overview="Recognize mahjong tiles from screenshots.",
        goal="detect tiles",
        why_problem="fixed-font cells are hard to OCR",
        approach_type="application",
        assumptions=[],
        scope=Scope(field="computer vision", scale="small", time_range="recent"),
        keywords=Keywords(include=["mahjong"], exclude=[]),
    )


class _FakeGH:
    def __init__(self, items=None, fail=False) -> None:
        self.items = items or []
        self.fail = fail
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(path)
        if self.fail:
            raise RuntimeError("github down")
        if path == "/search/repositories":
            return {"items": self.items}
        return {}


class _FakeHF:
    def __init__(self, models=None, fail=False) -> None:
        self.config = type("C", (), {"base_url": "https://huggingface.co"})()
        self.models = models or []
        self.fail = fail
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(path)
        if self.fail:
            raise RuntimeError("hub down")
        if path == "/api/models":
            return self.models
        return []

    def get_text(self, path, params=None):
        return ""


def _repo(full_name="acme/mahjong-cv", stars=300):
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "owner": {"login": full_name.split("/")[0]},
        "description": "mahjong tile detection",
        "stargazers_count": stars,
        "forks_count": 20,
        "watchers_count": stars,
        "open_issues_count": 3,
        "license": {"spdx_id": "MIT"},
        "default_branch": "main",
        "updated_at": "2026-05-01T00:00:00Z",
        "pushed_at": "2026-05-01T00:00:00Z",
        "topics": ["mahjong", "object-detection"],
    }


def _model(id_="user/mahjong-detector", downloads=5000, likes=60):
    return {
        "id": id_,
        "downloads": downloads,
        "likes": likes,
        "lastModified": "2026-06-01T00:00:00.000Z",
        "createdAt": "2024-01-01T00:00:00.000Z",
        "tags": ["license:apache-2.0", "object-detection"],
        "pipeline_tag": "object-detection",
        "library_name": "transformers",
    }


def _no_rich_github_cfg() -> GitCollectConfig:
    # Only hit /search/repositories so the fake client stays trivial.
    return GitCollectConfig(include_readme=False, include_issues=False, include_rich_signals=False)


# --- normalize_sources ------------------------------------------------------

def test_normalize_sources_aliases_and_dedupe():
    assert normalize_sources(["hf", "huggingface", "gh"]) == ["huggingface", "github"]
    assert normalize_sources(["github", "github"]) == ["github"]


def test_normalize_sources_empty_or_unknown_falls_back_to_all():
    assert normalize_sources([]) == list(DEFAULT_SOURCES)
    assert normalize_sources(None) == list(DEFAULT_SOURCES)
    assert normalize_sources(["bogus"]) == list(DEFAULT_SOURCES)


# --- merge ------------------------------------------------------------------

def test_collect_merges_both_sources_sorted_by_reliability():
    works = collect_track_a_works(
        _theme(),
        sources=["github", "huggingface"],
        git_config=_no_rich_github_cfg(),
        hf_config=HFCollectConfig(include_card=False, include_datasets=False),
        github_client=_FakeGH(items=[_repo()]),
        hf_client=_FakeHF(models=[_model()]),
    )
    types = {w.publication_type for w in works}
    assert "github_repository" in types
    assert "huggingface_model" in types
    scores = [w.source_meta.get("reliability_score", 0) for w in works]
    assert scores == sorted(scores, reverse=True)


def test_collect_single_source_only_hits_that_source():
    gh = _FakeGH(items=[_repo()])
    hf = _FakeHF(models=[_model()])
    works = collect_track_a_works(
        _theme(),
        sources=["huggingface"],
        git_config=_no_rich_github_cfg(),
        hf_config=HFCollectConfig(include_card=False, include_datasets=False),
        github_client=gh,
        hf_client=hf,
    )
    assert gh.calls == []  # github not queried
    assert all(w.publication_type == "huggingface_model" for w in works)


# --- per-source failure isolation -------------------------------------------

def test_github_failure_still_returns_huggingface_anchors():
    errors = []
    works = collect_track_a_works(
        _theme(),
        sources=["github", "huggingface"],
        git_config=_no_rich_github_cfg(),
        hf_config=HFCollectConfig(include_card=False, include_datasets=False),
        github_client=_FakeGH(fail=True),
        hf_client=_FakeHF(models=[_model()]),
        on_error=lambda src, exc: errors.append(src),
    )
    assert errors == ["github"]
    assert works and all(w.publication_type == "huggingface_model" for w in works)


def test_huggingface_failure_still_returns_github_anchors():
    errors = []
    works = collect_track_a_works(
        _theme(),
        sources=["github", "huggingface"],
        git_config=_no_rich_github_cfg(),
        hf_config=HFCollectConfig(include_card=False),
        github_client=_FakeGH(items=[_repo()]),
        hf_client=_FakeHF(fail=True),
        on_error=lambda src, exc: errors.append(src),
    )
    assert errors == ["huggingface"]
    assert works and all(w.publication_type == "github_repository" for w in works)
