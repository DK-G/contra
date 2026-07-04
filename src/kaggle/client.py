"""Minimal Kaggle public API (v1) client.

Mirrors :class:`src.hf.client.HFClient` in shape so the Track A collector can add
Kaggle as a third practical-anchor source alongside GitHub and Hugging Face.

Unlike the Hub (public read needs no token) or GitHub (token optional), the Kaggle
API requires credentials **even to read public datasets/notebooks**. So this client
exposes :attr:`has_credentials`; the collector uses it to *silently skip* Kaggle when
no credentials are configured — keeping contra's "runs with no key" ergonomics intact.

Credentials are read (in order) from:
- the ``KAGGLE_USERNAME`` + ``KAGGLE_KEY`` environment variables, then
- ``~/.kaggle/kaggle.json`` (the file the official Kaggle CLI writes).

One access shape is exposed:
- ``get()`` — JSON endpoints under ``/api/v1/...`` (list endpoints return a JSON array).
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class KaggleError(RuntimeError):
    """Raised when the Kaggle API request fails."""


def _load_credentials() -> Tuple[Optional[str], Optional[str]]:
    """Resolve (username, key) from env vars, then ~/.kaggle/kaggle.json."""
    username = os.getenv("KAGGLE_USERNAME")
    key = os.getenv("KAGGLE_KEY")
    if username and key:
        return username, key
    try:
        path = Path.home() / ".kaggle" / "kaggle.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("username") or username, data.get("key") or key
    except (OSError, json.JSONDecodeError):
        pass
    return username, key


@dataclass
class KaggleConfig:
    base_url: str = "https://www.kaggle.com/api/v1"
    username: Optional[str] = None
    key: Optional[str] = None
    timeout_sec: int = 20
    user_agent: str = "contra-cli/0.1"


class KaggleClient:
    def __init__(self, config: Optional[KaggleConfig] = None) -> None:
        if config is None:
            username, key = _load_credentials()
            config = KaggleConfig(username=username, key=key)
        self.config = config

    @property
    def has_credentials(self) -> bool:
        """True only when both a username and key are available (basic-auth needs both)."""
        return bool(self.config.username and self.config.key)

    def _headers(self, accept: str) -> Dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": self.config.user_agent,
        }
        if self.has_credentials:
            raw = f"{self.config.username}:{self.config.key}".encode("utf-8")
            headers["Authorization"] = f"Basic {base64.b64encode(raw).decode('ascii')}"
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
        """GET a JSON endpoint. Kaggle list endpoints return a JSON array."""
        url = self._build_url(path, params)
        req = urllib.request.Request(
            url, headers=self._headers("application/json"), method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise KaggleError(f"http {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise KaggleError(f"network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise KaggleError("invalid json from Kaggle API") from exc
