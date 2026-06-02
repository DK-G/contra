"""Minimal multi-provider LLM client (OpenAI Responses + Anthropic Messages).

Call sites build a single OpenAI-Responses-shaped payload
``{model, input:[{role,content}], temperature}`` and use responses_create +
extract_output_text. The provider is chosen by the model name, and non-OpenAI
responses are normalized back to ``{output_text, usage}`` so the call sites and
extract_output_text / usage accounting stay unchanged.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


class OpenAIError(RuntimeError):
    pass


# HTTP status codes worth retrying (transient server/rate-limit conditions).
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# o-series reasoning models (o1/o3/o4-mini, ...) reject sampling params like temperature/top_p
# on the Responses API; they self-manage sampling. Detect by the o<digit> name prefix so the
# scoring/judge payloads (which set temperature for gpt-4o-mini) work unchanged when swapped.
_REASONING_MODEL_RE = re.compile(r"^o\d", re.IGNORECASE)

# max output tokens for Anthropic (required there; OpenAI Responses does not need it). Scoring a
# chunk of 8 papers with Japanese rationales fits well under this; only actual output is billed.
_ANTHROPIC_MAX_TOKENS = 4096
_ANTHROPIC_VERSION = "2023-06-01"


def _is_reasoning_model(model: str) -> bool:
    return bool(_REASONING_MODEL_RE.match(model or ""))


def _provider_for_model(model: str) -> str:
    m = (model or "").lower()
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gemini"):
        return "google"
    return "openai"


@dataclass
class OpenAIConfig:
    api_key: str = ""  # resolved per-provider at request time when empty
    base_url: str = "https://api.openai.com/v1"
    timeout_sec: int = 60
    max_retries: int = 3
    backoff_base_sec: float = 1.0


def _require_key(env_name: str) -> str:
    key = os.getenv(env_name, "")
    if not key:
        raise OpenAIError(f"{env_name} is not set")
    return key


# Process-wide token accounting (for per-run cost visibility). Accumulated from each response's
# usage block. reasoning_tokens are a subset of output_tokens (billed as output) on o-series;
# cached_input_tokens are input tokens served from cache (cheaper) on both providers.
_USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0,
          "cached_input_tokens": 0}


def _accumulate_usage(usage: Dict[str, Any]) -> None:
    _USAGE["calls"] += 1
    _USAGE["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
    _USAGE["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
    _USAGE["reasoning_tokens"] += int(usage.get("reasoning_tokens", 0) or 0)
    _USAGE["cached_input_tokens"] += int(usage.get("cached_input_tokens", 0) or 0)


def get_usage() -> Dict[str, int]:
    return dict(_USAGE)


def reset_usage() -> None:
    for k in _USAGE:
        _USAGE[k] = 0


def _sanitize_openai_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Drop params a reasoning model would reject. Returns a shallow copy when changed."""
    if _is_reasoning_model(str(payload.get("model", ""))):
        return {k: v for k, v in payload.items() if k not in ("temperature", "top_p")}
    return payload


# Back-compat alias (older tests import _sanitize_payload).
_sanitize_payload = _sanitize_openai_payload


def _to_anthropic(payload: Dict[str, Any]) -> Tuple[str, Dict[str, str], bytes]:
    """Translate the OpenAI-Responses payload into an Anthropic Messages request.

    role=="system" messages become the top-level (cacheable) system block; the rest map to
    user/assistant messages. temperature is clamped to Anthropic's 0-1 range.
    """
    sys_parts: List[str] = []
    messages: List[dict] = []
    for msg in payload.get("input", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            sys_parts.append(content)
        else:
            messages.append({"role": "assistant" if role == "assistant" else "user",
                             "content": content})
    body: Dict[str, Any] = {
        "model": payload["model"],
        "max_tokens": int(payload.get("max_tokens", _ANTHROPIC_MAX_TOKENS)),
        "messages": messages,
    }
    if sys_parts:
        # Structured system with cache_control: the (large, repeated) system prompt is cached so
        # repeated scoring chunks pay the input cost once. Falls back gracefully if not cached.
        body["system"] = [{
            "type": "text",
            "text": "\n\n".join(sys_parts),
            "cache_control": {"type": "ephemeral"},
        }]
    temp = payload.get("temperature")
    if temp is not None:
        body["temperature"] = max(0.0, min(1.0, float(temp)))
    headers = {
        "x-api-key": _require_key("ANTHROPIC_API_KEY"),
        "anthropic-version": _ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    return "https://api.anthropic.com/v1/messages", headers, json.dumps(body).encode("utf-8")


def _normalize_anthropic(raw: Dict[str, Any]) -> Dict[str, Any]:
    text = "".join(p.get("text", "") for p in raw.get("content", []) if p.get("type") == "text")
    u = raw.get("usage") or {}
    return {
        "output_text": text,
        "usage": {
            # cache_read tokens are NOT included in input_tokens by Anthropic; add them so the
            # meter reflects total input volume, and track the cached portion for cost.
            "input_tokens": int(u.get("input_tokens", 0) or 0)
            + int(u.get("cache_read_input_tokens", 0) or 0)
            + int(u.get("cache_creation_input_tokens", 0) or 0),
            "output_tokens": int(u.get("output_tokens", 0) or 0),
            "reasoning_tokens": 0,
            "cached_input_tokens": int(u.get("cache_read_input_tokens", 0) or 0),
        },
    }


def _normalize_openai(raw: Dict[str, Any]) -> Dict[str, Any]:
    u = raw.get("usage") or {}
    raw["usage"] = {
        "input_tokens": int(u.get("input_tokens", 0) or 0),
        "output_tokens": int(u.get("output_tokens", 0) or 0),
        "reasoning_tokens": int((u.get("output_tokens_details") or {}).get("reasoning_tokens", 0) or 0),
        "cached_input_tokens": int((u.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0),
    }
    return raw


def _build_request(payload: Dict[str, Any], cfg: OpenAIConfig) -> Tuple[str, str, Dict[str, str], bytes]:
    provider = _provider_for_model(str(payload.get("model", "")))
    if provider == "anthropic":
        url, headers, body = _to_anthropic(payload)
        return provider, url, headers, body
    if provider == "google":
        raise OpenAIError("google/gemini provider not implemented yet")
    # openai (default)
    url = f"{cfg.base_url}/responses"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.api_key or _require_key('OPENAI_API_KEY')}",
    }
    body = json.dumps(_sanitize_openai_payload(payload)).encode("utf-8")
    return provider, url, headers, body


def responses_create(payload: Dict[str, Any], config: OpenAIConfig | None = None) -> Dict[str, Any]:
    cfg = config or OpenAIConfig()
    provider, url, headers, data = _build_request(payload, cfg)
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)

    last_err: Exception | None = None
    for attempt in range(cfg.max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=cfg.timeout_sec) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                normalized = _normalize_anthropic(raw) if provider == "anthropic" else _normalize_openai(raw)
                _accumulate_usage(normalized.get("usage") or {})
                return normalized
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            last_err = OpenAIError(f"{provider} http error: {exc.code} {detail}")
            if exc.code not in _RETRYABLE_STATUS:
                raise last_err from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # Socket read timeouts surface as bare TimeoutError/OSError and are NOT
            # wrapped in URLError, so they must be caught here or they escape OpenAIError.
            last_err = OpenAIError(f"{provider} request failed: {exc}")

        if attempt < cfg.max_retries:
            time.sleep(cfg.backoff_base_sec * (2 ** attempt))

    raise last_err if last_err is not None else OpenAIError(f"{provider} request failed")


def extract_output_text(response: Dict[str, Any]) -> str:
    # Both providers are normalized to carry output_text; keep the Responses fallback for safety.
    text = response.get("output_text")
    if isinstance(text, str) and text:
        return text
    output = response.get("output") or []
    for item in output:
        if item.get("type") == "message":
            for part in item.get("content") or []:
                if part.get("type") == "output_text":
                    return part.get("text") or ""
    return ""


__all__ = [
    "OpenAIConfig", "OpenAIError", "responses_create", "extract_output_text",
    "get_usage", "reset_usage",
]
