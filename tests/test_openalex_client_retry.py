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
    calls = _patch_urlopen(monkeypatch, [_http_error(503)])
    with pytest.raises(OpenAlexError) as exc:
        _client(max_retries=2).get({})
    assert "after 3 attempts" in str(exc.value)
    assert len(calls) == 3


def test_exhausted_429_is_named_as_a_shared_quota_not_a_bad_query(monkeypatch):
    """F-28 (2026-09-12): a byserendipity run starved the bybridge run that followed it, and
    the generic message let the caller read an IP-level quota as a property of the theme."""
    calls = _patch_urlopen(monkeypatch, [_http_error(429)])
    with pytest.raises(OpenAlexError) as exc:
        _client(max_retries=2).get({})
    msg = str(exc.value)
    assert "429" in msg and "クォータ" in msg and "時間をおいて" in msg
    assert "F-28" in msg
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


# --- F-11(3): run stats — "zero harvest" vs "fetch failure" must be separable ---

from src.openalex.client import RUN_STATS, reset_run_stats, run_stats_caveat


def test_clean_run_has_no_caveat(monkeypatch):
    reset_run_stats()
    _patch_urlopen(monkeypatch, [{"ok": True}])
    _client().get({})
    assert run_stats_caveat() == ""
    assert RUN_STATS == {"requests": 1, "retried": 0, "gave_up": 0, "budget": None}


def test_recovered_retry_is_reported_as_recovered(monkeypatch):
    reset_run_stats()
    _patch_urlopen(monkeypatch, [_http_error(429), {"ok": True}])
    _client().get({})
    caveat = run_stats_caveat()
    assert "リトライ 1 回" in caveat and "回復済み" in caveat
    assert "収穫ゼロ" not in caveat            # recovered runs don't cast doubt on the result


def test_exhausted_retries_warn_about_false_zero_harvest(monkeypatch):
    reset_run_stats()
    _patch_urlopen(monkeypatch, [_http_error(429)])
    with pytest.raises(OpenAlexError):
        _client().get({})
    caveat = run_stats_caveat()
    assert "リトライ上限まで失敗 1 件" in caveat
    assert "収穫ゼロ" in caveat                # the caller must not misread this as saturation


def test_stats_accumulate_across_clients_and_reset(monkeypatch):
    reset_run_stats()
    _patch_urlopen(monkeypatch, [{"ok": True}])
    _client().get({})
    _client().get({})                          # a second client, same run
    assert RUN_STATS["requests"] == 2
    reset_run_stats()
    assert RUN_STATS == {"requests": 0, "retried": 0, "gave_up": 0, "budget": None}


# --- F-29 (2026-09-16): the daily USD budget is not the burst limit -----------------------

def _http_error_with(code: int, headers: dict) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.openalex.org/works", code, "err", headers, io.BytesIO(b""))


# The exact headers seihai's independent curl probe read on 2026-09-16.
_OBSERVED_0916 = {
    "Retry-After": "6394", "X-RateLimit-Limit-USD": "0.1", "X-RateLimit-Remaining-USD": "0.0008",
    "X-RateLimit-Credits-Required": "10", "X-RateLimit-Cost-Required-USD": "0.001",
    "X-RateLimit-Prepaid-Remaining-USD": "0",
}


def test_exhausted_daily_budget_is_not_retried_and_names_the_wait_in_hours(monkeypatch):
    from src.openalex.client import reset_run_stats
    reset_run_stats()
    calls = _patch_urlopen(monkeypatch, [_http_error_with(429, _OBSERVED_0916)])
    with pytest.raises(OpenAlexError) as exc:
        _client(max_retries=2).get({})
    msg = str(exc.value)
    assert len(calls) == 1                         # no useless retries against an hours-long wait
    assert "日次予算" in msg and "F-29" in msg
    assert "6394" in msg and "1.8 時間" in msg     # the caller must not read "wait" as seconds
    assert "0.0008" in msg and "0.001" in msg
    assert "09:00 JST" in msg


def test_burst_429_with_budget_left_is_still_retried(monkeypatch):
    burst = dict(_OBSERVED_0916, **{"X-RateLimit-Remaining-USD": "0.05", "Retry-After": "2"})
    calls = _patch_urlopen(monkeypatch, [_http_error_with(429, burst), {"results": []}])
    assert _client(max_retries=2).get({}) == {"results": []}
    assert len(calls) == 2


def test_exhausted_burst_429_names_retry_after_when_present(monkeypatch):
    burst = dict(_OBSERVED_0916, **{"X-RateLimit-Remaining-USD": "0.05", "Retry-After": "30"})
    _patch_urlopen(monkeypatch, [_http_error_with(429, burst)])
    with pytest.raises(OpenAlexError) as exc:
        _client(max_retries=1).get({})
    assert "F-28" in str(exc.value) and "Retry-After 30 秒" in str(exc.value)


def test_429_without_meter_headers_keeps_old_behaviour(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [_http_error(429)])
    with pytest.raises(OpenAlexError):
        _client(max_retries=2).get({})
    assert len(calls) == 3


def test_meter_is_read_from_successful_responses_and_warns_when_low(monkeypatch):
    from src.openalex.client import RUN_STATS, low_budget_caveat, reset_run_stats

    class _MeteredResponse(_FakeResponse):
        def __init__(self, payload, headers):
            super().__init__(payload)
            self.headers = headers

    def fake_urlopen(req, timeout=None):
        return _MeteredResponse({"results": []}, {
            "X-RateLimit-Remaining-USD": "0.012", "X-RateLimit-Limit-USD": "0.1",
            "X-RateLimit-Cost-USD": "0.001", "X-RateLimit-Reset": "3600"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    reset_run_stats()
    _client().get({})
    assert RUN_STATS["budget"]["remaining_usd"] == 0.012
    line = low_budget_caveat()
    assert "あと約 12 回" in line and "seihai" in line
    RUN_STATS["budget"]["remaining_usd"] = 0.09
    assert low_budget_caveat() == ""               # a healthy meter adds nothing to the output
    reset_run_stats()


# --- F-33 (2026-09-25): 504 streaks on search.semantic — patience, not more quick retries ---


def _patient_client(patience: float, interval: float = 5.0, max_retries: int = 2):
    cfg = OpenAlexConfig(min_interval_sec=0.0, max_retries=max_retries, retry_backoff_sec=0.0,
                         gateway_patience_sec=patience, gateway_retry_interval_sec=interval)
    c = OpenAlexClient(cfg)
    clock = {"t": 0.0}
    c._now = lambda: clock["t"]

    def fake_sleep(s):
        clock["t"] += s

    c._sleep = fake_sleep
    return c


def test_patience_off_keeps_three_attempts_on_504(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [_http_error(504)])
    c = _patient_client(0.0)
    with pytest.raises(OpenAlexError) as exc:
        c.get({})
    assert len(calls) == 3
    assert "F-33" not in str(exc.value)
    assert c.last_gateway_wait == {"gateway_504": 3, "recovered": False, "waited_sec": 0.0}


def test_504_streak_is_waited_out_and_reported_as_recovered(monkeypatch):
    """The 2026-09-25 probe: 504 x N then 200 — three quick attempts fall inside the streak."""
    calls = _patch_urlopen(monkeypatch, [_http_error(504)] * 6 + [{"ok": True}])
    c = _patient_client(60.0, interval=5.0)
    assert c.get({}) == {"ok": True}
    assert len(calls) == 7
    assert c.last_gateway_wait == {"gateway_504": 6, "recovered": True, "waited_sec": 20.0}


def test_patience_is_bounded_and_named_in_the_error(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [_http_error(504)])
    c = _patient_client(30.0, interval=5.0)
    with pytest.raises(OpenAlexError) as exc:
        c.get({})
    # 3 normal attempts, then one every 5 s while (elapsed + 5) <= 30 -> 6 more
    assert len(calls) == 9
    assert "F-33" in str(exc.value) and "504 を 9 回" in str(exc.value)
    assert c.last_gateway_wait["recovered"] is False


def test_patience_does_not_extend_429_or_other_5xx(monkeypatch):
    for code in (429, 503):
        calls = _patch_urlopen(monkeypatch, [_http_error(code)])
        with pytest.raises(OpenAlexError):
            _patient_client(120.0).get({})
        assert len(calls) == 3, code


def test_clean_call_leaves_no_gateway_record(monkeypatch):
    _patch_urlopen(monkeypatch, [{"ok": True}])
    c = _patient_client(120.0)
    c.get({})
    assert c.last_gateway_wait is None
