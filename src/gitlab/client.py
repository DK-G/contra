"""Minimal GitLab REST API client."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


class GitLabError(RuntimeError):
    """Raised when the GitLab API request fails."""


@dataclass
class GitLabConfig:
    base_url: str = "https://gitlab.com/api/v4"
    token: Optional[str] = None
    timeout_sec: int = 20
    user_agent: str = "contra-cli/0.1"


class GitLabClient:
    def __init__(self, config: Optional[GitLabConfig] = None) -> None:
        self.config = config or GitLabConfig(token=os.getenv("GITLAB_TOKEN"))

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.config.user_agent,
        }
        if self.config.token:
            headers["PRIVATE-TOKEN"] = self.config.token
        return headers

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return json.loads(self.get_text(path, params=params))

    def get_text(self, path: str, params: Optional[Dict[str, Any]] = None) -> str:
        url = f"{self.config.base_url}{path}"
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url = f"{url}?{query}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitLabError(f"http {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GitLabError(f"network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise GitLabError("invalid json from GitLab API") from exc


def quote_project_id(project_id: str) -> str:
    return urllib.parse.quote(project_id, safe="")
