"""Tests for the non-arXiv full-text providers (Europe PMC / CORE / oa_url PDF) and shared
text utilities. Network is mocked via each provider's injected `fetcher` seam.
"""

from __future__ import annotations

import json
import zlib

from src.core.models import Work
from src.fulltext import build_default_chain
from src.fulltext.core import CoreProvider
from src.fulltext.europepmc import EuropePmcProvider, parse_jats_fulltext
from src.fulltext.ia_scholar import IaScholarProvider
from src.fulltext.oa_pdf import OaPdfProvider, pdf_extract_text
from src.fulltext.textutil import collapse_ws, extract_excerpt, prose_ratio


def _work(work_id="https://openalex.org/W1", doi=None, source_meta=None):
    return Work(
        id=work_id, title="t", year=2021, venue="", doi=doi, cited_by_count=0,
        abstract="", source_meta=source_meta or {},
    )


# --- textutil ---------------------------------------------------------------

def test_collapse_ws():
    assert collapse_ws("  a\n\t b   c ") == "a b c"


def test_extract_excerpt_caps():
    out = extract_excerpt("Sentence one here. " * 50, max_chars=60)
    assert len(out) <= 60 and out.endswith(".")


def test_prose_ratio_high_for_prose_low_for_binary():
    assert prose_ratio("This is a normal English sentence about mechanisms.") > 0.95
    assert prose_ratio("\x00\x01\x02\x03\x04\x05\x06\x07" * 10) < 0.2


# --- Europe PMC -------------------------------------------------------------

_JATS = (
    "<article><front><article-meta>"
    "<abstract><p>This studies a feedback mechanism in cells.</p></abstract>"
    "</article-meta></front>"
    "<body><sec><title>Introduction</title>"
    "<p>The rate-limiting step drives the measured outcome.</p></sec>"
    "<ref-list><ref>IGNORED REFERENCE ENTRY</ref></ref-list>"
    "<fig><caption>IGNORED FIGURE CAPTION</caption></fig>"
    "</body></article>"
).encode("utf-8")

_EPMC_SEARCH = json.dumps({
    "resultList": {"result": [
        {"source": "PMC", "id": "PMC777", "pmcid": "PMC777", "inEPMC": "Y", "isOpenAccess": "Y"}
    ]}
}).encode("utf-8")


def test_parse_jats_keeps_abstract_body_drops_refs_figs():
    out = parse_jats_fulltext(_JATS)
    assert "feedback mechanism" in out
    assert "rate-limiting step" in out
    assert "IGNORED REFERENCE ENTRY" not in out
    assert "IGNORED FIGURE CAPTION" not in out


def test_europepmc_resolves_via_doi():
    urls = []

    def fetcher(url):
        urls.append(url)
        if "/search" in url:
            return _EPMC_SEARCH
        if "fullTextXML" in url:
            return _JATS
        return None

    p = EuropePmcProvider(fetcher=fetcher)
    ft = p.resolve_fulltext(_work(doi="https://doi.org/10.1/abc"))
    assert ft is not None
    assert ft.source == "europepmc" and ft.source_id == "PMC777"
    assert "feedback mechanism" in ft.text
    assert any("PMC/PMC777/fullTextXML" in u for u in urls)


def test_europepmc_none_without_doi():
    called = []
    p = EuropePmcProvider(fetcher=lambda url: called.append(url) or None)
    assert p.resolve_fulltext(_work(doi=None)) is None
    assert called == []  # no DOI -> no lookup


def test_europepmc_skips_when_not_in_epmc():
    search = json.dumps({"resultList": {"result": [
        {"source": "MED", "id": "1", "inEPMC": "N"}
    ]}}).encode("utf-8")
    urls = []

    def fetcher(url):
        urls.append(url)
        return search if "/search" in url else None

    p = EuropePmcProvider(fetcher=fetcher)
    assert p.resolve_fulltext(_work(doi="10.1/x")) is None
    assert all("fullTextXML" not in u for u in urls)  # never fetched the body


# --- CORE -------------------------------------------------------------------

def test_core_disabled_without_key():
    p = CoreProvider(api_key="")
    assert p.enabled is False
    called = []
    p2 = CoreProvider(api_key="", fetcher=lambda url, headers: called.append(url) or None)
    assert p2.resolve_fulltext(_work(doi="10.1/x")) is None
    assert called == []


def test_core_resolves_and_sends_bearer():
    captured = {}
    body = "A long extracted full text. " * 30  # > _MIN_FULLTEXT_CHARS

    def fetcher(url, headers):
        captured.update(headers)
        return json.dumps({"results": [{"id": "core1", "fullText": body}]}).encode("utf-8")

    p = CoreProvider(api_key="SECRET", fetcher=fetcher)
    ft = p.resolve_fulltext(_work(doi="https://doi.org/10.1/abc"))
    assert ft is not None and ft.source == "core" and ft.source_id == "core1"
    assert "extracted full text" in ft.text
    assert captured.get("Authorization") == "Bearer SECRET"


def test_core_rejects_short_fulltext():
    def fetcher(url, headers):
        return json.dumps({"results": [{"id": "c", "fullText": "too short"}]}).encode("utf-8")

    assert CoreProvider(api_key="K", fetcher=fetcher).resolve_fulltext(_work(doi="10.1/x")) is None


def test_core_none_without_doi():
    assert CoreProvider(api_key="K").resolve_fulltext(_work(doi=None)) is None


# --- oa_url PDF -------------------------------------------------------------

def _make_pdf(payload: str) -> bytes:
    content = b"BT (" + payload.encode("latin-1") + b") Tj ET"
    comp = zlib.compress(content)
    return b"%PDF-1.4\nstream\n" + comp + b"\nendstream\n%%EOF"


_PDF_SENTENCE = "The feedback mechanism regulates the rate limiting step in the studied system. " * 8


def test_pdf_extract_text_from_flate_stream():
    out = pdf_extract_text(_make_pdf(_PDF_SENTENCE))
    assert "feedback mechanism" in out
    assert "rate limiting step" in out


def test_pdf_extract_text_empty_for_non_pdf():
    assert pdf_extract_text(b"not a pdf at all") == ""


def test_oa_pdf_provider_resolves():
    pdf = _make_pdf(_PDF_SENTENCE)
    p = OaPdfProvider(fetcher=lambda url: pdf)
    ft = p.resolve_fulltext(_work(source_meta={"oa_url": "https://x/y.pdf"}))
    assert ft is not None and ft.source == "oa_pdf"
    assert "feedback mechanism" in ft.text
    assert ft.url == "https://x/y.pdf"


def test_oa_pdf_none_without_url():
    called = []
    p = OaPdfProvider(fetcher=lambda url: called.append(url) or None)
    assert p.resolve_fulltext(_work(source_meta={})) is None
    assert called == []


def test_oa_pdf_rejects_short_or_garbage():
    # a valid PDF whose extracted text is too short -> gated out (None)
    p = OaPdfProvider(fetcher=lambda url: _make_pdf("tiny."))
    assert p.resolve_fulltext(_work(source_meta={"oa_url": "https://x/y.pdf"})) is None


def test_oa_pdf_uses_pdf_url_when_no_oa_url():
    pdf = _make_pdf(_PDF_SENTENCE)
    p = OaPdfProvider(fetcher=lambda url: pdf)
    ft = p.resolve_fulltext(_work(source_meta={"pdf_url": "https://x/z.pdf"}))
    assert ft is not None and ft.url == "https://x/z.pdf"


# --- IA Scholar (fatcat) ----------------------------------------------------

def _fatcat_release(pdf_url="https://web.archive.org/web/2020/https://x.org/paper.pdf"):
    return json.dumps({
        "ident": "fatcat123",
        "files": [
            {"mimetype": "text/html", "urls": [{"url": "https://x.org/landing"}]},
            {"mimetype": "application/pdf", "urls": [{"url": pdf_url}]},
        ],
    }).encode("utf-8")


def test_ia_scholar_resolves_archived_pdf():
    pdf = _make_pdf(_PDF_SENTENCE)
    urls = []

    def fetcher(url):
        urls.append(url)
        if "/release/lookup" in url:
            return _fatcat_release()
        if url.endswith(".pdf"):
            return pdf
        return None

    p = IaScholarProvider(fetcher=fetcher)
    ft = p.resolve_fulltext(_work(doi="https://doi.org/10.1/abc"))
    assert ft is not None and ft.source == "ia_scholar" and ft.source_id == "fatcat123"
    assert "feedback mechanism" in ft.text
    assert any("/release/lookup" in u for u in urls)


def test_ia_scholar_none_without_doi():
    called = []
    p = IaScholarProvider(fetcher=lambda url: called.append(url) or None)
    assert p.resolve_fulltext(_work(doi=None)) is None
    assert called == []


def test_ia_scholar_none_without_pdf_file():
    release = json.dumps({"ident": "x", "files": [
        {"mimetype": "text/html", "urls": [{"url": "https://x.org/landing"}]}
    ]}).encode("utf-8")
    p = IaScholarProvider(fetcher=lambda url: release if "lookup" in url else None)
    assert p.resolve_fulltext(_work(doi="10.1/x")) is None


def test_ia_scholar_skips_garbage_pdf():
    def fetcher(url):
        if "lookup" in url:
            return _fatcat_release()
        return _make_pdf("tiny.")  # passes mimetype but fails the prose/length gate
    assert IaScholarProvider(fetcher=fetcher).resolve_fulltext(_work(doi="10.1/x")) is None


# --- default chain ordering -------------------------------------------------

def test_build_default_chain_order():
    chain = build_default_chain(cache_dir="data/fulltext")
    assert [p.name for p in chain.providers] == [
        "arxiv", "europepmc", "ia_scholar", "core", "oa_pdf",
    ]
