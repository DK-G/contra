"""OpenAlex minimal HTTP client."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


class OpenAlexError(RuntimeError):
    pass


@dataclass
class OpenAlexConfig:
    base_url: str = "https://api.openalex.org/works"
    mailto: Optional[str] = None
    timeout_sec: int = 20
    min_interval_sec: float = 0.2


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

    def get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._rate_limit()
        url = self._build_url(params)
        req = urllib.request.Request(url, headers={"User-Agent": "contra-cli/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as res:
                data = res.read().decode("utf-8")
        except Exception as exc:  # pragma: no cover - network errors
            raise OpenAlexError(f"request failed: {exc}") from exc
        finally:
            self._last_call_at = time.time()

        try:
            return json.loads(data)
        except json.JSONDecodeError as exc:
            raise OpenAlexError(f"invalid json response: {exc}") from exc


__all__ = ["OpenAlexClient", "OpenAlexConfig", "OpenAlexError"]
