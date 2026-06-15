"""Tests for the OA full-text provider layer (src/fulltext) and its parser/classify wiring.

Network is never touched: ArxivProvider takes an injected `fetcher`, and the HTTP-free helpers
(extract_arxiv_id / extract_text_from_eprint / clean_latex) are exercised on in-memory bytes.
"""

from __future__ import annotations

import gzip
import io
import tarfile

from src.core.models import Work
from src.fulltext.arxiv import (
    ArxivProvider,
    clean_latex,
    extract_arxiv_id,
    extract_excerpt,
    extract_text_from_eprint,
)
from src.fulltext.base import (
    FullText,
    ProviderChain,
    attach_fulltext,
    effective_abstract,
    needs_fulltext,
)
from src.fulltext.cache import FulltextCache
from src.openalex.parser import normalize_work


# --- fixtures / helpers -----------------------------------------------------

def _work(work_id="https://openalex.org/W1", abstract="abstract", doi=None, source_meta=None):
    return Work(
        id=work_id,
        title="t",
        year=2021,
        venue="",
        doi=doi,
        cited_by_count=0,
        abstract=abstract,
        source_meta=source_meta or {},
    )


_SAMPLE_TEX = "\n".join([
    r"\documentclass{article}",
    r"\usepackage{amsmath}",
    r"\begin{document}",
    r"\section{Introduction}",
    r"We study a feedback loop where $x = y^2$ drives the outcome.",
    r"% this is a comment that must vanish",
    r"This mechanism explains the result~\cite{foo2020}.",
    r"\begin{equation} E = mc^2 \end{equation}",
    r"\textbf{Bold} findings follow.",
    r"\end{document}",
])


def _eprint_tar(tex: str, name: str = "main.tex") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        data = tex.encode("utf-8")
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return gzip.compress(buf.getvalue())


def _eprint_tar_multi(files: dict) -> bytes:
    """Build a gzipped tar of {name: bytes} — mirrors a real multi-file arXiv submission."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(buf.getvalue())


# --- extract_arxiv_id -------------------------------------------------------

def test_arxiv_id_from_explicit_source_meta():
    w = _work(source_meta={"arxiv_id": "2301.12345"})
    assert extract_arxiv_id(w) == "2301.12345"


def test_arxiv_id_from_doi():
    w = _work(doi="https://doi.org/10.48550/arXiv.2106.09685")
    assert extract_arxiv_id(w) == "2106.09685"


def test_arxiv_id_from_arxiv_url():
    w = _work(source_meta={"arxiv_url": "https://arxiv.org/abs/1706.03762v5"})
    assert extract_arxiv_id(w) == "1706.03762v5"


def test_arxiv_id_old_style():
    w = _work(source_meta={"arxiv_url": "https://arxiv.org/abs/hep-th/9901001"})
    assert extract_arxiv_id(w) == "hep-th/9901001"


def test_arxiv_id_none_when_no_hint():
    w = _work(doi="https://doi.org/10.1000/xyz123")
    assert extract_arxiv_id(w) is None


def test_arxiv_id_ignores_non_arxiv_doi_numbers():
    # a DOI that merely contains digits like an arXiv id must NOT be misread as one
    w = _work(doi="https://doi.org/10.1234/2301.12345")
    assert extract_arxiv_id(w) is None


# --- clean_latex / extract_excerpt / extract_text_from_eprint ---------------

def test_clean_latex_strips_markup_and_comments():
    out = clean_latex(_SAMPLE_TEX)
    assert "feedback loop" in out
    assert "Bold" in out
    assert "comment that must vanish" not in out  # % comment removed
    assert "\\cite" not in out and "cite" not in out  # citation dropped
    assert "$" not in out and "\\" not in out         # math + backslashes gone
    assert "E = mc" not in out                         # equation env dropped


def test_extract_excerpt_caps_and_cuts_on_sentence():
    text = ("Sentence one is here. " * 50).strip()
    out = extract_excerpt(text, max_chars=60)
    assert len(out) <= 60
    assert out.endswith(".")


def test_extract_excerpt_returns_all_when_short():
    assert extract_excerpt("short.", max_chars=100) == "short."


def test_extract_text_from_gzipped_tar():
    out = extract_text_from_eprint(_eprint_tar(_SAMPLE_TEX), max_chars=4000)
    assert "feedback loop" in out
    assert "\\" not in out


def test_extract_text_multifile_keeps_input_fragments():
    # Realistic arXiv submission: main \inputs separate fragments; a .bib and a binary figure
    # must be ignored, and a latin-1 fragment must decode. The included body must NOT be lost
    # to the main file's \end{document} trim (the multi-file regression this guards).
    main = "\n".join([
        r"\documentclass{article}",
        r"\begin{document}",
        r"\input{intro}",
        r"\input{methods}",
        r"\bibliography{refs}",
        r"\end{document}",
    ]).encode("utf-8")
    intro = (r"\section{Introduction}" "\n" r"The core feedback mechanism is studied here.").encode("utf-8")
    methods = (r"\section{Methods}" "\n" r"We measured rate-limiting under the Schr\"odinger regime.").encode("latin-1")
    files = {
        "main.tex": main,
        "intro.tex": intro,
        "methods.tex": methods,
        "refs.bib": b"@article{foo2020, title={ignored bibliography entry}}",
        "fig1.png": b"\x89PNG\r\n\x1a\n\x00binarynoise",
    }
    out = extract_text_from_eprint(_eprint_tar_multi(files), max_chars=4000)
    assert "feedback mechanism" in out          # intro fragment survived
    assert "rate-limiting" in out                # methods fragment survived
    assert "ignored bibliography entry" not in out  # .bib not pulled in
    assert "binarynoise" not in out                 # binary figure not pulled in
    assert "\\" not in out and "$" not in out


def test_extract_text_from_single_gzipped_tex():
    out = extract_text_from_eprint(gzip.compress(_SAMPLE_TEX.encode("utf-8")), max_chars=4000)
    assert "feedback loop" in out


def test_extract_text_pdf_returns_empty():
    assert extract_text_from_eprint(b"%PDF-1.5\n...binary...", max_chars=4000) == ""


def test_extract_text_truncates_long_body():
    big = r"\begin{document}" + ("word " * 5000) + r"\end{document}"
    out = extract_text_from_eprint(_eprint_tar(big), max_chars=500)
    assert len(out) <= 500


# --- ArxivProvider (injected fetcher, no network) ---------------------------

def test_provider_resolves_with_injected_fetcher():
    calls = []

    def fetcher(url, timeout):
        calls.append(url)
        return _eprint_tar(_SAMPLE_TEX)

    p = ArxivProvider(min_interval_sec=0, fetcher=fetcher)
    ft = p.resolve_fulltext(_work(source_meta={"arxiv_id": "2301.12345"}))
    assert ft is not None
    assert ft.source == "arxiv"
    assert ft.source_id == "2301.12345"
    assert "feedback loop" in ft.text
    assert ft.char_count == len(ft.text)
    assert calls == ["https://arxiv.org/e-print/2301.12345"]


def test_provider_returns_none_without_arxiv_id_and_skips_fetch():
    calls = []

    def fetcher(url, timeout):
        calls.append(url)
        return b""

    p = ArxivProvider(min_interval_sec=0, fetcher=fetcher)
    assert p.resolve_fulltext(_work(doi="https://doi.org/10.1/x")) is None
    assert calls == []  # no id -> no network


def test_provider_returns_none_on_empty_payload():
    p = ArxivProvider(min_interval_sec=0, fetcher=lambda url, timeout: b"")
    assert p.resolve_fulltext(_work(source_meta={"arxiv_id": "2301.1"})) is None


def test_provider_truncated_flag_set():
    big = r"\begin{document}" + ("word " * 5000) + r"\end{document}"
    p = ArxivProvider(min_interval_sec=0, max_chars=300, fetcher=lambda u, t: _eprint_tar(big))
    ft = p.resolve_fulltext(_work(source_meta={"arxiv_id": "2301.1"}))
    assert ft is not None and ft.truncated is True


# --- ProviderChain ----------------------------------------------------------

class _StubProvider:
    def __init__(self, name, result):
        self.name = name
        self.result = result
        self.calls = 0

    def resolve_fulltext(self, work):
        self.calls += 1
        return self.result


def test_chain_falls_through_to_second_provider():
    p1 = _StubProvider("a", None)
    ft = FullText(work_id="W1", source="b", text="hi")
    p2 = _StubProvider("b", ft)
    chain = ProviderChain([p1, p2])
    assert chain.resolve(_work()) is ft
    assert p1.calls == 1 and p2.calls == 1


def test_chain_short_circuits_on_first_hit():
    ft = FullText(work_id="W1", source="a", text="hi")
    p1 = _StubProvider("a", ft)
    p2 = _StubProvider("b", FullText(work_id="W1", source="b", text="other"))
    chain = ProviderChain([p1, p2])
    assert chain.resolve(_work()) is ft
    assert p2.calls == 0


def test_chain_treats_raising_provider_as_miss():
    class _Boom:
        name = "boom"

        def resolve_fulltext(self, work):
            raise RuntimeError("network down")

    ft = FullText(work_id="W1", source="b", text="hi")
    chain = ProviderChain([_Boom(), _StubProvider("b", ft)])
    assert chain.resolve(_work()) is ft


# --- FulltextCache ----------------------------------------------------------

def test_cache_roundtrip_hit(tmp_path):
    cache = FulltextCache(str(tmp_path))
    ft = FullText(work_id="W1", source="arxiv", source_id="2301.1", text="body", char_count=4)
    cache.store("https://openalex.org/W1", ft)
    cached, got = cache.lookup("https://openalex.org/W1")
    assert cached is True
    assert got is not None and got.text == "body" and got.source_id == "2301.1"


def test_cache_records_miss(tmp_path):
    cache = FulltextCache(str(tmp_path))
    cache.store("W2", None)
    cached, got = cache.lookup("W2")
    assert cached is True and got is None  # recorded miss, not "absent"


def test_cache_absent_is_not_cached(tmp_path):
    cached, got = FulltextCache(str(tmp_path)).lookup("W3")
    assert cached is False and got is None


def test_chain_with_cache_fetches_once(tmp_path):
    ft = FullText(work_id="W1", source="a", text="hi")
    provider = _StubProvider("a", ft)
    chain = ProviderChain([provider], cache=FulltextCache(str(tmp_path)))
    w = _work()
    assert chain.resolve(w).text == "hi"
    assert chain.resolve(w).text == "hi"  # second call served from cache
    assert provider.calls == 1


def test_chain_with_cache_remembers_miss(tmp_path):
    provider = _StubProvider("a", None)
    chain = ProviderChain([provider], cache=FulltextCache(str(tmp_path)))
    w = _work()
    assert chain.resolve(w) is None
    assert chain.resolve(w) is None
    assert provider.calls == 1  # miss cached -> not re-fetched


# --- needs_fulltext gate ----------------------------------------------------

def test_needs_fulltext_oa_short_true():
    w = _work(abstract="x" * 100, source_meta={"is_oa": True})
    assert needs_fulltext(w, max_abstract_chars=280) is True


def test_needs_fulltext_oa_long_false():
    w = _work(abstract="x" * 400, source_meta={"is_oa": True})
    assert needs_fulltext(w, max_abstract_chars=280) is False


def test_needs_fulltext_non_oa_false():
    w = _work(abstract="x" * 50, source_meta={"is_oa": False})
    assert needs_fulltext(w, max_abstract_chars=280) is False


def test_needs_fulltext_arxiv_url_counts_as_oa():
    w = _work(abstract="", source_meta={"arxiv_url": "https://arxiv.org/abs/2301.1"})
    assert needs_fulltext(w, max_abstract_chars=280) is True


# --- effective_abstract -----------------------------------------------------

def test_effective_abstract_identical_without_fulltext():
    w = _work(abstract="a" * 800)
    # must match the prior scorer input exactly: (abstract or "")[:500]
    assert effective_abstract(w) == ("a" * 800)[:500]


def test_effective_abstract_empty_abstract_no_fulltext():
    assert effective_abstract(_work(abstract=None)) == ""


def test_effective_abstract_appends_fulltext():
    w = _work(abstract="base abstract", source_meta={"fulltext_excerpt": "FULL BODY"})
    out = effective_abstract(w)
    assert "base abstract" in out and "FULL BODY" in out and "[全文抜粋]" in out


def test_effective_abstract_only_fulltext_when_abstract_empty():
    w = _work(abstract="", source_meta={"fulltext_excerpt": "FULL BODY"})
    out = effective_abstract(w)
    assert out.startswith("[全文抜粋]") and "FULL BODY" in out


def test_attach_fulltext_sets_source_meta():
    w = _work()
    assert attach_fulltext(w, FullText(work_id="W1", source="arxiv", source_id="2301.1", text="body"))
    assert w.source_meta["fulltext_excerpt"] == "body"
    assert w.source_meta["fulltext_source"] == "arxiv"


def test_attach_fulltext_noop_on_none_or_empty():
    w = _work()
    assert attach_fulltext(w, None) is False
    assert attach_fulltext(w, FullText(work_id="W1", source="arxiv", text="")) is False
    assert "fulltext_excerpt" not in w.source_meta


# --- parser source_meta population ------------------------------------------

def test_parser_populates_oa_and_arxiv_source_meta():
    payload = {
        "id": "https://openalex.org/W9",
        "display_name": "Attention Is All You Need",
        "publication_year": 2017,
        "open_access": {"is_oa": True, "oa_url": "https://arxiv.org/pdf/1706.03762"},
        "primary_location": {
            "pdf_url": "https://arxiv.org/pdf/1706.03762",
            "landing_page_url": "https://arxiv.org/abs/1706.03762",
        },
        "locations": [
            {"landing_page_url": "https://arxiv.org/abs/1706.03762"},
        ],
    }
    w = normalize_work(payload)
    assert w.source_meta["is_oa"] is True
    assert w.source_meta["oa_url"].endswith("1706.03762")
    assert "arxiv.org" in w.source_meta["arxiv_url"]
    # end-to-end: the provider layer can now derive the id from parsed metadata
    assert extract_arxiv_id(w) == "1706.03762"


def test_parser_source_meta_empty_when_no_oa_info():
    payload = {"id": "https://openalex.org/W10", "display_name": "x", "publication_year": 2020}
    w = normalize_work(payload)
    assert w.source_meta.get("is_oa") in (None, False)
    assert "arxiv_url" not in w.source_meta
