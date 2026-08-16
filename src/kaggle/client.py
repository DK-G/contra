"""Minimal Kaggle public API (v1) client.

Mirrors :class:`src.hf.client.HFClient` in shape so the Track A collector can add
Kaggle as a third practical-anchor source alongside GitHub and Hugging Face.

Unlike the Hub (public read needs no token) or GitHub (token optional), the Kaggle
API requires credentials **even to read public datasets/notebooks**. So this client
exposes :attr:`has_credentials`; the collector uses it to *silently skip* Kaggle when
no credentials are configured — keeping contra's "runs with no key" ergonomics intact.

Two credential formats are supported (the same ``/api/v1/...`` endpoints accept both,
differing only in the ``Authorization`` header):

- **New API token** (Bearer) — the single ``KGAT_...`` token Kaggle's settings page
  issues by default. Read from the ``KAGGLE_API_TOKEN`` env var, then
  ``~/.kaggle/access_token``. Sent as ``Authorization: Bearer <token>``.
- **Legacy credentials** (Basic) — ``username`` + ``key``. Read from the
  ``KAGGLE_USERNAME`` + ``KAGGLE_KEY`` env vars, then ``~/.kaggle/kaggle.json``
  (the file the legacy Kaggle CLI writes). Sent as ``Authorization: Basic <b64>``.

The new token wins when both are present. One access shape is exposed:
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


def _load_credentials() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolve (api_token, username, key).

    New-format Bearer token first (``KAGGLE_API_TOKEN`` env, then ``~/.kaggle/access_token``),
    then legacy Basic creds (``KAGGLE_USERNAME``/``KAGGLE_KEY`` env, then ``~/.kaggle/kaggle.json``).
    """
    api_token = os.getenv("KAGGLE_API_TOKEN")
    if not api_token:
        try:
            token_path = Path.home() / ".kaggle" / "access_token"
            if token_path.is_file():
                api_token = token_path.read_text(encoding="utf-8").strip() or None
        except OSError:
            pass

    username = os.getenv("KAGGLE_USERNAME")
    key = os.getenv("KAGGLE_KEY")
    if not (username and key):
        try:
            json_path = Path.home() / ".kaggle" / "kaggle.json"
            if json_path.is_file():
                data = json.loads(json_path.read_text(encoding="utf-8"))
                username = data.get("username") or username
                key = data.get("key") or key
        except (OSError, json.JSONDecodeError):
            pass

    return api_token, username, key


@dataclass
class KaggleConfig:
    base_url: str = "https://www.kaggle.com/api/v1"
    api_token: Optional[str] = None
    username: Optional[str] = None
    key: Optional[str] = None
    timeout_sec: int = 20
    user_agent: str = "contra-cli/0.1"


class KaggleClient:
    def __init__(self, config: Optional[KaggleConfig] = None) -> None:
        if config is None:
            api_token, username, key = _load_credentials()
            config = KaggleConfig(api_token=api_token, username=username, key=key)
        self.config = config

    @property
    def has_credentials(self) -> bool:
        """True when a new-format token, or a full legacy username+key pair, is available."""
        return bool(self.config.api_token or (self.config.username and self.config.key))

    def _headers(self, accept: str) -> Dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": self.config.user_agent,
        }
        if self.config.api_token:
            headers["Authorization"] = f"Bearer {self.config.api_token}"
        elif self.config.username and self.config.key:
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
