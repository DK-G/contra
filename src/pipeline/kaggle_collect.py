"""Track A practical-anchor collection from Kaggle.

A swappable sibling of :mod:`src.pipeline.git_collect` and :mod:`src.pipeline.hf_collect`.
Where the GitHub collector ranks repositories by a 4-pillar reliability score and the
Hugging Face one ranks Hub models/datasets, this one ranks Kaggle **datasets and
notebooks (kernels)** by Kaggle-native signals (votes, downloads, usability, medals,
recency, license) normalised onto the same 0-100 ``reliability_score`` stored in
``Work.source_meta`` — so Kaggle, HF and GitHub anchors merge and rank together in
:func:`src.pipeline.track_a.collect_track_a_works`.

Kaggle notebooks are the differentiated value here: runnable EDA/baselines that show
"how people actually approached the problem" (including failure patterns) — the kind of
practical foothold neither a GitHub repo nor a Hub card captures.

The Kaggle API needs credentials even for public reads, so collection **silently skips**
(returns ``[]``) when no credentials are configured; see :class:`src.kaggle.client.KaggleClient`.

Reliability pillars (total capped at 100):
- adoption   (max 40): datasets → downloads + votes + usability; kernels → votes + medal
- activity   (max 25): days since last update / last run
- license    (max 15): datasets → an explicit license; kernels → a known language
- theme_fit  (max 20): include-keyword hits in ref/title/subtitle/tags (minus excludes)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import ThemeInput, Work

# kind constants — also the suffix of publication_type ("kaggle_<kind>")
KIND_DATASET = "dataset"
KIND_KERNEL = "kernel"

_MEDAL_POINTS = {"gold": 12, "silver": 8, "bronze": 4, "1": 12, "2": 8, "3": 4}


@dataclass
class KaggleCollectConfig:
    limit: int = 10               # how many hits to keep per kind from the list endpoint
    max_works: int = 5            # cap on returned works after merge+rank
    include_datasets: bool = True
    include_kernels: bool = True


def build_kaggle_query(theme: ThemeInput) -> str:
    """The Kaggle ``search`` param is a single fuzzy string.

    Like the GitHub/HF query builders, use the first include keyword, falling back to
    the scope field then the goal (too many AND-ed terms returns 0 hits).
    """
    if theme.keywords.include:
        return theme.keywords.include[0].strip()
    if theme.scope.field:
        return theme.scope.field.strip()
    return (theme.goal or "").strip()


def _ref(item: Dict[str, Any]) -> str:
    return str(item.get("ref") or item.get("id") or "")


def _tag_names(item: Dict[str, Any]) -> List[str]:
    """Kaggle tags are dicts ({name/ref/fullPath}); reduce to display strings."""
    names: List[str] = []
    for tag in item.get("tags") or []:
        if isinstance(tag, dict):
            name = tag.get("name") or tag.get("fullPath") or tag.get("ref")
            if name:
                names.append(str(name))
        elif tag:
            names.append(str(tag))
    return names


def _year(*iso_values: str) -> int:
    for value in iso_values:
        if not value:
            continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).year
        except ValueError:
            continue
    return 0


def _days_since(iso_value: str) -> Optional[int]:
    if not iso_value:
        return None
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max((datetime.now(dt.tzinfo) - dt).days, 0)


def _dataset_adoption_score(downloads: int, votes: int, usability: float) -> int:
    if downloads >= 100_000:
        dl = 22
    elif downloads >= 10_000:
        dl = 18
    elif downloads >= 1_000:
        dl = 12
    elif downloads >= 100:
        dl = 7
    elif downloads >= 10:
        dl = 3
    elif downloads > 0:
        dl = 1
    else:
        dl = 0
    if votes >= 1_000:
        vt = 12
    elif votes >= 200:
        vt = 9
    elif votes >= 50:
        vt = 6
    elif votes >= 10:
        vt = 3
    elif votes > 0:
        vt = 1
    else:
        vt = 0
    # usabilityRating is a 0.0-1.0 quality signal Kaggle computes for datasets.
    us = int(round(max(min(usability, 1.0), 0.0) * 6))
    return min(dl + vt + us, 40)


def _kernel_adoption_score(votes: int, medal: str) -> int:
    if votes >= 500:
        vt = 28
    elif votes >= 100:
        vt = 22
    elif votes >= 30:
        vt = 15
    elif votes >= 10:
        vt = 9
    elif votes >= 3:
        vt = 4
    elif votes > 0:
        vt = 1
    else:
        vt = 0
    md = _MEDAL_POINTS.get(medal.strip().lower(), 0) if medal else 0
    return min(vt + md, 40)


def _activity_score(last_active: str) -> int:
    days = _days_since(last_active)
    if days is None:
        return 0
    if days <= 30:
        return 25
    if days <= 90:
        return 20
    if days <= 180:
        return 14
    if days <= 365:
        return 8
    return 2


def _license_score(license_name: str) -> int:
    name = license_name.strip().lower()
    if not name:
        return 0
    if name in {"other", "unknown", "unspecified"}:
        return 7
    return 15


def _theme_fit_score(theme: ThemeInput, text: str) -> int:
    haystack = text.lower()
    include_hits = sum(
        1 for token in theme.keywords.include if token and token.lower() in haystack
    )
    exclude_hits = sum(
        1 for token in theme.keywords.exclude if token and token.lower() in haystack
    )
    return max(min(include_hits * 7, 20) - min(exclude_hits * 7, 14), 0)


def _html_url(base_url: str, ref: str, kind: str) -> str:
    site = base_url.split("/api/", 1)[0] or "https://www.kaggle.com"
    path = "datasets" if kind == KIND_DATASET else "code"
    return f"{site}/{path}/{ref}"


def _normalize_dataset(item: Dict[str, Any], theme: ThemeInput, *, base_url: str) -> Work:
    ref = _ref(item)
    title = str(item.get("title") or "")
    subtitle = str(item.get("subtitle") or "")
    tags = _tag_names(item)
    downloads = int(item.get("downloadCount") or 0)
    votes = int(item.get("voteCount") or 0)
    try:
        usability = float(item.get("usabilityRating") or 0.0)
    except (TypeError, ValueError):
        usability = 0.0
    license_name = str(item.get("licenseName") or "")
    last_updated = str(item.get("lastUpdated") or "")

    fit_text = " ".join([ref, title, subtitle, " ".join(tags)])
    adoption = _dataset_adoption_score(downloads, votes, usability)
    activity = _activity_score(last_updated)
    license_pts = _license_score(license_name)
    theme_fit = _theme_fit_score(theme, fit_text)
    reliability = min(adoption + activity + license_pts + theme_fit, 100)

    abstract = subtitle or (" · ".join(tags[:8]) if tags else None)

    return Work(
        id=_html_url(base_url, ref, KIND_DATASET),
        title=ref,
        year=_year(last_updated),
        venue="Kaggle",
        doi=None,
        cited_by_count=votes,
        abstract=abstract,
        concepts=tags[:25],
        publication_type=f"kaggle_{KIND_DATASET}",
        source_meta={
            "reliability_score": reliability,
            "kaggle_kind": KIND_DATASET,
            "display_title": title,
            "downloads": downloads,
            "votes": votes,
            "usability_rating": usability,
            "license_name": license_name,
            "last_updated": last_updated,
            "tags": tags,
            "adoption_score": adoption,
            "activity_score": activity,
            "license_score": license_pts,
            "theme_fit_score": theme_fit,
        },
    )


def _normalize_kernel(item: Dict[str, Any], theme: ThemeInput, *, base_url: str) -> Work:
    ref = _ref(item)
    title = str(item.get("title") or "")
    author = str(item.get("author") or "")
    tags = _tag_names(item)
    votes = int(item.get("totalVotes") or item.get("voteCount") or 0)
    medal = str(item.get("medal") or "")
    language = str(item.get("languageName") or item.get("language") or "")
    last_run = str(item.get("lastRunTime") or "")

    fit_text = " ".join([ref, title, " ".join(tags)])
    adoption = _kernel_adoption_score(votes, medal)
    activity = _activity_score(last_run)
    # kernels rarely expose a license; a known language is the closest "declared metadata"
    # signal, scored on the same 0-15 pillar so kernels and datasets rank comparably.
    language_pts = 15 if language.strip() else 0
    theme_fit = _theme_fit_score(theme, fit_text)
    reliability = min(adoption + activity + language_pts + theme_fit, 100)

    abstract = title or (f"Kaggle notebook by {author}" if author else None)

    return Work(
        id=_html_url(base_url, ref, KIND_KERNEL),
        title=ref,
        year=_year(last_run),
        venue="Kaggle",
        doi=None,
        cited_by_count=votes,
        abstract=abstract,
        concepts=tags[:25],
        publication_type=f"kaggle_{KIND_KERNEL}",
        source_meta={
            "reliability_score": reliability,
            "kaggle_kind": KIND_KERNEL,
            "display_title": title,
            "author": author,
            "votes": votes,
            "medal": medal,
            "language": language,
            "last_run_time": last_run,
            "tags": tags,
            "adoption_score": adoption,
            "activity_score": activity,
            "license_score": language_pts,
            "theme_fit_score": theme_fit,
        },
    )


def _search(client: Any, kind: str, query: str, limit: int) -> List[Dict[str, Any]]:
    if kind == KIND_DATASET:
        endpoint, sort_by = "/datasets/list", "votes"
    else:
        endpoint, sort_by = "/kernels/list", "voteCount"
    payload = client.get(endpoint, {"search": query, "sortBy": sort_by})
    items: List[Any]
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        # Some responses wrap the list; be tolerant.
        wrapped = payload.get("datasets") or payload.get("kernels") or payload.get("items")
        items = wrapped if isinstance(wrapped, list) else []
    else:
        items = []
    return [p for p in items if isinstance(p, dict)][: max(limit, 0)]


def collect_track_a_kaggle_works(
    theme: ThemeInput,
    config: Optional[KaggleCollectConfig] = None,
    client: Optional[Any] = None,
) -> List[Work]:
    """Collect + score Track A practical anchors from Kaggle.

    Returns ``Work`` objects ranked by the Kaggle reliability score (desc), capped at
    ``config.max_works``. Returns ``[]`` immediately when no Kaggle credentials are
    configured (silent skip). Network/HTTP errors propagate to the caller; the unified
    :func:`src.pipeline.track_a.collect_track_a_works` isolates per-source failure.
    """
    cfg = config or KaggleCollectConfig()
    if client is None:
        from src.kaggle.client import KaggleClient

        client = KaggleClient()
    # Kaggle needs credentials even for public reads — skip silently when absent so
    # contra keeps working with no key configured.
    if not getattr(client, "has_credentials", True):
        return []
    base_url = getattr(getattr(client, "config", None), "base_url", "https://www.kaggle.com/api/v1")

    query = build_kaggle_query(theme)
    if not query:
        return []

    works: List[Work] = []
    if cfg.include_datasets:
        for item in _search(client, KIND_DATASET, query, cfg.limit):
            if _ref(item):
                works.append(_normalize_dataset(item, theme, base_url=base_url))
    if cfg.include_kernels:
        for item in _search(client, KIND_KERNEL, query, cfg.limit):
            if _ref(item):
                works.append(_normalize_kernel(item, theme, base_url=base_url))

    works.sort(key=lambda w: w.source_meta.get("reliability_score", 0), reverse=True)
    return works[: max(cfg.max_works, 0)]
