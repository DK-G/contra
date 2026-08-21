"""Retry behaviour of OpenAlexClient.get (F-11).

A transient 429 from the shared pool must not abort a collection run — the caller cannot
distinguish that failure from a genuine zero harvest. Non-transient 4xx must still fail
immediately: retrying a wrong request only repeats the mistake.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from src.openalex.client import OpenAlexClient, OpenAlexConfig, OpenAlexError


def _client(max_retries: int = 2) -> OpenAlexClient:
    cfg = OpenAlexConfig(min_interval_sec=0.0, max_retries=max_retries, retry_backoff_sec=0.0)
    c = OpenAlexClient(cfg)
    c._sleep = lambda s: None  # no real waiting in tests
    return c


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.openalex.org/works", code, "err", {}, io.BytesIO(b""))


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._data = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None


def _patch_urlopen(monkeypatch, outcomes: list) -> list:
    """Each outcome is either an Exception to raise or a dict payload to return."""
    calls: list = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeResponse(outcome)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def test_transient_429_is_retried_and_succeeds(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [_http_error(429), {"results": []}])
    assert _client().get({"per-page": 1}) == {"results": []}
    assert len(calls) == 2


def test_5xx_is_retried(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [_http_error(503), _http_error(502), {"ok": True}])
    assert _client().get({}) == {"ok": True}
    assert len(calls) == 3


def test_retries_are_bounded(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [_http_error(429)])
    with pytest.raises(OpenAlexError) as exc:
        _client(max_retries=2).get({})
    assert "after 3 attempts" in str(exc.value)
    assert len(calls) == 3


def test_non_transient_4xx_fails_immediately(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [_http_error(403)])
    with pytest.raises(OpenAlexError):
        _client().get({})
    assert len(calls) == 1  # no retry on a request that is actually wrong


def test_timeout_class_errors_are_retried(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [TimeoutError("timed out"), {"ok": True}])
    assert _client().get({}) == {"ok": True}
    assert len(calls) == 2


def test_zero_retries_keeps_old_single_shot_behaviour(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [_http_error(429)])
    with pytest.raises(OpenAlexError):
        _client(max_retries=0).get({})
    assert len(calls) == 1
