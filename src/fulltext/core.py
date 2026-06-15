"""CORE full-text provider (API key via env; third in the chain).

CORE aggregates OA full text across repositories and often returns the extracted plain text
directly, so no PDF parsing is needed. The API key is read from the CORE_API_KEY environment
variable — never hardcoded (spec.md §4). With no key the provider is silently disabled
(resolve returns None) so the chain simply falls through to the next provider.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from typing import Callable, Optional

from src.core.models import Work
from src.fulltext.base import FullText
from src.fulltext.http import HttpFetcher
from src.fulltext.textutil import collapse_ws, extract_excerpt

_SEARCH_URL = "https://api.core.ac.uk/v3/search/works"

# Minimum plausibly-useful full text length; CORE sometimes returns a stub / metadata blob.
_MIN_FULLTEXT_CHARS = 400


def _norm_doi(doi: str) -> str:
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if d.startswith(prefix):
            return d[len(prefix):]
    return d


class CoreProvider:
    name = "core"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        http: Optional[HttpFetcher] = None,
        max_chars: int = 4000,
        fetcher: Optional[Callable[[str, dict], Optional[bytes]]] = None,
    ) -> None:
        # Env is the default source; an explicit api_key (tests) overrides. Empty => disabled.
        self.api_key = api_key if api_key is not None else os.environ.get("CORE_API_KEY", "")
        self.http = http or HttpFetcher()
        self.max_chars = max_chars
        self._fetcher = fetcher

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _get(self, url: str, headers: dict) -> Optional[bytes]:
        if self._fetcher is not None:
            return self._fetcher(url, headers)
        return self.http.get(url, headers=headers)

    def resolve_fulltext(self, work: Work) -> Optional[FullText]:
        if not self.enabled or not work.doi:
            return None
        query = urllib.parse.urlencode({"q": f'doi:"{_norm_doi(str(work.doi))}"', "limit": "1"})
        data = self._get(f"{_SEARCH_URL}?{query}", {"Authorization": f"Bearer {self.api_key}"})
        if not data:
            return None
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        results = payload.get("results") or []
        if not results or not isinstance(results[0], dict):
            return None
        full = collapse_ws(str(results[0].get("fullText") or ""))
        if len(full) < _MIN_FULLTEXT_CHARS:
            return None
        text = extract_excerpt(full, max_chars=self.max_chars)
        if not text:
            return None
        return FullText(
            work_id=work.id,
            source=self.name,
            source_id=str(results[0].get("id") or ""),
            url=f"{_SEARCH_URL}?{query}",
            text=text,
            char_count=len(text),
            truncated=len(full) > len(text),
        )


__all__ = ["CoreProvider"]
