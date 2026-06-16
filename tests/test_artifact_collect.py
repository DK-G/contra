"""Tests for practical artifact collection."""

from __future__ import annotations

from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.artifact_collect import (
    ArtifactCollectConfig,
    collect_datacite_artifacts,
    collect_huggingface_artifacts,
    collect_track_a_artifact_works,
    collect_zenodo_artifacts,
)


def _theme() -> ThemeInput:
    return ThemeInput(
        theme_overview="Evaluate model robustness across hospital imaging domains.",
        goal="Find practical datasets and reusable models.",
        why_problem="Small sample shifts reduce reliability.",
        approach_type="system-building",
        assumptions=[],
        scope=Scope(field="medical imaging", scale="multi-site", time_range="recent"),
        keywords=Keywords(include=["medical imaging", "domain shift"], exclude=[]),
    )


class _FakeHfClient:
    def get(self, path, params=None):
        if path == "/api/models":
            return [
                {
                    "id": "org/med-seg",
                    "downloads": 12000,
                    "likes": 40,
                    "lastModified": "2026-06-01T00:00:00Z",
                    "tags": ["medical-imaging", "segmentation", "paper"],
                    "cardData": {"license": "apache-2.0", "summary": "Segmentation model with evaluation details."},
                }
            ]
        if path == "/api/datasets":
            return []
        if path == "/api/spaces":
            return []
        raise AssertionError(path)


class _FakeZenodoClient:
    def get(self, path, params=None):
        assert path == "/records"
        return {
            "hits": {
                "hits": [
                    {
                        "id": 123,
                        "doi": "10.5281/zenodo.123",
                        "links": {"html": "https://zenodo.org/records/123"},
                        "metadata": {
                            "title": "Medical Imaging Domain Shift Dataset",
                            "description": "<p>Dataset and scripts for domain shift evaluation.</p>",
                            "publication_date": "2026-05-01",
                            "keywords": ["medical imaging", "dataset"],
                            "license": {"id": "cc-by-4.0"},
                            "resource_type": {"title": "Dataset"},
                            "related_identifiers": [{"identifier": "https://github.com/acme/med"}],
                        },
                        "files": [{"key": "data.zip"}],
                        "modified": "2026-05-02T00:00:00Z",
                    }
                ]
            }
        }


class _FakeDataCiteClient:
    def get(self, path, params=None):
        assert path == "/dois"
        return {
            "data": [
                {
                    "id": "10.5281/zenodo.123",
                    "attributes": {
                        "doi": "10.5281/zenodo.123",
                        "titles": [{"title": "Medical Imaging Domain Shift Dataset"}],
                        "descriptions": [{"description": "Duplicate DOI record."}],
                        "publicationYear": 2026,
                        "url": "https://doi.org/10.5281/zenodo.123",
                        "rightsList": [{"rightsIdentifier": "cc-by-4.0"}],
                        "subjects": [{"subject": "medical imaging"}],
                        "types": {"resourceTypeGeneral": "Dataset"},
                    },
                }
            ]
        }


def test_collect_huggingface_artifacts_maps_model_card_signals():
    artifacts = collect_huggingface_artifacts(
        _theme(),
        ArtifactCollectConfig(per_page=5, max_items=3),
        client=_FakeHfClient(),
    )
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.source_type == "hf_model"
    assert artifact.license_name == "apache-2.0"
    assert artifact.reliability_score > 0


def test_collect_zenodo_and_datacite_artifacts_map_doi_metadata():
    zenodo = collect_zenodo_artifacts(
        _theme(),
        ArtifactCollectConfig(per_page=5, max_items=3),
        client=_FakeZenodoClient(),
    )[0]
    datacite = collect_datacite_artifacts(
        _theme(),
        ArtifactCollectConfig(per_page=5, max_items=3),
        client=_FakeDataCiteClient(),
    )[0]
    assert zenodo.source_type == "zenodo_record"
    assert datacite.source_type == "datacite_doi"
    assert zenodo.doi == datacite.doi
    assert zenodo.reliability_score > 0
    assert datacite.reliability_score > 0


def test_collect_track_a_artifact_works_deduplicates_zenodo_datacite_doi():
    works = collect_track_a_artifact_works(
        _theme(),
        ArtifactCollectConfig(per_page=5, max_items=10, include_huggingface=True),
        hf_client=_FakeHfClient(),
        zenodo_client=_FakeZenodoClient(),
        datacite_client=_FakeDataCiteClient(),
    )
    assert len(works) == 2
    assert {work.publication_type for work in works} == {"hf_model", "zenodo_record"}
    assert all(work.source_meta["reliability_score"] > 0 for work in works)
    assert all("problem_solution_fit_score" in work.source_meta for work in works)


def test_collect_track_a_artifact_works_can_use_problem_search_queries():
    works = collect_track_a_artifact_works(
        _theme(),
        ArtifactCollectConfig(per_page=5, max_items=10, include_huggingface=True, use_problem_search=True),
        hf_client=_FakeHfClient(),
        zenodo_client=_FakeZenodoClient(),
        datacite_client=_FakeDataCiteClient(),
    )
    assert works
    assert all(work.source_meta["problem_solution_fit_score"] >= 0 for work in works)


class _RecordingHfClient(_FakeHfClient):
    def __init__(self) -> None:
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params or {}))
        return super().get(path, params)


def test_problem_search_artifacts_collect_across_multiple_intents():
    client = _RecordingHfClient()
    collect_huggingface_artifacts(
        _theme(),
        ArtifactCollectConfig(
            per_page=1,
            max_items=1,
            include_huggingface=True,
            include_zenodo=False,
            include_datacite=False,
            use_problem_search=True,
        ),
        client=client,
    )
    model_queries = [params["search"] for path, params in client.calls if path == "/api/models"]
    assert len(model_queries) > 1
    assert len(set(model_queries)) > 1
