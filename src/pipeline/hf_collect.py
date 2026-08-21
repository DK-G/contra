"""Track A practical-anchor collection from the Hugging Face Hub.

A swappable sibling of :mod:`src.pipeline.git_collect`. Where the GitHub collector
ranks repositories by a 4-pillar reliability score built from stars/forks/issues/CI,
this one ranks Hub **models and datasets** by HF-native signals (downloads, likes,
recency, license, theme-fit) normalised onto the same 0-100 ``reliability_score``
stored in ``Work.source_meta`` — so HF and GitHub anchors merge and rank together in
:func:`src.pipeline.track_a.collect_track_a_works`.

Reliability pillars (total capped at 100):
- adoption  (max 40): downloads (≤25) + likes (≤15)
- activity  (max 25): days since lastModified
- license   (max 15): an explicit, non-"other/unknown" license tag
- theme_fit (max 20): include-keyword hits in id/tags/pipeline_tag/card text
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import ThemeInput, Work
from src.pipeline.git_collect import _README_DENSITY_UNIT, _README_MIN_LEN

# kind constants — also the suffix of publication_type ("huggingface_<kind>")
KIND_MODEL = "model"
KIND_DATASET = "dataset"


@dataclass
class HFCollectConfig:
    limit: int = 10               # how many hits to request per kind from the Hub
    max_works: int = 5            # cap on returned works after merge+rank
    include_models: bool = True
    include_datasets: bool = True
    include_card: bool = True     # fetch the README card for theme-fit / abstract
    card_char_limit: int = 2000


def build_hf_query(theme: ThemeInput) -> str:
    """The Hub ``search`` param is a single fuzzy string matched against the id.

    Too many AND-ed terms returns 0 hits, so (like the GitHub query builder) use the
    first include keyword, falling back to the scope field then the goal.
    """
    if theme.keywords.include:
        return theme.keywords.include[0].strip()
    if theme.scope.field:
        return theme.scope.field.strip()
    return (theme.goal or "").strip()


def _item_id(item: Dict[str, Any]) -> str:
    return str(item.get("id") or item.get("modelId") or item.get("_id") or "")


def _extract_license(tags: List[str]) -> str:
    for tag in tags:
        if isinstance(tag, str) and tag.startswith("license:"):
            return tag.split(":", 1)[1].strip()
    return ""


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


def _strip_card_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block (``---`` … ``---``) from a card README."""
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return text.strip()
    end = stripped.find("\n---", 3)
    if end == -1:
        return text.strip()
    after = stripped[end + 4 :]
    return after.strip()


def _card_path(item_id: str, kind: str) -> str:
    if kind == KIND_DATASET:
        return f"/datasets/{item_id}/raw/main/README.md"
    return f"/{item_id}/raw/main/README.md"


def _html_url(base_url: str, item_id: str, kind: str) -> str:
    if kind == KIND_DATASET:
        return f"{base_url}/datasets/{item_id}"
    return f"{base_url}/{item_id}"


def _adoption_score(downloads: int, likes: int) -> int:
    if downloads >= 100_000:
        dl = 25
    elif downloads >= 10_000:
        dl = 20
    elif downloads >= 1_000:
        dl = 14
    elif downloads >= 100:
        dl = 8
    elif downloads >= 10:
        dl = 4
    elif downloads > 0:
        dl = 1
    else:
        dl = 0
    if likes >= 1_000:
        lk = 15
    elif likes >= 200:
        lk = 12
    elif likes >= 50:
        lk = 8
    elif likes >= 10:
        lk = 4
    elif likes > 0:
        lk = 1
    else:
        lk = 0
    return dl + lk


def _activity_score(last_modified: str) -> int:
    days = _days_since(last_modified)
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
    if name in {"other", "unknown", "unlicense-other"}:
        return 7
    return 15


def _theme_fit_score(theme: ThemeInput, strong_text: str, card_text: str = "") -> int:
    """Keyword fit: id/tags/pipeline/library hits earn full credit; card hits earn
    length-normalised partial credit (occurrences per 10k chars, capped at 1.0).

    Same F-03 fix as the GitHub readme fit: matching a [:2000] card prefix missed
    mentions below the fold, while full-text presence made CARD LENGTH a relevance
    proxy (model cards, like mega-READMEs, mention everything incidentally). The
    density constants are shared with git_collect (calibrated on live probes).
    """
    strong = strong_text.lower()
    card = card_text.lower()
    denom = max(len(card), _README_MIN_LEN) / _README_DENSITY_UNIT

    include_credit = 0.0
    for token in theme.keywords.include:
        t = (token or "").lower()
        if not t:
            continue
        if t in strong:
            include_credit += 1.0
        elif card:
            include_credit += min(card.count(t) / denom, 1.0)
    exclude_hits = sum(
        1 for token in theme.keywords.exclude
        if token and (token.lower() in strong or token.lower() in card)
    )
    return max(min(int(round(include_credit * 7)), 20) - min(exclude_hits * 7, 14), 0)


def _fit_text(item_id: str, tags: List[str], pipeline_tag: str, library: str, card: str = "") -> str:
    return " ".join([item_id, " ".join(tags), pipeline_tag, library, card])


def _normalize_item(
    item: Dict[str, Any],
    kind: str,
    theme: ThemeInput,
    *,
    base_url: str,
    card_text: str = "",
    card_char_limit: int = 2000,
) -> Work:
    item_id = _item_id(item)
    tags = [str(t) for t in (item.get("tags") or []) if t]
    pipeline_tag = str(item.get("pipeline_tag") or "")
    library = str(item.get("library_name") or "")
    downloads = int(item.get("downloads") or item.get("downloadsAllTime") or 0)
    likes = int(item.get("likes") or 0)
    last_modified = str(item.get("lastModified") or "")
    created_at = str(item.get("createdAt") or "")
    license_name = _extract_license(tags)
    gated = item.get("gated")

    full_card = _strip_card_frontmatter(card_text) if card_text else ""
    card = full_card[:card_char_limit]          # truncation stays a DISPLAY concern only
    strong_text = _fit_text(item_id, tags, pipeline_tag, library)

    adoption = _adoption_score(downloads, likes)
    activity = _activity_score(last_modified)
    license_pts = _license_score(license_name)
    theme_fit = _theme_fit_score(theme, strong_text, full_card)
    reliability = min(adoption + activity + license_pts + theme_fit, 100)

    if card:
        abstract = card
    else:
        synth = " · ".join(p for p in [pipeline_tag, library, ", ".join(tags[:8])] if p)
        abstract = synth or None

    return Work(
        id=_html_url(base_url, item_id, kind),
        title=item_id,
        year=_year(created_at, last_modified),
        venue="HuggingFace",
        doi=None,
        cited_by_count=likes,
        abstract=abstract,
        concepts=tags[:25],
        publication_type=f"huggingface_{kind}",
        source_meta={
            "reliability_score": reliability,
            "hf_kind": kind,
            "downloads": downloads,
            "likes": likes,
            "license_name": license_name,
            "last_modified": last_modified,
            "created_at": created_at,
            "pipeline_tag": pipeline_tag,
            "library_name": library,
            "gated": gated,
            "tags": tags,
            "adoption_score": adoption,
            "activity_score": activity,
            "license_score": license_pts,
            "theme_fit_score": theme_fit,
        },
    )


def _search(client: Any, kind: str, query: str, limit: int) -> List[Dict[str, Any]]:
    endpoint = "/api/datasets" if kind == KIND_DATASET else "/api/models"
    payload = client.get(
        endpoint,
        {
            "search": query,
            "sort": "downloads",
            "direction": -1,
            "limit": limit,
            "full": "true",
        },
    )
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    # Some Hub responses wrap the list; be tolerant.
    if isinstance(payload, dict):
        items = payload.get("models") or payload.get("datasets") or payload.get("items")
        if isinstance(items, list):
            return [p for p in items if isinstance(p, dict)]
    return []


def collect_track_a_hf_works(
    theme: ThemeInput,
    config: Optional[HFCollectConfig] = None,
    client: Optional[Any] = None,
) -> List[Work]:
    """Collect + score Track A practical anchors from the Hugging Face Hub.

    Returns ``Work`` objects ranked by the HF reliability score (desc), capped at
    ``config.max_works``. Network/HTTP errors propagate to the caller; the unified
    :func:`src.pipeline.track_a.collect_track_a_works` isolates per-source failure.
    """
    cfg = config or HFCollectConfig()
    if client is None:
        from src.hf.client import HFClient

        client = HFClient()
    base_url = getattr(getattr(client, "config", None), "base_url", "https://huggingface.co")

    query = build_hf_query(theme)
    if not query:
        return []

    kinds: List[str] = []
    if cfg.include_models:
        kinds.append(KIND_MODEL)
    if cfg.include_datasets:
        kinds.append(KIND_DATASET)

    works: List[Work] = []
    for kind in kinds:
        items = _search(client, kind, query, cfg.limit)
        for item in items:
            item_id = _item_id(item)
            if not item_id:
                continue
            card_text = ""
            if cfg.include_card:
                try:
                    card_text = client.get_text(_card_path(item_id, kind))
                except Exception:
                    card_text = ""
            works.append(
                _normalize_item(
                    item,
                    kind,
                    theme,
                    base_url=base_url,
                    card_text=card_text,
                    card_char_limit=cfg.card_char_limit,
                )
            )

    works.sort(key=lambda w: w.source_meta.get("reliability_score", 0), reverse=True)
    return works[: max(cfg.max_works, 0)]
