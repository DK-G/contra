"""Tests for retry/backoff and exception conversion in openai_client.responses_create."""

import io
import urllib.error

import pytest

import src.openai_client as oc
from src.openai_client import OpenAIConfig, OpenAIError, responses_create


def _cfg(max_retries=2):
    # backoff_base 0 keeps the (patched) sleep deterministic and instant.
    return OpenAIConfig(api_key="test-key", max_retries=max_retries, backoff_base_sec=0.0)


class _FakeResp:
    """Minimal context-manager standing in for urlopen's return value."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def _http_error(code: int, detail: bytes = b"boom"):
    return urllib.error.HTTPError(
        url="https://api.openai.com/v1/responses",
        code=code,
        msg="err",
        hdrs=None,
        fp=io.BytesIO(detail),
    )


def _patch_urlopen(monkeypatch, side_effects):
    """side_effects: list of either Exception instances/classes or response bytes."""
    calls = {"n": 0}
    seq = list(side_effects)

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        item = seq.pop(0)
        if isinstance(item, BaseException) or (
            isinstance(item, type) and issubclass(item, BaseException)
        ):
            raise item
        return _FakeResp(item)

    monkeypatch.setattr(oc.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(oc.time, "sleep", lambda _s: None)
    return calls


def test_timeout_error_is_converted_not_propagated(monkeypatch):
    # Bare TimeoutError previously escaped OpenAIError and crashed the run.
    calls = _patch_urlopen(monkeypatch, [TimeoutError("read timed out")] * 3)
    with pytest.raises(OpenAIError):
        responses_create({"x": 1}, _cfg(max_retries=2))
    assert calls["n"] == 3  # initial try + 2 retries


def test_transient_timeout_then_success(monkeypatch):
    calls = _patch_urlopen(
        monkeypatch,
        [TimeoutError("t"), b'{"output_text": "ok"}'],
    )
    result = responses_create({"x": 1}, _cfg(max_retries=2))
    assert result["output_text"] == "ok"  # normalized response carries output_text
    assert calls["n"] == 2


def test_retryable_http_status_is_retried(monkeypatch):
    calls = _patch_urlopen(
        monkeypatch,
        [_http_error(429), _http_error(503), b'{"ok": true}'],
    )
    result = responses_create({"x": 1}, _cfg(max_retries=3))
    assert result.get("ok") is True  # normalization adds a usage block but preserves the body
    assert calls["n"] == 3


def test_non_retryable_http_status_raises_immediately(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [_http_error(401), b'{"ok": true}'])
    with pytest.raises(OpenAIError):
        responses_create({"x": 1}, _cfg(max_retries=3))
    assert calls["n"] == 1  # no retry on 401


def test_url_error_is_converted(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [urllib.error.URLError("dns")] * 2)
    with pytest.raises(OpenAIError):
        responses_create({"x": 1}, _cfg(max_retries=1))
    assert calls["n"] == 2
