"""Polite HTTP fetcher shared by the non-arXiv full-text providers.

stdlib urllib only (spec.md §4). Rate-limited, single sequential connection, bounded retry
with exponential backoff, returns None on failure (providers then fall through the chain).
The `opener` seam lets tests inject a fake transport without touching the network.
"""

from __future__ import annotations

import time
import urllib.request
from typing import Callable, Dict, Optional

_USER_AGENT = "contra-cli/0.1 (full-text provider; mailto via OpenAlex politepool)"


class HttpFetcher:
    def __init__(
        self,
        *,
        min_interval_sec: float = 0.34,
        timeout_sec: int = 30,
        max_retries: int = 3,
        user_agent: str = _USER_AGENT,
        opener: Optional[Callable[[str, Dict[str, str], int], bytes]] = None,
    ) -> None:
        self.min_interval_sec = min_interval_sec
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.user_agent = user_agent
        self._opener = opener
        self._last_call_at = 0.0

    def _open(self, url: str, headers: Dict[str, str], timeout: int) -> bytes:
        if self._opener is not None:
            return self._opener(url, headers, timeout)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as res:  # pragma: no cover - network
            return res.read()

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_call_at
        if elapsed < self.min_interval_sec:
            time.sleep(self.min_interval_sec - elapsed)

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[bytes]:
        merged = {"User-Agent": self.user_agent}
        if headers:
            merged.update(headers)
        for attempt in range(max(1, self.max_retries)):
            self._rate_limit()
            try:
                return self._open(url, merged, self.timeout_sec)
            except Exception:  # pragma: no cover - network error path
                if attempt + 1 >= self.max_retries:
                    return None
                time.sleep(min(2 ** attempt, 8))
            finally:
                self._last_call_at = time.time()
        return None


__all__ = ["HttpFetcher"]
