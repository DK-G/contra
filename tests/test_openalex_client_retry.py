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


# --- F-36 (2026-09-27): "searches left" must be priced at the search cost -----------------
# The meter divided the remaining USD by the LAST response's cost. A search costs $0.001
# (10 credits) but a filter list call costs $0.0001 (1 credit; probed 2026-09-27:
# X-RateLimit-Cost-USD 0.0001 / Credits-Used 1), so the same day read "$0.097 -> 約 97 回"
# after byserendipity (last request a semantic search) and "$0.0838 -> 約 838 回" after
# bybridge (last request a filter call).

class _HeaderedResponse(_FakeResponse):
    def __init__(self, payload, headers):
        super().__init__(payload)
        self.headers = headers


def _metered_sequence(monkeypatch, metas):
    it = iter(metas)

    def fake_urlopen(req, timeout=None):
        return _HeaderedResponse({"results": []}, next(it))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def test_searches_left_is_priced_at_the_search_cost_not_the_last_request(monkeypatch):
    from src.openalex.client import RUN_STATS, budget_line, reset_run_stats
    _metered_sequence(monkeypatch, [
        {"X-RateLimit-Remaining-USD": "0.097", "X-RateLimit-Limit-USD": "0.1",
         "X-RateLimit-Cost-USD": "0.001"},                      # search.semantic
        {"X-RateLimit-Remaining-USD": "0.0838", "X-RateLimit-Limit-USD": "0.1",
         "X-RateLimit-Cost-USD": "0.0001"},                     # cites: filter list
    ])
    reset_run_stats()
    c = _client()
    c.get({"search.semantic": "q"})
    c.get({"filter": "cites:W1"})
    line = budget_line(RUN_STATS["budget"])
    assert "$0.0838" in line
    assert "約 83 回" in line and "838 回" not in line
    reset_run_stats()


def test_filter_only_run_still_counts_searches_at_the_search_price(monkeypatch):
    from src.openalex.client import RUN_STATS, budget_line, reset_run_stats
    _metered_sequence(monkeypatch, [
        {"X-RateLimit-Remaining-USD": "0.0678", "X-RateLimit-Limit-USD": "0.1",
         "X-RateLimit-Cost-USD": "0.0001"},
    ])
    reset_run_stats()
    _client().get({"filter": "ids.openalex:W1"})
    assert "約 67 回" in budget_line(RUN_STATS["budget"])
    reset_run_stats()


# --- F-40 (2026-09-29): anonymous full-text search paused ---------------------------------

# The body and header OpenAlex returned at 21:03 JST on 2026-09-29 for `search=` and
# `filter=title_and_abstract.search:` (search.semantic and plain filters still answered 200).
_PAUSED_BODY = (b'{"error":"Search temporarily unavailable","message":"Anonymous search is paused while '
                b'the search cluster recovers from heavy load. Please retry shortly, or use a free API '
                b'key for uninterrupted access: https://openalex.org/rest-api."}')


def _paused_503() -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.openalex.org/works", 503, "Service Unavailable",
                                  {"Retry-After": "60"}, io.BytesIO(_PAUSED_BODY))


def test_paused_anonymous_search_is_named_not_reported_as_a_bare_503(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [_paused_503()])
    with pytest.raises(OpenAlexError) as exc:
        _client(max_retries=2).get({"search": "x"})
    msg = str(exc.value)
    assert "匿名" in msg and "全文検索" in msg and "F-40" in msg
    assert "OPENALEX_API_KEY" in msg
    assert "クエリや候補の問題ではありません" in msg
    assert "Retry-After 60 秒" in msg
    assert len(calls) == 3


def test_other_503_keeps_the_generic_message(monkeypatch):
    _patch_urlopen(monkeypatch, [_http_error(503)])
    with pytest.raises(OpenAlexError) as exc:
        _client(max_retries=1).get({})
    assert "after 2 attempts" in str(exc.value) and "F-40" not in str(exc.value)


def test_api_key_from_environment_is_sent(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "k-test")
    calls = _patch_urlopen(monkeypatch, [{"results": []}])
    _client().get({"search": "x"})
    assert "api_key=k-test" in calls[0].full_url


def test_no_api_key_leaves_the_url_unchanged(monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    calls = _patch_urlopen(monkeypatch, [{"results": []}])
    _client().get({"search": "x"})
    assert "api_key" not in calls[0].full_url
