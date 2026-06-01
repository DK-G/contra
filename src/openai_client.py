"""Minimal OpenAI Responses API client."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict


class OpenAIError(RuntimeError):
    pass


# HTTP status codes worth retrying (transient server/rate-limit conditions).
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass
class OpenAIConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    timeout_sec: int = 60
    max_retries: int = 3
    backoff_base_sec: float = 1.0


def _require_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise OpenAIError("OPENAI_API_KEY is not set")
    return api_key


def responses_create(payload: Dict[str, Any], config: OpenAIConfig | None = None) -> Dict[str, Any]:
    cfg = config or OpenAIConfig(api_key=_require_api_key())
    url = f"{cfg.base_url}/responses"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {cfg.api_key}")

    last_err: Exception | None = None
    for attempt in range(cfg.max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=cfg.timeout_sec) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            last_err = OpenAIError(f"openai http error: {exc.code} {detail}")
            if exc.code not in _RETRYABLE_STATUS:
                raise last_err from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # Socket read timeouts surface as bare TimeoutError/OSError and are NOT
            # wrapped in URLError, so they must be caught here or they escape OpenAIError.
            last_err = OpenAIError(f"openai request failed: {exc}")

        if attempt < cfg.max_retries:
            time.sleep(cfg.backoff_base_sec * (2 ** attempt))

    raise last_err if last_err is not None else OpenAIError("openai request failed")


def extract_output_text(response: Dict[str, Any]) -> str:
    # Responses API returns output items; use output_text convenience if present.
    text = response.get("output_text")
    if isinstance(text, str) and text:
        return text
    output = response.get("output") or []
    for item in output:
        if item.get("type") == "message":
            contents = item.get("content") or []
            for part in contents:
                if part.get("type") == "output_text":
                    return part.get("text") or ""
    return ""


__all__ = ["OpenAIConfig", "OpenAIError", "responses_create", "extract_output_text"]
