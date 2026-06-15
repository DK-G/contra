"""arXiv full-text provider (first increment: keyless, LaTeX e-print source).

arXiv is tried first because it is keyless and its e-print (LaTeX source) gives the lowest-
noise full text — no PDF text-extraction artefacts. We fetch https://arxiv.org/e-print/<id>,
decompress it with the stdlib (gzip + tarfile), strip LaTeX markup, and extract a
length-capped excerpt. Anything that cannot be parsed as text (e.g. a PDF-only submission)
returns None so the pipeline falls back to the abstract-only path.

Rate: 1 request / 3s, single sequential connection, with timeout + bounded retries — per
arXiv's robots etiquette. HTTP is urllib.request only (no external deps, spec.md §4).
"""

from __future__ import annotations

import gzip
import io
import re
import tarfile
import time
import urllib.request
from datetime import datetime, timezone
from typing import Callable, List, Optional

from src.core.models import Work
from src.fulltext.base import FullText
from src.fulltext.textutil import extract_excerpt

_USER_AGENT = "contra-cli/0.1 (full-text provider; mailto via OpenAlex politepool)"

# arXiv id forms: new "2301.12345" / "2301.12345v2", old "hep-th/9901001".
_ARXIV_NEW = re.compile(r"\d{4}\.\d{4,5}(?:v\d+)?")
_ARXIV_OLD = re.compile(r"[a-z][a-z\-]+(?:\.[A-Za-z]{2})?/\d{7}(?:v\d+)?")


def _arxiv_id_from_text(text: str) -> Optional[str]:
    """Pull an arXiv id out of a DOI or URL string (only when it clearly references arXiv)."""
    low = text.lower()
    if "arxiv" not in low and "10.48550" not in low:
        return None
    m = _ARXIV_OLD.search(text)
    if m:
        return m.group(0)
    m = _ARXIV_NEW.search(text)
    if m:
        return m.group(0)
    return None


def extract_arxiv_id(work: Work) -> Optional[str]:
    """Resolve the work's arXiv id from source_meta, then DOI / OA / location URLs.

    source_meta['arxiv_id'] (if a caller set it explicitly) wins; otherwise we derive it from
    the DOI (10.48550/arXiv.*) or any arXiv landing/pdf/oa URL the parser stored.
    """
    sm = getattr(work, "source_meta", None) or {}
    explicit = sm.get("arxiv_id")
    if explicit:
        return str(explicit)
    candidates: List[str] = []
    if work.doi:
        candidates.append(str(work.doi))
    for key in ("arxiv_url", "oa_url", "pdf_url", "landing_page_url"):
        val = sm.get(key)
        if val:
            candidates.append(str(val))
    for text in candidates:
        aid = _arxiv_id_from_text(text)
        if aid:
            return aid
    return None


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="ignore")


def _document_body(tex: str) -> str:
    """The content between \\begin{document} and \\end{document}, or the whole fragment.

    arXiv multi-file submissions \\input separate .tex fragments; those fragments have no
    \\begin{document}. We must keep each file's BODY (and the fragments whole) so the included
    text survives — otherwise concatenating a fragment AFTER the main file's \\end{document}
    would be truncated away by the document-boundary trim.
    """
    begin = re.search(r"\\begin\{document\}", tex)
    if not begin:
        return tex
    body = tex[begin.end():]
    end = re.search(r"\\end\{document\}", body)
    if end:
        body = body[:end.start()]
    return body


def _join_tex(texts: List[str]) -> str:
    """Concatenate .tex blobs: main file bodies first (in file order), then \\input fragments.

    Each main file (one containing \\begin{document}) contributes only its body; fragment files
    are kept whole. This preserves the included body of split submissions instead of losing it
    to the main file's \\end{document} trim.
    """
    mains = [_document_body(t) for t in texts if "\\begin{document}" in t]
    frags = [t for t in texts if "\\begin{document}" not in t]
    return "\n".join(mains + frags)


def _eprint_to_tex(data: bytes) -> str:
    """Decompress an arXiv e-print payload to concatenated LaTeX source.

    Handles: gzipped tar (multi-file submission), a single gzipped .tex, or raw text.
    Returns "" for PDF-only payloads (stdlib cannot cleanly extract PDF text).
    """
    if data[:5] == b"%PDF-":
        return ""
    raw = data
    if data[:2] == b"\x1f\x8b":  # gzip magic
        try:
            raw = gzip.decompress(data)
        except OSError:
            raw = data
    try:
        with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
            texts: List[str] = []
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                if not member.name.lower().endswith((".tex", ".txt")):
                    continue
                handle = tar.extractfile(member)
                if handle is None:
                    continue
                texts.append(_decode(handle.read()))
            if texts:
                return _join_tex(texts)
    except (tarfile.TarError, OSError, EOFError):
        pass
    if raw[:5] == b"%PDF-":
        return ""
    return _decode(raw)


def clean_latex(tex: str) -> str:
    """Strip LaTeX markup down to readable prose (best-effort, noise reduction for the LLM)."""
    begin = re.search(r"\\begin\{document\}", tex)
    if begin:
        tex = tex[begin.end():]
    end = re.search(r"\\end\{document\}", tex)
    if end:
        tex = tex[:end.start()]
    # drop comments (unescaped %)
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    # drop content-free / formula / float environments wholesale
    tex = re.sub(
        r"\\begin\{(equation|align|eqnarray|figure|table|tabular|thebibliography|"
        r"displaymath|gather|multline)\*?\}.*?\\end\{\1\*?\}",
        " ", tex, flags=re.DOTALL,
    )
    # citations / refs / labels / package noise -> drop entirely
    tex = re.sub(
        r"\\(cite[a-z]*|ref|eqref|autoref|label|usepackage|documentclass|input|include|"
        r"bibliography|bibliographystyle|includegraphics|newcommand|renewcommand)\b\s*"
        r"(\[[^\]]*\])?\s*(\{[^}]*\})?",
        " ", tex,
    )
    # section-like commands -> keep the heading text as a sentence
    tex = re.sub(
        r"\\(section|subsection|subsubsection|paragraph|title|chapter)\*?\s*\{([^{}]*)\}",
        r" \2. ", tex,
    )
    # text-formatting commands -> keep inner content
    tex = re.sub(r"\\(textbf|textit|emph|texttt|mathrm|textrm|text|mbox)\s*\{([^{}]*)\}", r"\2", tex)
    # inline math -> space
    tex = re.sub(r"\$[^$]*\$", " ", tex)
    # remaining \command{arg} -> keep the arg text
    tex = re.sub(r"\\[a-zA-Z]+\*?\s*(\[[^\]]*\])?\s*\{([^{}]*)\}", r"\2", tex)
    # remaining bare \command -> drop
    tex = re.sub(r"\\[a-zA-Z]+\*?", " ", tex)
    tex = tex.replace("{", " ").replace("}", " ").replace("\\", " ")
    tex = re.sub(r"\s+", " ", tex)
    return tex.strip()


def clean_eprint(data: bytes) -> str:
    """e-print bytes -> full cleaned prose (uncapped). "" if not parseable as text."""
    tex = _eprint_to_tex(data)
    if not tex:
        return ""
    return clean_latex(tex)


def extract_text_from_eprint(data: bytes, max_chars: int = 4000) -> str:
    """Full pipeline: e-print bytes -> LaTeX -> cleaned prose -> length-capped excerpt."""
    return extract_excerpt(clean_eprint(data), max_chars=max_chars)


class ArxivProvider:
    """Resolve full text from arXiv's e-print (LaTeX) source. Keyless. 1 req / 3s."""

    name = "arxiv"

    def __init__(
        self,
        *,
        min_interval_sec: float = 3.0,
        timeout_sec: int = 30,
        max_retries: int = 3,
        max_chars: int = 4000,
        eprint_base: str = "https://arxiv.org/e-print/",
        fetcher: Optional[Callable[[str, int], bytes]] = None,
    ) -> None:
        self.min_interval_sec = min_interval_sec
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.max_chars = max_chars
        self.eprint_base = eprint_base
        self._fetcher = fetcher or self._http_fetch
        self._last_call_at = 0.0

    def _http_fetch(self, url: str, timeout: int) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as res:  # pragma: no cover - network
            return res.read()

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_call_at
        if elapsed < self.min_interval_sec:
            time.sleep(self.min_interval_sec - elapsed)

    def _fetch(self, url: str) -> Optional[bytes]:
        for attempt in range(max(1, self.max_retries)):
            self._rate_limit()
            try:
                return self._fetcher(url, self.timeout_sec)
            except Exception:  # pragma: no cover - network error path
                if attempt + 1 >= self.max_retries:
                    return None
                time.sleep(min(2 ** attempt, 8))
            finally:
                self._last_call_at = time.time()
        return None

    def resolve_fulltext(self, work: Work) -> Optional[FullText]:
        arxiv_id = extract_arxiv_id(work)
        if not arxiv_id:
            return None
        url = self.eprint_base + arxiv_id
        data = self._fetch(url)
        if not data:
            return None
        cleaned = clean_eprint(data)
        if not cleaned:
            return None
        text = extract_excerpt(cleaned, max_chars=self.max_chars)
        if not text:
            return None
        return FullText(
            work_id=work.id,
            source=self.name,
            source_id=arxiv_id,
            url=url,
            text=text,
            char_count=len(text),
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            truncated=len(cleaned) > len(text),
        )


__all__ = [
    "ArxivProvider",
    "extract_arxiv_id",
    "extract_text_from_eprint",
    "clean_latex",
    "extract_excerpt",
]
