"""Minimal Hugging Face Hub API client.

Mirrors :class:`src.github.client.GitHubClient` in shape so the Track A collector
can swap GitHub for Hugging Face as a practical-anchor source. Read access to the
public Hub API needs no token; ``HF_TOKEN`` is honoured when present (raises rate
limits and reaches gated/private repos the caller is allowed to see).

Two access shapes are exposed:
- ``get()``   — JSON endpoints under ``/api/...`` (search returns a JSON *array*).
- ``get_text()`` — raw text (model/dataset card README); returns "" on 404 so a
  missing card never aborts collection.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


class HFError(RuntimeError):
    """Raised when the Hugging Face Hub API request fails."""


@dataclass
class HFConfig:
    base_url: str = "https://huggingface.co"
    token: Optional[str] = None
    timeout_sec: int = 20
    user_agent: str = "contra-cli/0.1"


class HFClient:
    def __init__(self, config: Optional[HFConfig] = None) -> None:
        self.config = config or HFConfig(token=os.getenv("HF_TOKEN"))

    def _headers(self, accept: str) -> Dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": self.config.user_agent,
        }
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return headers

    def _build_url(self, path: str, params: Optional[Dict[str, Any]]) -> str:
        url = f"{self.config.base_url}{path}"
        if params:
            query = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}
            )
            if query:
                url = f"{url}?{query}"
        return url

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """GET a JSON endpoint. Hub search endpoints return a JSON array."""
        url = self._build_url(path, params)
        req = urllib.request.Request(
            url, headers=self._headers("application/json"), method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HFError(f"http {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise HFError(f"network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise HFError("invalid json from Hugging Face Hub API") from exc

    def get_text(self, path: str, params: Optional[Dict[str, Any]] = None) -> str:
        """GET raw text (e.g. a card README). Returns "" on 404 (missing card)."""
        url = self._build_url(path, params)
        req = urllib.request.Request(
            url, headers=self._headers("text/plain"), method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return ""
            detail = exc.read().decode("utf-8", errors="replace")
            raise HFError(f"http {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise HFError(f"network error: {exc.reason}") from exc
