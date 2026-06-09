"""Minimal GitHub REST API client."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


class GitHubError(RuntimeError):
    """Raised when the GitHub API request fails."""


@dataclass
class GitHubConfig:
    base_url: str = "https://api.github.com"
    token: Optional[str] = None
    timeout_sec: int = 20
    user_agent: str = "contra-cli/0.1"


class GitHubClient:
    def __init__(self, config: Optional[GitHubConfig] = None) -> None:
        self.config = config or GitHubConfig(token=os.getenv("GITHUB_TOKEN"))

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.config.user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return headers

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url = f"{url}?{query}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubError(f"http {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GitHubError(f"network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise GitHubError("invalid json from GitHub API") from exc
