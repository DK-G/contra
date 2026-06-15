"""Real-network probe for the arXiv full-text provider (src/fulltext/arxiv.py).

The unit tests mock the network, so they cannot catch mismatches between our stdlib
gzip/tarfile + LaTeX-stripping pipeline and the ACTUAL bytes arXiv serves at
https://arxiv.org/e-print/<id> (multi-file tarballs, odd encodings, PDF-only sources).
This probe fetches a few known arXiv ids for real, runs the full resolve pipeline at the
production rate (1 req/3s), and reports what came back so we can eyeball noise reduction.

It can also drive the FULL default chain (arXiv -> Europe PMC -> CORE -> oa_url PDF) for a
single work via --doi / --oa-url / --arxiv-id, to validate the non-arXiv providers too.
CORE only activates when CORE_API_KEY is set in the environment.

Run from repo root (needs outbound access to the relevant hosts):
  python scripts/arxiv_fulltext_probe.py
  python scripts/arxiv_fulltext_probe.py --ids 1706.03762 2010.11929 --max-chars 1500
  python scripts/arxiv_fulltext_probe.py --doi 10.1371/journal.pone.0000217
  python scripts/arxiv_fulltext_probe.py --oa-url https://example.org/paper.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.core.models import Work  # noqa: E402
from src.fulltext import build_default_chain  # noqa: E402
from src.fulltext.arxiv import ArxivProvider, extract_arxiv_id  # noqa: E402

# Defaults chosen to span fields/eras and exercise multi-file LaTeX tarballs.
_DEFAULT_IDS = ["1706.03762", "2010.11929", "1412.6980"]


def _work_for(arxiv_id: str) -> Work:
    return Work(
        id=f"probe:{arxiv_id}",
        title=arxiv_id,
        year=0,
        venue="",
        doi=None,
        cited_by_count=0,
        abstract="",
        source_meta={"arxiv_id": arxiv_id},
    )


def _noise_report(text: str) -> str:
    """How clean is the excerpt? Leftover \\ / $ / { } signal incomplete LaTeX stripping."""
    return (
        f"backslash={text.count(chr(92))} dollar={text.count('$')} "
        f"brace={text.count('{') + text.count('}')}"
    )


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="arXiv full-text provider real-network probe")
    parser.add_argument("--ids", nargs="+", default=_DEFAULT_IDS, help="arXiv ids to fetch")
    parser.add_argument("--max-chars", type=int, default=2000, help="excerpt char cap")
    parser.add_argument("--preview", type=int, default=400, help="chars of excerpt to print")
    parser.add_argument("--doi", help="run the FULL chain for one work with this DOI")
    parser.add_argument("--oa-url", help="oa_url for the PDF fallback when running the full chain")
    parser.add_argument("--arxiv-id", help="arXiv id hint for the full-chain work")
    args = parser.parse_args(argv)

    # Full-chain mode: validate the non-arXiv providers (Europe PMC / CORE / oa_url PDF).
    if args.doi or args.oa_url or args.arxiv_id:
        sm = {}
        if args.oa_url:
            sm["oa_url"] = args.oa_url
        if args.arxiv_id:
            sm["arxiv_id"] = args.arxiv_id
        work = Work(
            id="probe:chain", title="", year=0, venue="", doi=args.doi,
            cited_by_count=0, abstract="", source_meta=sm,
        )
        chain = build_default_chain()
        print(f"chain: {[p.name for p in chain.providers]}  (CORE active: {bool(__import__('os').environ.get('CORE_API_KEY'))})")
        ft = chain.resolve(work)
        if ft is None:
            print("[miss] no provider resolved full text for this work")
            return 1
        print(f"[ok] resolved by source={ft.source} id={ft.source_id} url={ft.url}")
        print(f"     chars={ft.char_count} truncated={ft.truncated} | noise: {_noise_report(ft.text)}")
        print(f"     preview: {ft.text[: args.preview]}...")
        return 0

    # Real provider: keyless, 1 req/3s, real urllib fetch.
    provider = ArxivProvider(max_chars=args.max_chars)
    ok = 0
    for arxiv_id in args.ids:
        work = _work_for(arxiv_id)
        derived = extract_arxiv_id(work)
        print(f"\n=== {arxiv_id} (derived id: {derived}) ===")
        try:
            ft = provider.resolve_fulltext(work)
        except Exception as exc:  # network or parse failure
            print(f"[error] resolve failed: {exc}")
            continue
        if ft is None:
            print("[miss] no full text resolved (PDF-only source, or fetch/parse failed)")
            continue
        ok += 1
        print(f"[ok] source={ft.source} id={ft.source_id} url={ft.url}")
        print(f"     chars={ft.char_count} truncated={ft.truncated} | noise: {_noise_report(ft.text)}")
        preview = ft.text[: args.preview].replace("\n", " ")
        print(f"     preview: {preview}...")

    print(f"\n[summary] resolved {ok}/{len(args.ids)} arXiv full texts")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
