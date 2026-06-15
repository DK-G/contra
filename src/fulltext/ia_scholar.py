"""Internet Archive Scholar full-text provider (keyless; in the ② non-arXiv OA group).

IA Scholar (scholar.archive.org) is backed by the fatcat catalog. We look a work up by DOI in
the fatcat API with files expanded, pick an archived PDF, and reuse the shared best-effort PDF
text extraction. This reaches OA full text that is preserved in the Internet Archive even when
the publisher's own oa_url is missing or dead — a useful complement to Europe PMC / CORE.

stdlib only (urllib + json). Keyless. Resolves None whenever there is no DOI, no archived PDF,
or the PDF text fails the prose-quality gate.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Callable, List, Optional

from src.core.models import Work
from src.fulltext.base import FullText
from src.fulltext.http import HttpFetcher
from src.fulltext.oa_pdf import extract_pdf_excerpt

_LOOKUP_URL = "https://api.fatcat.wiki/v0/release/lookup"


def _norm_doi(doi: str) -> str:
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if d.startswith(prefix):
            return d[len(prefix):]
    return d


def _pdf_urls(release: dict) -> List[str]:
    """Archived PDF urls from a fatcat release (files expanded), best candidates first."""
    out: List[str] = []
    for f in release.get("files") or []:
        if not isinstance(f, dict):
            continue
        if str(f.get("mimetype") or "").lower() not in ("application/pdf", "application/x-pdf"):
            continue
        for u in f.get("urls") or []:
            if isinstance(u, dict) and u.get("url"):
                out.append(str(u["url"]))
    # Prefer Internet Archive / web.archive copies (stable, the point of IA Scholar).
    out.sort(key=lambda u: 0 if ("archive.org" in u) else 1)
    return out


class IaScholarProvider:
    name = "ia_scholar"

    def __init__(
        self,
        *,
        http: Optional[HttpFetcher] = None,
        max_chars: int = 4000,
        fetcher: Optional[Callable[[str], Optional[bytes]]] = None,
    ) -> None:
        self.http = http or HttpFetcher()
        self.max_chars = max_chars
        self._fetcher = fetcher

    def _get(self, url: str) -> Optional[bytes]:
        if self._fetcher is not None:
            return self._fetcher(url)
        return self.http.get(url)

    def _lookup(self, doi: str) -> Optional[dict]:
        query = urllib.parse.urlencode({"doi": doi, "expand": "files", "hide": "abstracts,refs"})
        data = self._get(f"{_LOOKUP_URL}?{query}")
        if not data:
            return None
        try:
            release = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return release if isinstance(release, dict) else None

    def resolve_fulltext(self, work: Work) -> Optional[FullText]:
        if not work.doi:
            return None
        release = self._lookup(_norm_doi(str(work.doi)))
        if not release:
            return None
        for url in _pdf_urls(release):
            data = self._get(url)
            if not data:
                continue
            res = extract_pdf_excerpt(data, max_chars=self.max_chars)
            if res is None:
                continue
            text, truncated = res
            return FullText(
                work_id=work.id,
                source=self.name,
                source_id=str(release.get("ident") or ""),
                url=url,
                text=text,
                char_count=len(text),
                truncated=truncated,
            )
        return None


__all__ = ["IaScholarProvider"]
