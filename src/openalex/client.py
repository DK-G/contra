"""OpenAlex minimal HTTP client."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


class OpenAlexError(RuntimeError):
    pass


# Transient statuses worth one more try (F-11): 429 = shared-pool rate limit (observed
# in the wild as a one-off that clears within a second), 5xx = server-side hiccups.
# 4xx other than 429 mean the REQUEST is wrong — retrying those just repeats the mistake.
_RETRY_STATUSES = {429, 500, 502, 503, 504}


@dataclass
class OpenAlexConfig:
    base_url: str = "https://api.openalex.org/works"
    mailto: Optional[str] = None
    timeout_sec: int = 20
    min_interval_sec: float = 0.2
    max_retries: int = 2            # extra attempts on transient failures (0 = old behaviour)
    retry_backoff_sec: float = 1.0  # first retry waits this long, second waits double


class OpenAlexClient:
    def __init__(self, config: Optional[OpenAlexConfig] = None) -> None:
        self.config = config or OpenAlexConfig()
        self._last_call_at = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_call_at
        if elapsed < self.config.min_interval_sec:
            time.sleep(self.config.min_interval_sec - elapsed)

    def _build_url(self, params: Dict[str, Any]) -> str:
        if self.config.mailto:
            params = dict(params)
            params["mailto"] = self.config.mailto
        query = urllib.parse.urlencode(params, doseq=True)
        return f"{self.config.base_url}?{query}"

    def _sleep(self, seconds: float) -> None:  # separated so tests can stub the wait out
        time.sleep(seconds)

    def get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """One GET with bounded retries on transient failures (429/5xx, timeouts).

        F-11 (``docs/field_observations_seihai.md``): without retries a one-off 429 from the
        shared anonymous pool aborts the collection mid-run, and the caller cannot tell that
        "zero harvest" from a genuine empty result. Two backoff retries absorb exactly that
        class of failure; a request that is actually wrong (other 4xx) still fails immediately.
        """
        url = self._build_url(params)
        req = urllib.request.Request(url, headers={"User-Agent": "contra-cli/0.1"})
        attempts = max(0, self.config.max_retries) + 1
        last_exc: Optional[Exception] = None
        for attempt in range(attempts):
            if attempt:
                self._sleep(self.config.retry_backoff_sec * (2 ** (attempt - 1)))
            self._rate_limit()
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as res:
                    data = res.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code in _RETRY_STATUSES:
                    continue
                raise OpenAlexError(f"request failed: {exc}") from exc
            except Exception as exc:  # pragma: no cover - network errors
                last_exc = exc       # timeouts / connection resets are transient too
                continue
            finally:
                self._last_call_at = time.time()

            try:
                return json.loads(data)
            except json.JSONDecodeError as exc:
                raise OpenAlexError(f"invalid json response: {exc}") from exc
        raise OpenAlexError(
            f"request failed after {attempts} attempts: {last_exc}"
        ) from last_exc


__all__ = ["OpenAlexClient", "OpenAlexConfig", "OpenAlexError"]
