"""Europe PMC full-text provider (keyless; second in the chain after arXiv).

Covers OA full text that is NOT on arXiv (biomedical / life sciences and other PMC-indexed
work). Flow: look the work up by DOI in the Europe PMC REST search, and when the hit is in
the EPMC full-text store (inEPMC=Y), fetch its JATS XML and extract the <abstract>+<body>
prose. JATS is XML, so extraction is far lower-noise than PDF. stdlib only (urllib + ElementTree).
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Callable, List, Optional
from xml.etree import ElementTree as ET

from src.core.models import Work
from src.fulltext.base import FullText
from src.fulltext.http import HttpFetcher
from src.fulltext.textutil import collapse_ws, extract_excerpt

_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_FULLTEXT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{source}/{ext_id}/fullTextXML"

# JATS sections that carry no transferable mechanism prose — dropped before text extraction.
_SKIP_TAGS = {"ref-list", "table-wrap", "fig", "table", "tex-math", "disp-formula", "inline-formula"}


def _norm_doi(doi: str) -> str:
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if d.startswith(prefix):
            return d[len(prefix):]
    return d


def _local(tag: str) -> str:
    """Local name of a possibly-namespaced ElementTree tag ('{ns}body' -> 'body')."""
    return tag.rsplit("}", 1)[-1]


def _text_under(elem: ET.Element) -> str:
    """Concatenate the visible text under an element, skipping reference/figure/math subtrees."""
    parts: List[str] = []

    def walk(node: ET.Element) -> None:
        if _local(node.tag) in _SKIP_TAGS:
            return
        if node.text:
            parts.append(node.text)
        for child in list(node):
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(elem)
    return collapse_ws(" ".join(parts))


def parse_jats_fulltext(xml_bytes: bytes) -> str:
    """Extract <abstract> + <body> prose from a JATS full-text XML document."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return ""
    chunks: List[str] = []
    for elem in root.iter():
        if _local(elem.tag) in ("abstract", "body"):
            text = _text_under(elem)
            if text:
                chunks.append(text)
    return collapse_ws(" ".join(chunks))


class EuropePmcProvider:
    name = "europepmc"

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
        query = urllib.parse.urlencode({
            "query": f'DOI:"{doi}"',
            "format": "json",
            "resultType": "lite",
            "pageSize": "1",
        })
        data = self._get(f"{_SEARCH_URL}?{query}")
        if not data:
            return None
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        results = (payload.get("resultList") or {}).get("result") or []
        return results[0] if results and isinstance(results[0], dict) else None

    def resolve_fulltext(self, work: Work) -> Optional[FullText]:
        if not work.doi:
            return None
        hit = self._lookup(_norm_doi(str(work.doi)))
        if not hit or str(hit.get("inEPMC", "")).upper() != "Y":
            return None
        source = str(hit.get("source") or "")
        ext_id = str(hit.get("id") or "")
        if not source or not ext_id:
            return None
        url = _FULLTEXT_URL.format(source=source, ext_id=ext_id)
        xml_bytes = self._get(url)
        if not xml_bytes:
            return None
        full = parse_jats_fulltext(xml_bytes)
        if not full:
            return None
        text = extract_excerpt(full, max_chars=self.max_chars)
        if not text:
            return None
        return FullText(
            work_id=work.id,
            source=self.name,
            source_id=str(hit.get("pmcid") or ext_id),
            url=url,
            text=text,
            char_count=len(text),
            truncated=len(full) > len(text),
        )


__all__ = ["EuropePmcProvider", "parse_jats_fulltext"]
