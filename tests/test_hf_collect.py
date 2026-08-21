"""Tests for Track A Hugging Face Hub practical-anchor collection."""

from __future__ import annotations

from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.hf_collect import (
    HFCollectConfig,
    _adoption_score,
    _activity_score,
    _extract_license,
    _license_score,
    _strip_card_frontmatter,
    build_hf_query,
    collect_track_a_hf_works,
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


class _FakeHFClient:
    def __init__(self, models=None, datasets=None, cards=None, fail=False) -> None:
        self.config = type("C", (), {"base_url": "https://huggingface.co"})()
        self._models = models or []
        self._datasets = datasets or []
        self._cards = cards or {}
        self._fail = fail
        self.calls = []
        self.text_calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        if self._fail:
            raise RuntimeError("hub down")
        if path == "/api/models":
            return self._models
        if path == "/api/datasets":
            return self._datasets
        return []

    def get_text(self, path, params=None):
        self.text_calls.append(path)
        return self._cards.get(path, "")


# --- query / helpers --------------------------------------------------------

def test_build_hf_query_prefers_first_include_keyword():
    assert build_hf_query(_theme(include=["mahjong", "riichi"])) == "mahjong"


def test_build_hf_query_falls_back_to_field_then_goal():
    assert build_hf_query(_theme(include=[], field="computer vision")) == "computer vision"
    assert build_hf_query(_theme(include=[], field="", goal="tile detection")) == "tile detection"


def test_extract_license_reads_license_tag():
    assert _extract_license(["pytorch", "license:apache-2.0", "object-detection"]) == "apache-2.0"
    assert _extract_license(["pytorch"]) == ""


def test_strip_card_frontmatter_removes_yaml_block():
    card = "---\nlicense: mit\ntags:\n- vision\n---\n\n# Model\nDetects mahjong tiles."
    body = _strip_card_frontmatter(card)
    assert body.startswith("# Model")
    assert "license: mit" not in body


def test_adoption_and_activity_scores_are_monotonic():
    assert _adoption_score(200_000, 2000) > _adoption_score(50, 5)
    assert _adoption_score(0, 0) == 0
    assert _activity_score("") == 0
    # license scoring distinguishes explicit vs other/unknown vs absent
    assert _license_score("mit") == 15
    assert _license_score("other") == 7
    assert _license_score("") == 0


# --- collection -------------------------------------------------------------

def _model(id_, downloads, likes, last_modified="2026-06-01T00:00:00.000Z", tags=None, pipeline="object-detection"):
    return {
        "id": id_,
        "downloads": downloads,
        "likes": likes,
        "lastModified": last_modified,
        "createdAt": "2024-01-01T00:00:00.000Z",
        "tags": tags if tags is not None else ["license:mit", "pytorch", "object-detection"],
        "pipeline_tag": pipeline,
        "library_name": "transformers",
    }


def test_collect_returns_ranked_work_objects_for_models_and_datasets():
    client = _FakeHFClient(
        models=[
            _model("user/strong", 50_000, 800),
            _model("user/weak", 5, 0, last_modified="2019-01-01T00:00:00.000Z", tags=["pytorch"]),
        ],
        datasets=[_model("user/mahjong-dataset", 2000, 30, tags=["license:cc-by-4.0"])],
    )
    works = collect_track_a_hf_works(_theme(), HFCollectConfig(include_card=False), client=client)
    assert len(works) == 3
    # ranked by reliability_score desc
    scores = [w.source_meta["reliability_score"] for w in works]
    assert scores == sorted(scores, reverse=True)
    # the strong, recent, licensed model outranks the stale unlicensed one
    assert works[0].title == "user/strong"
    # model vs dataset routing in url + publication_type
    by_title = {w.title: w for w in works}
    assert by_title["user/strong"].publication_type == "huggingface_model"
    assert by_title["user/strong"].id == "https://huggingface.co/user/strong"
    dataset = by_title["user/mahjong-dataset"]
    assert dataset.publication_type == "huggingface_dataset"
    assert dataset.id == "https://huggingface.co/datasets/user/mahjong-dataset"
    assert dataset.venue == "HuggingFace"
    assert dataset.source_meta["license_name"] == "cc-by-4.0"


def test_collect_uses_card_as_abstract_and_theme_fit():
    card_path = "/user/m/raw/main/README.md"
    client = _FakeHFClient(
        models=[_model("user/m", 100, 5)],
        datasets=[],
        cards={card_path: "---\nlicense: mit\n---\n# Mahjong\nDetects mahjong tiles and hands."},
    )
    works = collect_track_a_hf_works(
        _theme(include=["mahjong"]), HFCollectConfig(include_datasets=False), client=client
    )
    assert works[0].abstract.startswith("# Mahjong")
    assert works[0].source_meta["theme_fit_score"] > 0  # "mahjong" present in card
    assert card_path in client.text_calls


def test_collect_skips_card_fetch_when_disabled():
    client = _FakeHFClient(models=[_model("user/m", 100, 5)], datasets=[])
    collect_track_a_hf_works(
        _theme(), HFCollectConfig(include_card=False, include_datasets=False), client=client
    )
    assert client.text_calls == []


def test_collect_respects_max_works_cap():
    client = _FakeHFClient(
        models=[_model(f"user/m{i}", 1000 * i, i) for i in range(1, 8)],
        datasets=[],
    )
    works = collect_track_a_hf_works(
        _theme(), HFCollectConfig(include_card=False, include_datasets=False, max_works=3), client=client
    )
    assert len(works) == 3


def test_collect_empty_query_returns_empty():
    client = _FakeHFClient(models=[_model("user/m", 100, 5)])
    works = collect_track_a_hf_works(
        _theme(include=[], field="", goal=""), HFCollectConfig(), client=client
    )
    assert works == []
    assert client.calls == []


# --- F-03 (2026-08-22): card fit is density-normalised, not prefix-truncated ---

from src.core.models import Keywords, Scope
from src.pipeline.hf_collect import _theme_fit_score as _hf_fit


def _kw_theme(*include):
    return ThemeInput(
        theme_overview="o", goal="g", why_problem="w", approach_type="application",
        assumptions=[], scope=Scope(field="statistics", scale="small", time_range="last_10_years"),
        keywords=Keywords(include=list(include), exclude=[]),
    )


def test_hf_fit_mention_below_2000_chars_now_counts():
    # The old [:2000] prefix cut missed this mention entirely.
    card = ("x" * 5000) + " anytime-valid inference " + ("y" * 1000)
    assert _hf_fit(_kw_theme("anytime-valid"), "some/model tags", card) == 7


def test_hf_fit_mega_card_scattered_mentions_earn_partial_credit_only():
    chunk = "z" * 40_000
    card = chunk + " e-value " + chunk + " e-value " + chunk
    fit = _hf_fit(_kw_theme("e-value"), "some/model", card)
    assert 0 <= fit <= 2      # 2 hits / 120KB ~= 0.17 credit, not a full 7


def test_hf_fit_strong_field_hit_is_full_credit():
    assert _hf_fit(_kw_theme("sprt"), "acme/sprt-toolkit tags", "q" * 100_000) == 7
