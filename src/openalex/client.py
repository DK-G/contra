"""OpenAlex minimal HTTP client."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


class OpenAlexError(RuntimeError):
    pass


# Transient statuses worth one more try (F-11): 429 = shared-pool rate limit (observed
# in the wild as a one-off that clears within a second), 5xx = server-side hiccups.
# 4xx other than 429 mean the REQUEST is wrong — retrying those just repeats the mistake.
_RETRY_STATUSES = {429, 500, 502, 503, 504}

# F-11(3): process-wide fetch telemetry for one tool run. A run where some requests failed
# (even after retries) must not present itself as a clean "zero harvest" — the MCP layer
# resets this before each tool call and appends a caveat line when anything went wrong.
# Counters, not state: clients are constructed per collection stage, so per-instance stats
# would fragment across the run.
RUN_STATS = {"requests": 0, "retried": 0, "gave_up": 0, "budget": None}


def reset_run_stats() -> None:
    RUN_STATS.update(requests=0, retried=0, gave_up=0, budget=None)


# --- F-29 (2026-09-16): the DAILY USD budget, not the burst limit ------------------------
#
# OpenAlex meters this IP in USD: $0.10/day, $0.001 (10 credits) per search = about 100
# searches per day, shared by every by* tool and every session on the machine. The budget
# resets at 00:00 UTC (= 09:00 JST, measured 2026-09-18: X-RateLimit-Reset 42732 s at 21:08
# JST) — AFTER seihai's 07:05 daily run, so whatever ran since 09:00 the previous day is
# charged to that run. On 2026-09-16 the probe read Remaining-USD 0.0008 < Cost-Required
# 0.001 with Retry-After 6394 s; contra retried twice (useless: the wait is hours, not
# seconds) and then said "wait and retry", which the caller read as seconds.
# Every response carries the meter, so it is read on success too; a 429 whose meter says
# "budget below the cost of one request" is not retried and names the wait in hours.

def _hdr_float(headers: Any, name: str) -> Optional[float]:
    try:
        value = headers.get(name) if headers is not None else None
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def read_budget(headers: Any) -> Optional[Dict[str, Optional[float]]]:
    """The USD meter from one OpenAlex response's headers; None when absent."""
    meter = {
        "remaining_usd": _hdr_float(headers, "X-RateLimit-Remaining-USD"),
        "limit_usd": _hdr_float(headers, "X-RateLimit-Limit-USD"),
        "cost_usd": (_hdr_float(headers, "X-RateLimit-Cost-Required-USD")
                     or _hdr_float(headers, "X-RateLimit-Cost-USD")),
        "reset_sec": _hdr_float(headers, "X-RateLimit-Reset"),
        "retry_after_sec": _hdr_float(headers, "Retry-After"),
    }
    if meter["remaining_usd"] is None and meter["retry_after_sec"] is None:
        return None
    return meter


def budget_exhausted(meter: Optional[Dict[str, Optional[float]]]) -> bool:
    """True when the daily USD budget cannot pay for one more request."""
    if not meter or meter.get("remaining_usd") is None:
        return False
    cost = meter.get("cost_usd") or 0.001
    return meter["remaining_usd"] < cost


def _wait_phrase(seconds: Optional[float]) -> str:
    if seconds is None:
        return "待ち時間は応答に含まれていません"
    resume = time.strftime("%H:%M", time.localtime(time.time() + seconds))
    if seconds >= 3600:
        return f"Retry-After {int(seconds)} 秒＝約 {seconds / 3600:.1f} 時間（再開目安 {resume}）"
    return f"Retry-After {int(seconds)} 秒（再開目安 {resume}）"


# F-36 (2026-09-27): "searches left" was remaining / the LAST response's cost, but OpenAlex
# prices requests by kind — a search costs $0.001 (10 credits), a filter list call $0.0001
# (1 credit; probed 2026-09-27: X-RateLimit-Cost-USD 0.0001 / Credits-Used 1). bybridge ends
# on filter calls, so on 2026-09-27 the same day read "$0.097 -> 約 97 回" after byserendipity
# and "$0.0838 -> 約 838 回" after bybridge. The count is now priced at the search cost: the
# documented price, or the dearest request this run actually paid for if that is higher.
SEARCH_COST_USD = 0.001


def _record_meter(meter: Dict[str, Optional[float]]) -> None:
    previous = RUN_STATS.get("budget") or {}
    meter["search_cost_usd"] = max(SEARCH_COST_USD, meter.get("cost_usd") or 0.0,
                                   previous.get("search_cost_usd") or 0.0)
    RUN_STATS["budget"] = meter


def budget_line(meter: Optional[Dict[str, Optional[float]]]) -> str:
    """'OpenAlex 日次予算の残り $0.052 / $0.1（検索 1 回 $0.001 換算であと約 52 回…）' — '' without a meter."""
    if not meter or meter.get("remaining_usd") is None:
        return ""
    unit = meter.get("search_cost_usd") or max(SEARCH_COST_USD, meter.get("cost_usd") or 0.0)
    limit = meter.get("limit_usd")
    left = int(meter["remaining_usd"] / unit + 1e-9)
    return (f"OpenAlex 日次予算の残り ${meter['remaining_usd']:g}"
            + (f" / ${limit:g}" if limit is not None else "")
            + f"（検索 1 回 ${unit:g} 換算であと約 {left} 回・リセットは 00:00 UTC＝09:00 JST）")


def run_stats_caveat() -> str:
    """One caveat line when the run saw transient failures; '' when it was clean."""
    if not (RUN_STATS["retried"] or RUN_STATS["gave_up"]):
        return ""
    parts = [f"OpenAlex リクエスト {RUN_STATS['requests']} 件中"]
    if RUN_STATS["retried"]:
        parts.append(f"一時失敗→リトライ {RUN_STATS['retried']} 回")
    if RUN_STATS["gave_up"]:
        parts.append(f"リトライ上限まで失敗 {RUN_STATS['gave_up']} 件")
    tail = (
        "。結果が薄い場合は「収穫ゼロ」ではなく取得失敗の可能性があります（再実行を推奨）。"
        if RUN_STATS["gave_up"]
        else "（リトライで回復済み。ただしこの行は HTTP 応答だけを見ており、"
        "段や facet ごとの欠損は保証しない——facet 別内訳を参照）。"
    )
    budget = budget_line(RUN_STATS.get("budget"))
    return "⚠ 取得診断: " + " / ".join(parts) + tail + (f" {budget}" if budget else "")


def low_budget_caveat(threshold: float = 0.25) -> str:
    """One line when the day's budget is below `threshold` of the limit, even on a clean run.

    The budget is shared with seihai's 07:05 run, which is charged for everything since 09:00
    JST the day before — a caller that sees the meter low can defer, before the 429 arrives.
    """
    meter = RUN_STATS.get("budget")
    if not meter or meter.get("remaining_usd") is None or not meter.get("limit_usd"):
        return ""
    if meter["remaining_usd"] >= threshold * meter["limit_usd"]:
        return ""
    return "ℹ " + budget_line(meter) + "。この予算は by* 全体と seihai の朝の実行で共有されています（F-29）。"


@dataclass
class OpenAlexConfig:
    base_url: str = "https://api.openalex.org/works"
    mailto: Optional[str] = None
    timeout_sec: int = 20
    min_interval_sec: float = 0.2
    max_retries: int = 2            # extra attempts on transient failures (0 = old behaviour)
    retry_backoff_sec: float = 1.0  # first retry waits this long, second waits double
    # F-33 (2026-09-25): after the normal retries, keep re-sending a request whose last answer
    # was a 504 until this many seconds have passed since the first attempt (0 = off, the old
    # behaviour). Only worth it where a 504 streak is known to clear: see OpenAlexClient.get.
    gateway_patience_sec: float = 0.0
    gateway_retry_interval_sec: float = 5.0


class OpenAlexClient:
    def __init__(self, config: Optional[OpenAlexConfig] = None) -> None:
        self.config = config or OpenAlexConfig()
        self._last_call_at = 0.0
        # F-33: how the last get() went through a 504 streak — {"gateway_504": n,
        # "waited_sec": s, "recovered": bool}; None when the call saw no 504.
        self.last_gateway_wait: Optional[Dict[str, Any]] = None

    def _now(self) -> float:  # separated so tests can drive the patience clock
        return time.time()

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_call_at
        if elapsed < self.config.min_interval_sec:
            time.sleep(self.config.min_interval_sec - elapsed)

    def _build_url(self, params: Dict[str, Any]) -> str:
        if self.config.mailto:
            params = dict(params)
            params["mailto"] = self.config.mailto
        query = urllib.parse.urlencode(params, doseq=True)
        return f"{self.config.base_url}?{query}"

    def _sleep(self, seconds: float) -> None:  # separated so tests can stub the wait out
        time.sleep(seconds)

    def get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """One GET with bounded retries on transient failures (429/5xx, timeouts).

        F-11 (``docs/field_observations_seihai.md``): without retries a one-off 429 from the
        shared anonymous pool aborts the collection mid-run, and the caller cannot tell that
        "zero harvest" from a genuine empty result. Two backoff retries absorb exactly that
        class of failure; a request that is actually wrong (other 4xx) still fails immediately.
        """
        url = self._build_url(params)
        req = urllib.request.Request(url, headers={"User-Agent": "contra-cli/0.1"})
        attempts = max(0, self.config.max_retries) + 1
        last_exc: Optional[Exception] = None
        RUN_STATS["requests"] += 1
        # F-33 (docs/field_observations_seihai.md, 2026-09-25): the `search.semantic` endpoint
        # answers 504 at exactly 9.1 s (a gateway timeout) in STREAKS that clear after minutes,
        # after which every request passes in 2-7 s (probe 21:03-21:07 JST: 10 x 504, then
        # 8/8 x 200 for the same 716-char query). The streak does not depend on query length or
        # per-page (8-word and 15-word queries 504-ed while a 25-word one passed), and a 504 is
        # not charged against the daily USD budget (no meter headers; Remaining-USD moved only
        # on successes). Three attempts within ~3 s of backoff land inside one streak — that is
        # how the bybridge semantic leg supplied 0 seeds on 9/24 and 9/25 and the roster drifted.
        # So, where the caller opts in, a 504 is re-sent every `gateway_retry_interval_sec`
        # until `gateway_patience_sec` has passed since the first attempt: it costs wall time,
        # not budget. 429 and every other status keep the bounded behaviour above.
        # F-39 (2026-09-28): every semantic request those streaks were measured on carried
        # `filter=type:article`. Without it the same texts passed on the first attempt in
        # 1.8-3.9 s; with it a terrain-navigation query 504-ed on every attempt and a music query
        # passed once in 8.0 s. The "streak that clears" is better read as a slow filtered query
        # that passes once the endpoint has cached it. The type filter is now client-side; the
        # patience stays as a guard for genuine gateway trouble.
        started = self._now()
        gw_504 = 0
        self.last_gateway_wait = None
        attempt = 0
        while True:
            if attempt >= attempts:
                patient = (
                    self.config.gateway_patience_sec > 0
                    and isinstance(last_exc, urllib.error.HTTPError) and last_exc.code == 504
                    and self._now() - started + self.config.gateway_retry_interval_sec
                    <= self.config.gateway_patience_sec
                )
                if not patient:
                    break
                RUN_STATS["retried"] += 1
                self._sleep(self.config.gateway_retry_interval_sec)
            elif attempt:
                RUN_STATS["retried"] += 1
                self._sleep(self.config.retry_backoff_sec * (2 ** (attempt - 1)))
            attempt += 1
            self._rate_limit()
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as res:
                    data = res.read().decode("utf-8")
                    meter = read_budget(getattr(res, "headers", None))
                    if meter:
                        _record_meter(meter)
            except urllib.error.HTTPError as exc:
                last_exc = exc
                meter = read_budget(getattr(exc, "headers", None))
                if meter:
                    _record_meter(meter)
                if exc.code == 429 and budget_exhausted(meter):
                    # F-29: hours of wait, not seconds — a retry cannot succeed; say so now.
                    RUN_STATS["gave_up"] += 1
                    raise OpenAlexError(
                        "OpenAlex の日次予算が枯渇しています（429・"
                        f"残 ${meter['remaining_usd']:g} < 1 回の費用 ${meter.get('cost_usd') or 0.001:g}"
                        + (f"・上限 ${meter['limit_usd']:g}/日" if meter.get("limit_usd") is not None else "")
                        + f"）。{_wait_phrase(meter.get('retry_after_sec'))}。"
                        "数十秒の待ちや呼び順の変更では回復しません。クエリや候補の問題でもありません"
                        "（予算は by* 全体・全セッションで共有され、00:00 UTC＝09:00 JST にリセット・F-29）。"
                    ) from exc
                if exc.code == 504:
                    gw_504 += 1
                if exc.code in _RETRY_STATUSES:
                    continue
                raise OpenAlexError(f"request failed: {exc}") from exc
            except Exception as exc:  # pragma: no cover - network errors
                last_exc = exc       # timeouts / connection resets are transient too
                continue
            finally:
                self._last_call_at = time.time()

            if gw_504:
                self.last_gateway_wait = {"gateway_504": gw_504, "recovered": True,
                                          "waited_sec": round(self._now() - started, 1)}
            try:
                return json.loads(data)
            except json.JSONDecodeError as exc:
                raise OpenAlexError(f"invalid json response: {exc}") from exc
        RUN_STATS["gave_up"] += 1
        if gw_504:
            self.last_gateway_wait = {"gateway_504": gw_504, "recovered": False,
                                      "waited_sec": round(self._now() - started, 1)}
        # F-28 (docs/field_observations_seihai.md, 2026-09-12): every by* tool draws on ONE
        # OpenAlex quota for this IP, so a byserendipity run can starve the bybridge run that
        # follows it (measured: three consecutive bybridge failures right after a successful
        # byserendipity, reproduced with a bare curl-equivalent outside contra). A 429 that
        # survives the retries is not "this query is wrong" and not "the theme is exhausted";
        # the caller's next move is to wait, not to reformulate. Same doctrine as F-16/S-112:
        # never let an upstream outage read as a property of the candidates.
        if isinstance(last_exc, urllib.error.HTTPError) and last_exc.code == 429:
            raise OpenAlexError(
                f"OpenAlex のレート制限（429）が {attempts} 回の再試行でも解けませんでした"
                "＝この IP の共有クォータ枯渇です。クエリや候補の問題ではありません"
                "（by* は同一クォータを共有するため、直前に別の by* を回していると起きやすい・F-28）。"
                "時間をおいて再実行してください。"
                + (f"（{_wait_phrase(RUN_STATS['budget'].get('retry_after_sec'))}）"
                   if (RUN_STATS.get("budget") or {}).get("retry_after_sec") is not None else "")
            ) from last_exc
        raise OpenAlexError(
            f"request failed after {attempt} attempts: {last_exc}"
            + (f"（504 を {gw_504} 回・{self.last_gateway_wait['waited_sec']:g} 秒待って未回復・F-33）"
               if gw_504 and self.config.gateway_patience_sec > 0 else "")
        ) from last_exc


__all__ = [
    "OpenAlexClient",
    "OpenAlexConfig",
    "OpenAlexError",
    "RUN_STATS",
    "SEARCH_COST_USD",
    "budget_exhausted",
    "budget_line",
    "low_budget_caveat",
    "read_budget",
    "reset_run_stats",
    "run_stats_caveat",
]
