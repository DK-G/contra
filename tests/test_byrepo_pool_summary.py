"""F-41: byrepo says what the POOL contains per keyword, and what it could not read.

seihai 2026-10-02 (r05): keywords `whipsaw, hysteresis, trend-following, regime-filter,
backtesting`; the four returned anchors read relevance 0.33-0.43, all of it earned by the two
general keywords. The replay of that call (scripts/byrepo_pool_probe.py, same day) pooled 30
repositories: whipsaw 1 (README), hysteresis 1 (README), trend-following 15 (1 on the identity
surface), regime-filter 5 (0), backtesting 26 (18). The calibration case below is that pool.
"""

from __future__ import annotations

import src.mcp_server as mcp
from src.core.models import Keywords, Scope, ThemeInput
from src.github.client import GitHubError
from src.pipeline.git_collect import GitCollectConfig, collect_track_a_git_works
from src.pipeline.theme_fit import pool_keyword_breakdown, pool_summary

KEYWORDS = ["whipsaw", "hysteresis", "trend-following", "regime-filter", "backtesting"]
_STRONG = "name/description/topics"


def _meta(**hits: str) -> dict:
    """hits: keyword (underscored) -> 'strong' | 'readme'."""
    return {"theme_fit_matched": [
        {"keyword": k.replace("_", "-"), "where": _STRONG if v == "strong" else "readme", "credit": 1.0}
        for k, v in hits.items()
    ]}


def _replayed_pool() -> list:
    """30 anchors with the per-keyword counts of the 2026-10-02 replay."""
    pool = [_meta(backtesting="strong") for _ in range(15)]
    pool += [_meta(backtesting="strong", trend_following="readme") for _ in range(2)]
    pool.append(_meta(trend_following="strong", backtesting="strong"))  # bt strong 18, tf strong 1
    pool += [_meta(trend_following="readme", backtesting="readme") for _ in range(8)]  # bt readme 8
    pool += [_meta(trend_following="readme") for _ in range(2)]
    pool.append(_meta(trend_following="readme", whipsaw="readme"))
    pool.append(_meta(trend_following="readme", hysteresis="readme"))   # tf readme 14
    # regime-filter 5, README only — on anchors already counted above
    for m in pool[18:23]:
        m["theme_fit_matched"].append({"keyword": "regime-filter", "where": "readme", "credit": 0.4})
    assert len(pool) == 30
    return pool


def test_breakdown_counts_the_replayed_pool():
    rows = {r["keyword"]: r for r in pool_keyword_breakdown(
        KEYWORDS, [m["theme_fit_matched"] for m in _replayed_pool()])}
    assert (rows["whipsaw"]["strong"], rows["whipsaw"]["readme"]) == (0, 1)
    assert (rows["hysteresis"]["strong"], rows["hysteresis"]["readme"]) == (0, 1)
    assert (rows["trend-following"]["strong"], rows["trend-following"]["readme"]) == (1, 14)
    assert (rows["regime-filter"]["strong"], rows["regime-filter"]["readme"]) == (0, 5)
    assert (rows["backtesting"]["strong"], rows["backtesting"]["readme"]) == (18, 8)


def test_summary_names_the_core_keywords_the_pool_never_carried():
    text = pool_summary(KEYWORDS, _replayed_pool())
    assert "取得 30 件" in text
    assert "whipsaw 1（0・1）" in text and "backtesting 26（18・8）" in text
    warning = next(line for line in text.splitlines() if line.startswith("⚠ 名前/説明/topics"))
    named = warning.split(" — ")[0]
    assert "whipsaw（README の言及のみ 1 件）" in named
    assert "hysteresis（README の言及のみ 1 件）" in named
    assert "regime-filter（README の言及のみ 5 件）" in named
    assert "backtesting" not in named and "trend-following" not in named


def test_keyword_absent_even_from_readmes_is_worded_as_zero():
    text = pool_summary(["whipsaw", "backtesting"], [_meta(backtesting="strong")] * 3)
    assert "whipsaw（README を含め 0 件）" in text


def test_no_warning_when_every_keyword_reaches_an_identity_surface():
    pool = [_meta(whipsaw="strong"), _meta(backtesting="strong", whipsaw="readme")]
    text = pool_summary(["whipsaw", "backtesting"], pool)
    assert "プール内訳" in text and "⚠" not in text


def test_summary_is_silent_without_measurements_or_keywords():
    assert pool_summary(KEYWORDS, [{"reliability_score": 99}]) == ""   # anchor never matched
    assert pool_summary([], [_meta(backtesting="strong")]) == ""


def test_summary_reports_fetch_failures_as_unmeasured():
    pool = [_meta(backtesting="strong") for _ in range(3)]
    pool[1]["readme_fetch_error"] = "http 403: rate limit exceeded"
    pool[2]["readme_fetch_error"] = "http 403: rate limit exceeded"
    pool[2]["issue_signal_summary"] = "issue取得失敗"
    text = pool_summary(["backtesting"], pool)
    assert "取得失敗: README 2 件・issue 1 件（http 403: rate limit exceeded）" in text


# --- collection: a rate-limited README is not "a repository without a README" ---------------

def _theme() -> ThemeInput:
    return ThemeInput(
        theme_overview="Suppress the stop-and-reverse whipsaw of a trend-following rule.",
        goal="Find implementations.", why_problem="The whipsaw erases the edge.",
        approach_type="system-building", assumptions=[],
        scope=Scope(field="quantitative finance", scale="strategy", time_range="recent"),
        keywords=Keywords(include=["whipsaw", "backtesting"], exclude=[]),
    )


class _ReadmeFailingClient:
    def __init__(self, error: str) -> None:
        self.error = error

    def get(self, path, params=None):
        if path == "/search/repositories":
            return {"items": [{
                "full_name": "acme/bt", "html_url": "https://github.com/acme/bt",
                "description": "backtesting toolkit", "stargazers_count": 10,
                "updated_at": "2026-09-01T00:00:00Z", "pushed_at": "2026-09-01T00:00:00Z",
                "topics": [],
            }]}
        if path.endswith("/readme"):
            raise GitHubError(self.error)
        if path.endswith("/issues"):
            return []
        raise AssertionError(path)


def _collect(error: str) -> dict:
    works = collect_track_a_git_works(
        _theme(), config=GitCollectConfig(per_page=5, max_repos=5), client=_ReadmeFailingClient(error))
    return works[0].source_meta


def test_rate_limited_readme_is_recorded_on_the_anchor():
    meta = _collect('http 403: {"message":"API rate limit exceeded for 203.0.113.7."}')
    assert meta["readme_fetch_error"] == "http 403: rate limit exceeded"   # the caller's IP is dropped
    assert "README 1 件" in pool_summary(["whipsaw", "backtesting"], [meta])


def test_missing_readme_is_not_a_fetch_failure():
    meta = _collect('http 404: {"message":"Not Found"}')
    assert meta["readme_fetch_error"] == ""
    assert "取得失敗" not in pool_summary(["whipsaw", "backtesting"], [meta])


# --- MCP wiring: the breakdown covers the whole pool, not the returned anchors --------------

class _Work:
    def __init__(self, reliability: int, **hits: str) -> None:
        self.source_meta = {"reliability_score": reliability, "relevance": 0.5,
                            "anchor_rank_score": float(reliability), "relevance_tier": 1,
                            **_meta(**hits)}


def test_byrepo_output_carries_the_pool_breakdown_before_the_cut(monkeypatch):
    pool = [_Work(90, backtesting="strong"), _Work(80, backtesting="strong"),
            _Work(10, whipsaw="strong")]
    monkeypatch.setattr(mcp, "collect_track_a_works", lambda *a, **k: list(pool))
    monkeypatch.setattr(mcp, "assemble_keyless_track_a_document", lambda *a, **k: object())
    monkeypatch.setattr(mcp, "render_markdown", lambda doc: "ANCHORS")
    result = mcp.StdinMcpServer()._execute_byrepo({
        "theme_overview": "テーマ概要。" * 40, "goal": "g", "why_problem": "w",
        "assumptions": ["仮説1", "仮説2"], "scope_field": "quantitative finance",
        "keywords_include": ["whipsaw", "hysteresis", "backtesting"],
        "structured": True, "sources": ["github"], "track_a_count": 1,
    })
    text = result["content"][0]["text"]
    # whipsaw is carried only by the lowest-ranked anchor, which the cut to 1 drops.
    assert "取得 3 件" in text and "whipsaw 1（1・0）" in text
    assert "hysteresis（README を含め 0 件）" in text
    assert text.index("プール内訳") < text.index("ANCHORS")
