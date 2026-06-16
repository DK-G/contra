"""Track A practical artifact collection for model/data/research outputs."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Any, Dict, List, Optional

from src.core.models import PracticalArtifact, ThemeInput, Work
from src.pipeline.problem_search import (
    ProblemSearchPlan,
    QuerySpec,
    build_plain_query_specs,
    build_problem_search_plan,
    score_problem_solution_fit,
)


class ArtifactApiError(RuntimeError):
    """Raised when an artifact source API request fails."""


@dataclass
class ArtifactCollectConfig:
    per_page: int = 10
    max_items: int = 10
    include_huggingface: bool = True
    include_zenodo: bool = True
    include_datacite: bool = True
    use_problem_search: bool = False


@dataclass
class JsonApiClient:
    base_url: str
    timeout_sec: int = 20
    user_agent: str = "contra-cli/0.1"

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url = f"{url}?{query}"
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": self.user_agent},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ArtifactApiError(f"http {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ArtifactApiError(f"network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ArtifactApiError("invalid json from artifact API") from exc


def build_artifact_query(theme: ThemeInput) -> str:
    if theme.keywords.include:
        return " ".join(theme.keywords.include[:2])
    if theme.scope.field:
        return theme.scope.field
    return theme.goal[:80]


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _year_from_date(value: str) -> int:
    if not value:
        return 0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).year
    except ValueError:
        match = re.search(r"\b(19|20)\d{2}\b", value)
        return int(match.group(0)) if match else 0


def _days_since(value: str) -> Optional[int]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return max((datetime.now(dt.tzinfo) - dt).days, 0)
    except ValueError:
        return None


def _norm_title(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").casefold()).strip()


def _norm_doi(doi: Optional[str]) -> str:
    if not doi:
        return ""
    text = doi.strip().lower()
    text = text.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    return text


def _license_score(license_name: str) -> int:
    if not license_name or license_name.lower() in {"unknown", "other", "none"}:
        return 0
    return 20


def _activity_score(updated_at: str) -> int:
    days = _days_since(updated_at)
    if days is None:
        return 0
    if days <= 30:
        return 15
    if days <= 180:
        return 10
    if days <= 365:
        return 5
    return 1


def _adoption_score(downloads: int, likes: int = 0) -> int:
    score = 0
    if downloads >= 100000:
        score += 15
    elif downloads >= 10000:
        score += 10
    elif downloads >= 1000:
        score += 6
    elif downloads > 0:
        score += 3
    if likes >= 100:
        score += 5
    elif likes >= 10:
        score += 3
    elif likes > 0:
        score += 1
    return min(score, 20)


def _completeness_score(artifact: PracticalArtifact) -> int:
    score = 0
    if artifact.description:
        score += 8
    if artifact.tags:
        score += 5
    if artifact.metadata.get("card_data") or artifact.metadata.get("metadata"):
        score += 7
    if artifact.metadata.get("files") or artifact.metadata.get("resource_type"):
        score += 5
    return min(score, 25)


def _linkage_score(artifact: PracticalArtifact) -> int:
    text = f"{artifact.description} {' '.join(artifact.tags)} {artifact.doi or ''}".lower()
    score = 0
    if artifact.doi:
        score += 8
    if any(signal in text for signal in ("paper", "arxiv", "citation", "benchmark", "dataset")):
        score += 7
    if artifact.metadata.get("related_identifiers") or artifact.metadata.get("relatedIdentifiers"):
        score += 5
    return min(score, 20)


def _risk_penalty(artifact: PracticalArtifact) -> int:
    text = f"{artifact.license_name} {' '.join(artifact.tags)} {artifact.metadata}".lower()
    penalty = 0
    if "gated" in text or artifact.metadata.get("gated"):
        penalty += 8
    if "no license" in text or not artifact.license_name:
        penalty += 5
    if "deprecated" in text or "yanked" in text:
        penalty += 7
    return min(penalty, 20)


def _apply_artifact_reliability(artifact: PracticalArtifact) -> PracticalArtifact:
    artifact.completeness_score = _completeness_score(artifact)
    artifact.activity_score = _activity_score(artifact.updated_at)
    artifact.adoption_score = _adoption_score(artifact.downloads, artifact.likes)
    artifact.license_score = _license_score(artifact.license_name)
    artifact.linkage_score = _linkage_score(artifact)
    artifact.risk_penalty = _risk_penalty(artifact)
    total = (
        artifact.completeness_score
        + artifact.activity_score
        + artifact.adoption_score
        + artifact.license_score
        + artifact.linkage_score
        - artifact.risk_penalty
    )
    artifact.reliability_score = max(min(total, 100), 0)
    return artifact


def _apply_problem_solution_fit(
    theme: ThemeInput,
    artifact: PracticalArtifact,
    plan: Optional[ProblemSearchPlan] = None,
) -> PracticalArtifact:
    fit = score_problem_solution_fit(
        theme,
        text="\n".join([artifact.title, artifact.description]),
        source_type=artifact.source_type,
        tags=artifact.tags,
        metadata_text=json.dumps(artifact.metadata, ensure_ascii=False),
        plan=plan,
    )
    artifact.problem_solution_fit_score = fit.score
    artifact.problem_match_score = fit.problem_score
    artifact.solution_mechanism_score = fit.solution_score
    artifact.execution_evidence_score = fit.execution_score
    artifact.evaluation_evidence_score = fit.evaluation_score
    artifact.constraint_visibility_score = fit.constraint_score
    artifact.matched_problem = fit.matched_problem
    artifact.solution_mechanism = fit.solution_mechanism
    artifact.usable_artifact = fit.usable_artifact
    artifact.visible_constraint = fit.visible_constraint
    return artifact


def _rank_artifacts(artifacts: List[PracticalArtifact], cfg: ArtifactCollectConfig) -> List[PracticalArtifact]:
    ranked = sorted(
        artifacts,
        key=lambda item: (
            item.problem_match_score,
            item.problem_solution_fit_score,
            item.reliability_score,
        ),
        reverse=True,
    )
    if cfg.use_problem_search:
        return [item for item in ranked if item.problem_match_score > 0]
    return ranked


def _query_candidate_budget(limit: int, query_specs: List[QuerySpec], use_problem_search: bool) -> int:
    if not use_problem_search:
        return limit
    return max(limit, limit * max(len(query_specs), 1))


def artifact_to_work(artifact: PracticalArtifact) -> Work:
    source_label = {
        "hf_model": "Hugging Face Model",
        "hf_dataset": "Hugging Face Dataset",
        "hf_space": "Hugging Face Space",
        "zenodo_record": "Zenodo",
        "datacite_doi": "DataCite",
    }.get(artifact.source_type, artifact.source)
    return Work(
        id=artifact.url,
        title=artifact.title,
        year=artifact.year,
        venue=source_label,
        doi=artifact.doi,
        cited_by_count=artifact.downloads or artifact.likes,
        abstract=artifact.description or None,
        concepts=list(artifact.tags),
        publication_type=artifact.source_type,
        source_meta={
            "source_type": artifact.source_type,
            "provider": artifact.source,
            "license_name": artifact.license_name,
            "updated_at": artifact.updated_at,
            "downloads": artifact.downloads,
            "likes": artifact.likes,
            "reliability_score": artifact.reliability_score,
            "completeness_score": artifact.completeness_score,
            "activity_score": artifact.activity_score,
            "adoption_score": artifact.adoption_score,
            "license_score": artifact.license_score,
            "linkage_score": artifact.linkage_score,
            "risk_penalty": artifact.risk_penalty,
            "problem_solution_fit_score": artifact.problem_solution_fit_score,
            "problem_match_score": artifact.problem_match_score,
            "solution_mechanism_score": artifact.solution_mechanism_score,
            "execution_evidence_score": artifact.execution_evidence_score,
            "evaluation_evidence_score": artifact.evaluation_evidence_score,
            "constraint_visibility_score": artifact.constraint_visibility_score,
            "matched_problem": artifact.matched_problem,
            "solution_mechanism": artifact.solution_mechanism,
            "usable_artifact": artifact.usable_artifact,
            "visible_constraint": artifact.visible_constraint,
        },
    )


def _hf_artifact(
    item: dict,
    source_type: str,
    theme: Optional[ThemeInput] = None,
    plan: Optional[ProblemSearchPlan] = None,
) -> PracticalArtifact:
    item_id = str(item.get("id") or item.get("modelId") or item.get("datasetId") or item.get("name") or "")
    base = {
        "hf_model": "https://huggingface.co",
        "hf_dataset": "https://huggingface.co/datasets",
        "hf_space": "https://huggingface.co/spaces",
    }[source_type]
    card = item.get("cardData") or {}
    tags = [str(tag) for tag in (item.get("tags") or []) if tag]
    license_name = str(card.get("license") or item.get("license") or "")
    description = str(card.get("summary") or item.get("description") or item.get("pipeline_tag") or "")
    artifact = _apply_artifact_reliability(
        PracticalArtifact(
            artifact_id=item_id,
            title=item_id,
            url=f"{base}/{item_id}",
            source="huggingface",
            source_type=source_type,
            description=description,
            year=_year_from_date(str(item.get("lastModified") or item.get("createdAt") or "")),
            license_name=license_name,
            downloads=int(item.get("downloads") or 0),
            likes=int(item.get("likes") or 0),
            updated_at=str(item.get("lastModified") or item.get("updatedAt") or ""),
            tags=tags,
            metadata={"card_data": card, "gated": item.get("gated")},
        )
    )
    return _apply_problem_solution_fit(theme, artifact, plan) if theme else artifact


def collect_huggingface_artifacts(
    theme: ThemeInput,
    config: Optional[ArtifactCollectConfig] = None,
    client: Optional[JsonApiClient] = None,
) -> List[PracticalArtifact]:
    cfg = config or ArtifactCollectConfig()
    plan = build_problem_search_plan(theme) if cfg.use_problem_search else None
    hf = client or JsonApiClient("https://huggingface.co")
    queries = build_plain_query_specs("huggingface", theme, plan) if plan else [
        QuerySpec("huggingface", "default", build_artifact_query(theme))
    ]
    candidate_budget = _query_candidate_budget(cfg.max_items, queries, cfg.use_problem_search)
    specs = [
        ("/api/models", "hf_model"),
        ("/api/datasets", "hf_dataset"),
        ("/api/spaces", "hf_space"),
    ]
    artifacts: List[PracticalArtifact] = []
    seen: set[str] = set()
    for query in queries:
        for path, source_type in specs:
            try:
                payload = hf.get(
                    path,
                    {"search": query.query, "sort": "downloads", "direction": -1, "limit": cfg.per_page},
                )
            except ArtifactApiError:
                continue
            items = payload if isinstance(payload, list) else []
            for item in items:
                item_id = str(item.get("id") or item.get("modelId") or item.get("datasetId") or item.get("name") or "")
                key = f"{source_type}:{item_id}"
                if not item_id or key in seen:
                    continue
                seen.add(key)
                artifacts.append(_hf_artifact(item, source_type, theme=theme, plan=plan))
                if len(artifacts) >= candidate_budget:
                    break
            if len(artifacts) >= candidate_budget:
                break
        if len(artifacts) >= candidate_budget:
            break
    return _rank_artifacts(artifacts, cfg)[: cfg.max_items]


def _zenodo_artifact(
    item: dict,
    theme: Optional[ThemeInput] = None,
    plan: Optional[ProblemSearchPlan] = None,
) -> PracticalArtifact:
    metadata = item.get("metadata") or {}
    resource_type = metadata.get("resource_type") or {}
    license_data = metadata.get("license") or {}
    doi = str(item.get("doi") or metadata.get("doi") or "")
    title = str(metadata.get("title") or item.get("title") or "")
    url = str(item.get("links", {}).get("html") or item.get("doi_url") or item.get("conceptdoi") or "")
    if not url and doi:
        url = f"https://doi.org/{doi}"
    description = _strip_html(str(metadata.get("description") or ""))
    tags = [str(t) for t in (metadata.get("keywords") or []) if t]
    files = item.get("files") or []
    artifact = _apply_artifact_reliability(
        PracticalArtifact(
            artifact_id=str(item.get("id") or doi or title),
            title=title,
            url=url,
            source="zenodo",
            source_type="zenodo_record",
            description=description,
            year=_year_from_date(str(metadata.get("publication_date") or item.get("created") or "")),
            license_name=str(license_data.get("id") or license_data.get("title") or ""),
            doi=doi or None,
            downloads=int(item.get("stats", {}).get("downloads") or 0),
            updated_at=str(item.get("modified") or item.get("updated") or item.get("created") or ""),
            tags=tags,
            metadata={
                "resource_type": resource_type.get("title") or resource_type.get("type"),
                "files": files,
                "related_identifiers": metadata.get("related_identifiers") or [],
            },
        )
    )
    return _apply_problem_solution_fit(theme, artifact, plan) if theme else artifact


def collect_zenodo_artifacts(
    theme: ThemeInput,
    config: Optional[ArtifactCollectConfig] = None,
    client: Optional[JsonApiClient] = None,
) -> List[PracticalArtifact]:
    cfg = config or ArtifactCollectConfig()
    plan = build_problem_search_plan(theme) if cfg.use_problem_search else None
    zenodo = client or JsonApiClient("https://zenodo.org/api")
    queries = build_plain_query_specs("zenodo_record", theme, plan) if plan else [
        QuerySpec("zenodo_record", "default", build_artifact_query(theme))
    ]
    candidate_budget = _query_candidate_budget(cfg.max_items, queries, cfg.use_problem_search)
    artifacts: List[PracticalArtifact] = []
    seen: set[str] = set()
    for query in queries:
        payload = zenodo.get(
            "/records",
            {"q": query.query, "size": cfg.per_page, "sort": "bestmatch"},
        )
        items = (payload.get("hits") or {}).get("hits") if isinstance(payload, dict) else []
        for item in items or []:
            key = str(item.get("doi") or item.get("id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            artifacts.append(_zenodo_artifact(item, theme=theme, plan=plan))
            if len(artifacts) >= candidate_budget:
                break
        if len(artifacts) >= candidate_budget:
            break
    return _rank_artifacts(artifacts, cfg)[: cfg.max_items]


def _datacite_artifact(
    item: dict,
    theme: Optional[ThemeInput] = None,
    plan: Optional[ProblemSearchPlan] = None,
) -> PracticalArtifact:
    attrs = item.get("attributes") or {}
    titles = attrs.get("titles") or []
    descriptions = attrs.get("descriptions") or []
    subjects = attrs.get("subjects") or []
    rights = attrs.get("rightsList") or []
    types = attrs.get("types") or {}
    doi = str(attrs.get("doi") or item.get("id") or "")
    title = str((titles[0] or {}).get("title") if titles else doi)
    description = _strip_html(str((descriptions[0] or {}).get("description") if descriptions else ""))
    license_name = str((rights[0] or {}).get("rightsIdentifier") or (rights[0] or {}).get("rights") if rights else "")
    url = str(attrs.get("url") or (f"https://doi.org/{doi}" if doi else ""))
    artifact = _apply_artifact_reliability(
        PracticalArtifact(
            artifact_id=doi or str(item.get("id") or title),
            title=title,
            url=url,
            source="datacite",
            source_type="datacite_doi",
            description=description,
            year=int(attrs.get("publicationYear") or 0),
            license_name=license_name,
            doi=doi or None,
            updated_at=str(attrs.get("updated") or attrs.get("created") or ""),
            tags=[str((s or {}).get("subject")) for s in subjects if (s or {}).get("subject")],
            metadata={
                "resource_type": types.get("resourceTypeGeneral") or types.get("resourceType"),
                "relatedIdentifiers": attrs.get("relatedIdentifiers") or [],
            },
        )
    )
    return _apply_problem_solution_fit(theme, artifact, plan) if theme else artifact


def collect_datacite_artifacts(
    theme: ThemeInput,
    config: Optional[ArtifactCollectConfig] = None,
    client: Optional[JsonApiClient] = None,
) -> List[PracticalArtifact]:
    cfg = config or ArtifactCollectConfig()
    plan = build_problem_search_plan(theme) if cfg.use_problem_search else None
    datacite = client or JsonApiClient("https://api.datacite.org")
    queries = build_plain_query_specs("datacite_doi", theme, plan) if plan else [
        QuerySpec("datacite_doi", "default", build_artifact_query(theme))
    ]
    candidate_budget = _query_candidate_budget(cfg.max_items, queries, cfg.use_problem_search)
    artifacts: List[PracticalArtifact] = []
    seen: set[str] = set()
    seen_titles: set[str] = set()
    for query in queries:
        payload = datacite.get(
            "/dois",
            {"query": query.query, "page[size]": cfg.per_page},
        )
        items = payload.get("data") if isinstance(payload, dict) else []
        for item in items or []:
            attrs = item.get("attributes") or {}
            key = str(attrs.get("doi") or item.get("id") or "")
            titles = attrs.get("titles") or []
            title = _norm_title(str((titles[0] or {}).get("title") if titles else key))
            if not key or key in seen or (title and title in seen_titles):
                continue
            seen.add(key)
            if title:
                seen_titles.add(title)
            artifacts.append(_datacite_artifact(item, theme=theme, plan=plan))
            if len(artifacts) >= candidate_budget:
                break
        if len(artifacts) >= candidate_budget:
            break
    return _rank_artifacts(artifacts, cfg)[: cfg.max_items]


def collect_track_a_artifact_works(
    theme: ThemeInput,
    config: Optional[ArtifactCollectConfig] = None,
    *,
    hf_client: Optional[JsonApiClient] = None,
    zenodo_client: Optional[JsonApiClient] = None,
    datacite_client: Optional[JsonApiClient] = None,
) -> List[Work]:
    cfg = config or ArtifactCollectConfig()
    artifacts: List[PracticalArtifact] = []
    if cfg.include_huggingface:
        try:
            artifacts.extend(collect_huggingface_artifacts(theme, cfg, client=hf_client))
        except ArtifactApiError:
            pass
    if cfg.include_zenodo:
        try:
            artifacts.extend(collect_zenodo_artifacts(theme, cfg, client=zenodo_client))
        except ArtifactApiError:
            pass
    if cfg.include_datacite:
        try:
            artifacts.extend(collect_datacite_artifacts(theme, cfg, client=datacite_client))
        except ArtifactApiError:
            pass

    deduped: List[PracticalArtifact] = []
    seen_dois: set[str] = set()
    seen_titles: set[str] = set()
    seen_urls: set[str] = set()
    for artifact in _rank_artifacts(artifacts, cfg):
        doi = _norm_doi(artifact.doi)
        title = _norm_title(artifact.title)
        url = artifact.url.strip().lower()
        if (doi and doi in seen_dois) or (title and title in seen_titles) or (url and url in seen_urls):
            continue
        if doi:
            seen_dois.add(doi)
        if title:
            seen_titles.add(title)
        if url:
            seen_urls.add(url)
        deduped.append(artifact)
        if len(deduped) >= cfg.max_items:
            break
    return [artifact_to_work(artifact) for artifact in deduped]
