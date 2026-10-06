"""byrepo hyphen probe (F-42): how GitHub repository search reads a hyphenated keyword.

Search-only (the search quota is 10 requests/minute unauthenticated and separate from the
60/hour core quota), so it never costs README fetches. For each term it sends three spellings
— bare (`trend-following`), quoted with the hyphen (`"trend-following"`), quoted with a space
(`"trend following"`) — and prints the match count plus how many of the top results carry the
phrase on their identity surface (name / description / topics), judged by the same normaliser
byrepo's relevance uses.

Usage: python scripts/byrepo_hyphen_probe.py trend-following regime-filter [--top 30]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.github.client import GitHubClient, GitHubError  # noqa: E402
from src.pipeline.git_collect import _pushed_qualifier  # noqa: E402
from src.pipeline.theme_fit import normalize, phrase_in  # noqa: E402

PAUSE_SEC = 7.0   # 10 searches/minute


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("terms", nargs="+")
    ap.add_argument("--top", type=int, default=30)
    ns = ap.parse_args()
    gh = GitHubClient()
    for term in ns.terms:
        spaced = term.replace("-", " ")
        needle = normalize(term)
        for label, token in (("bare", term), ("quoted-hyphen", f'"{term}"'), ("quoted-space", f'"{spaced}"')):
            query = f"{token} in:name,description,readme {_pushed_qualifier()}"
            try:
                payload = gh.get("/search/repositories", {"q": query, "per_page": ns.top})
            except GitHubError as exc:
                print(f"{term:22} {label:14} ERROR {exc}")
                time.sleep(PAUSE_SEC)
                continue
            items = payload.get("items") or []
            strong = sum(
                1 for it in items
                if phrase_in(normalize(" ".join([str(it.get("full_name") or ""), str(it.get("description") or ""),
                                                 " ".join(it.get("topics") or [])])), needle))
            names = ", ".join(str(it.get("full_name")) for it in items[:4])
            print(f"{term:22} {label:14} total={payload.get('total_count'):>9,}  "
                  f"identity-surface match in top {len(items)}: {strong:>2}  | {names}")
            time.sleep(PAUSE_SEC)


if __name__ == "__main__":
    main()
