"""Local per-work-id cache for resolved full text (and misses).

Stored under a .gitignore'd directory (default data/fulltext/). Caching the MISS as well as
the hit is deliberate: a saturated re-run must not re-hammer arXiv for works that have no
resolvable source. Each entry is a small JSON file; the format is forward-compatible (a
`resolved` flag + the FullText fields) so later providers can reuse it unchanged.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, Tuple

from src.fulltext.base import FullText

_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def _safe_name(work_id: str) -> str:
    """Map a work id (often an OpenAlex URL) to a filesystem-safe filename stem."""
    tail = work_id.rsplit("/", 1)[-1] or work_id
    safe = _SAFE.sub("_", tail)
    return safe or "work"


class FulltextCache:
    def __init__(self, cache_dir: str = "data/fulltext") -> None:
        self.cache_dir = Path(cache_dir)

    def _path(self, work_id: str) -> Path:
        return self.cache_dir / f"{_safe_name(work_id)}.json"

    def lookup(self, work_id: str) -> Tuple[bool, Optional[FullText]]:
        """Return (cached, fulltext). cached=False means the work is not in the cache yet.

        cached=True with fulltext=None is a recorded MISS (do not re-fetch).
        """
        path = self._path(work_id)
        if not path.exists():
            return False, None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False, None
        if not isinstance(data, dict) or not data.get("resolved"):
            return True, None
        ft = data.get("fulltext") or {}
        return True, FullText(
            work_id=str(ft.get("work_id", work_id)),
            source=str(ft.get("source", "")),
            source_id=str(ft.get("source_id", "")),
            url=str(ft.get("url", "")),
            text=str(ft.get("text", "")),
            char_count=int(ft.get("char_count", 0) or 0),
            fetched_at=str(ft.get("fetched_at", "")),
            truncated=bool(ft.get("truncated", False)),
        )

    def store(self, work_id: str, fulltext: Optional[FullText]) -> None:
        path = self._path(work_id)
        if fulltext is None:
            payload = {"work_id": work_id, "resolved": False, "fulltext": None}
        else:
            payload = {
                "work_id": work_id,
                "resolved": True,
                "fulltext": {
                    "work_id": fulltext.work_id,
                    "source": fulltext.source,
                    "source_id": fulltext.source_id,
                    "url": fulltext.url,
                    "text": fulltext.text,
                    "char_count": fulltext.char_count,
                    "fetched_at": fulltext.fetched_at,
                    "truncated": fulltext.truncated,
                },
            }
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # cache is best-effort; a write failure must not break resolution


__all__ = ["FulltextCache"]
