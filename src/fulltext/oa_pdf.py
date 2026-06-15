"""OpenAlex oa_url PDF fallback provider (last in the chain; ③ the generic OA fallback).

This is the catch-all for OA full text that neither arXiv nor Europe PMC/CORE resolved: fetch
the PDF at the work's OA url and best-effort extract its text with the stdlib only (zlib to
inflate FlateDecode content streams + a content-stream string scanner). Pure-stdlib PDF text
extraction is inherently lossy (it cannot handle CID/Type0 font glyph remapping), so the
result is gated by a prose-quality heuristic: anything that does not look like clean prose is
dropped (return None) rather than feeding garbage to the mechanism scorer. Since this is the
LAST provider, a None here just leaves the existing abstract-only path in place.
"""

from __future__ import annotations

import re
import zlib
from typing import Callable, List, Optional

from src.core.models import Work
from src.fulltext.base import FullText
from src.fulltext.http import HttpFetcher
from src.fulltext.textutil import collapse_ws, extract_excerpt, prose_ratio

_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
_OCTAL_RE = re.compile(rb"[0-7]{1,3}")

_MIN_PDF_TEXT_CHARS = 400      # below this, extraction effectively failed
_MIN_PROSE_RATIO = 0.85        # below this, the bytes are glyph garbage, not prose

_PDF_ESCAPES = {
    0x6E: 0x0A, 0x72: 0x0D, 0x74: 0x09, 0x62: 0x08,
    0x66: 0x0C, 0x28: 0x28, 0x29: 0x29, 0x5C: 0x5C,
}


def _inflate_streams(data: bytes) -> List[bytes]:
    """Inflate every FlateDecode-looking stream; fall back to the raw bytes if none inflate."""
    out: List[bytes] = []
    for match in _STREAM_RE.finditer(data):
        raw = match.group(1)
        try:
            out.append(zlib.decompress(raw))
        except zlib.error:
            try:
                out.append(zlib.decompressobj().decompress(raw))
            except zlib.error:
                continue
    return out or [data]


def _pdf_strings(content: bytes) -> List[bytes]:
    """Scan a content stream for balanced (...) string literals (the show-text operands)."""
    out: List[bytes] = []
    i, n = 0, len(content)
    while i < n:
        if content[i] != 0x28:  # '('
            i += 1
            continue
        depth, j = 1, i + 1
        buf = bytearray()
        while j < n and depth > 0:
            ch = content[j]
            if ch == 0x5C:  # backslash: keep escape pair verbatim for the decoder
                buf.append(ch)
                if j + 1 < n:
                    buf.append(content[j + 1])
                j += 2
                continue
            if ch == 0x28:
                depth += 1
                buf.append(ch)
            elif ch == 0x29:
                depth -= 1
                if depth == 0:
                    j += 1
                    break
                buf.append(ch)
            else:
                buf.append(ch)
            j += 1
        out.append(bytes(buf))
        i = j
    return out


def _decode_pdf_string(b: bytes) -> str:
    res = bytearray()
    i, n = 0, len(b)
    while i < n:
        ch = b[i]
        if ch == 0x5C and i + 1 < n:
            nxt = b[i + 1]
            if nxt in _PDF_ESCAPES:
                res.append(_PDF_ESCAPES[nxt])
                i += 2
                continue
            m = _OCTAL_RE.match(b, i + 1)
            if m and 0x30 <= nxt <= 0x37:
                res.append(int(m.group(0), 8) & 0xFF)
                i += 1 + len(m.group(0))
                continue
            i += 2  # backslash-newline line continuation / unknown escape
            continue
        res.append(ch)
        i += 1
    return res.decode("latin-1", errors="ignore")


def pdf_extract_text(data: bytes) -> str:
    """Best-effort plain text from a PDF's content streams ("" if it does not look like a PDF)."""
    if data[:5] != b"%PDF-":
        return ""
    parts: List[str] = []
    for stream in _inflate_streams(data):
        for raw in _pdf_strings(stream):
            parts.append(_decode_pdf_string(raw))
    return collapse_ws(" ".join(parts))


class OaPdfProvider:
    name = "oa_pdf"

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

    def resolve_fulltext(self, work: Work) -> Optional[FullText]:
        sm = getattr(work, "source_meta", None) or {}
        url = sm.get("oa_url") or sm.get("pdf_url")
        if not url:
            return None
        data = self._get(str(url))
        if not data:
            return None
        full = pdf_extract_text(data)
        # Quality gate: reject stubs and glyph-garbage so only clean prose reaches the scorer.
        if len(full) < _MIN_PDF_TEXT_CHARS or prose_ratio(full) < _MIN_PROSE_RATIO:
            return None
        text = extract_excerpt(full, max_chars=self.max_chars)
        if not text:
            return None
        return FullText(
            work_id=work.id,
            source=self.name,
            source_id="",
            url=str(url),
            text=text,
            char_count=len(text),
            truncated=len(full) > len(text),
        )


__all__ = ["OaPdfProvider", "pdf_extract_text"]
