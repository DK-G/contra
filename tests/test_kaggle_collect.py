"""Tests for Track A Kaggle practical-anchor collection."""

from __future__ import annotations

from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.kaggle_collect import (
    KaggleCollectConfig,
    _dataset_adoption_score,
    _activity_score,
    _kernel_adoption_score,
    _license_score,
    _tag_names,
    build_kaggle_query,
    collect_track_a_kaggle_works,
)


def _theme(include=None, exclude=None, field="machine learning", goal="detect things") -> ThemeInput:
    # `include=[]` must stay empty (don't fall back to a default) so the query-fallback
    # path is exercised; only `None` means "use the default keyword".
    return ThemeInput(
        theme_overview="Recognize mahjong tiles from game screenshots.",
        goal=goal,
        why_problem="Fixed-font score cells are hard to OCR.",
        approach_type="application",
        assumptions=[],
        scope=Scope(field=field, scale="small", time_range="recent"),
        keywords=Keywords(
            include=["mahjong"] if include is None else include,
            exclude=[] if exclude is None else exclude,
        ),
    )


class _FakeKaggleClient:
    def __init__(self, datasets=None, kernels=None, fail=False, has_credentials=True) -> None:
        self.config = type("C", (), {"base_url": "https://www.kaggle.com/api/v1"})()
        self._datasets = datasets or []
        self._kernels = kernels or []
        self._fail = fail
        self.has_credentials = has_credentials
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        if self._fail:
            raise RuntimeError("kaggle down")
        if path == "/datasets/list":
            return self._datasets
        if path == "/kernels/list":
            return self._kernels
        return []


# --- query / helpers --------------------------------------------------------

def test_build_kaggle_query_prefers_first_include_keyword():
    assert build_kaggle_query(_theme(include=["mahjong", "riichi"])) == "mahjong"


def test_build_kaggle_query_falls_back_to_field_then_goal():
    assert build_kaggle_query(_theme(include=[], field="computer vision")) == "computer vision"
    assert build_kaggle_query(_theme(include=[], field="", goal="tile detection")) == "tile detection"


def test_tag_names_handles_dicts_and_strings():
    assert _tag_names({"tags": [{"name": "cv"}, {"fullPath": "image"}, "raw"]}) == ["cv", "image", "raw"]
    assert _tag_names({}) == []


def test_scores_are_monotonic_and_bounded():
    assert _dataset_adoption_score(200_000, 2000, 1.0) > _dataset_adoption_score(50, 5, 0.2)
    assert _dataset_adoption_score(0, 0, 0.0) == 0
    assert _dataset_adoption_score(10_000_000, 100_000, 1.0) <= 40
    assert _kernel_adoption_score(1000, "gold") > _kernel_adoption_score(2, "")
    assert _kernel_adoption_score(1000, "gold") <= 40
    assert _activity_score("") == 0
    assert _license_score("mit") == 15
    assert _license_score("other") == 7
    assert _license_score("") == 0


def test_kernel_medal_boosts_adoption():
    assert _kernel_adoption_score(50, "gold") > _kernel_adoption_score(50, "")


# --- collection -------------------------------------------------------------

def _dataset(ref, downloads, votes, usability=0.8, last_updated="2026-06-01T00:00:00Z",
             license_name="CC0-1.0", tags=None):
    return {
        "ref": ref,
        "title": ref.split("/")[-1],
        "subtitle": "mahjong tiles dataset",
        "downloadCount": downloads,
        "voteCount": votes,
        "usabilityRating": usability,
        "licenseName": license_name,
        "lastUpdated": last_updated,
        "tags": tags if tags is not None else [{"name": "mahjong"}, {"name": "computer vision"}],
    }


def _kernel(ref, votes, medal="", last_run="2026-06-01T00:00:00Z", language="Python"):
    return {
        "ref": ref,
        "title": ref.split("/")[-1],
        "author": ref.split("/")[0],
        "totalVotes": votes,
        "medal": medal,
        "lastRunTime": last_run,
        "languageName": language,
    }


def test_collect_returns_ranked_work_objects_for_datasets_and_kernels():
    client = _FakeKaggleClient(
        datasets=[
            _dataset("user/strong", 50_000, 800),
            _dataset("user/weak", 5, 0, usability=0.1,
                     last_updated="2019-01-01T00:00:00Z", license_name=""),
        ],
        kernels=[_kernel("user/mahjong-eda", 300, medal="gold")],
    )
    works = collect_track_a_kaggle_works(_theme(), KaggleCollectConfig(), client=client)
    assert len(works) == 3
    scores = [w.source_meta["reliability_score"] for w in works]
    assert scores == sorted(scores, reverse=True)
    by_title = {w.title: w for w in works}
    # dataset routing → url + publication_type
    strong = by_title["user/strong"]
    assert strong.publication_type == "kaggle_dataset"
    assert strong.id == "https://www.kaggle.com/datasets/user/strong"
    assert strong.venue == "Kaggle"
    # the strong, recent, licensed dataset outranks the stale unlicensed one
    assert strong.source_meta["reliability_score"] > by_title["user/weak"].source_meta["reliability_score"]
    # kernel routing → /code/ url + publication_type
    kernel = by_title["user/mahjong-eda"]
    assert kernel.publication_type == "kaggle_kernel"
    assert kernel.id == "https://www.kaggle.com/code/user/mahjong-eda"
    assert kernel.source_meta["medal"] == "gold"


def test_collect_theme_fit_rewards_include_keyword():
    client = _FakeKaggleClient(datasets=[_dataset("user/mahjong-tiles", 100, 5)], kernels=[])
    works = collect_track_a_kaggle_works(_theme(include=["mahjong"]), client=client)
    assert works[0].source_meta["theme_fit_score"] > 0


def test_collect_skips_when_no_credentials():
    client = _FakeKaggleClient(datasets=[_dataset("user/d", 100, 5)], has_credentials=False)
    works = collect_track_a_kaggle_works(_theme(), client=client)
    assert works == []
    assert client.calls == []  # never queried the API


def test_collect_respects_max_works_cap():
    client = _FakeKaggleClient(
        datasets=[_dataset(f"user/d{i}", 1000 * i, i) for i in range(1, 8)],
        kernels=[],
    )
    works = collect_track_a_kaggle_works(_theme(), KaggleCollectConfig(max_works=3), client=client)
    assert len(works) == 3


def test_collect_can_limit_to_kernels_only():
    client = _FakeKaggleClient(datasets=[_dataset("user/d", 100, 5)], kernels=[_kernel("user/k", 20)])
    works = collect_track_a_kaggle_works(
        _theme(), KaggleCollectConfig(include_datasets=False), client=client
    )
    assert all(w.publication_type == "kaggle_kernel" for w in works)
    assert ("/datasets/list", {"search": "mahjong", "sortBy": "votes"}) not in client.calls


def test_collect_empty_query_returns_empty():
    client = _FakeKaggleClient(datasets=[_dataset("user/d", 100, 5)])
    works = collect_track_a_kaggle_works(_theme(include=[], field="", goal=""), client=client)
    assert works == []
    assert client.calls == []
