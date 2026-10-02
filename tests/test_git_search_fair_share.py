"""F-41: a keyword the OR query crowds out is searched on its own.

seihai 2026-10-02 (r05): `whipsaw OR hysteresis OR trend-following OR regime-filter OR
backtesting` matched 483,226 repositories; the best-match top 30 held 26 `backtesting` matches
and one `whipsaw` (a partial README mention). Searched alone, `whipsaw` has 1,762 matches. The
fake client below carries those counts: the OR query returns only general-keyword repositories,
and each keyword searched alone returns its own.

An equal share of the OR query is 483,226 / 5 = 96,645: `trend-following` (279,586) and
`backtesting` (167,043) are above it and stay with the OR leg; `whipsaw`, `hysteresis` and
`regime-filter` are below it and get a search of their own.
"""

from __future__ import annotations

import pytest

from src.core.models import Keywords, Scope, ThemeInput
from src.github.client import GitHubError
from src.pipeline.git_collect import (
    SEARCH_LEG_ALL,
    GitCollectConfig,
    _assign_leg_turns,
    build_track_a_git_query,
    build_track_a_git_search_legs,
    collect_track_a_git_works,
)
from src.pipeline.theme_fit import pool_keyword_breakdown, pool_summary

KEYWORDS = ["whipsaw", "hysteresis", "trend-following", "regime-filter", "backtesting"]
OR_TOTAL = 483_226
TOTALS = {"whipsaw": 1_762, "hysteresis": 29_367, "trend-following": 279_586,
          "regime-filter": 36_645, "backtesting": 167_043}


def _theme(include=KEYWORDS, exclude=()) -> ThemeInput:
    return ThemeInput(
        theme_overview="Suppress the stop-and-reverse whipsaw of a trend-following rule.",
        goal="Find implementations.", why_problem="The whipsaw erases the edge.",
        approach_type="system-building", assumptions=[],
        scope=Scope(field="quantitative finance", scale="strategy", time_range="recent"),
        keywords=Keywords(include=list(include), exclude=list(exclude)),
    )


def _item(name: str, description: str) -> dict:
    return {"full_name": name, "html_url": f"https://github.com/{name}", "description": description,
            "stargazers_count": 10, "updated_at": "2026-09-01T00:00:00Z",
            "pushed_at": "2026-09-01T00:00:00Z", "topics": []}


class _PerKeywordClient:
    """OR query -> general-keyword repositories only; a single keyword -> its own repositories."""

    def __init__(self, fail=(), shared=()) -> None:
        self.fail = set(fail)
        self.shared = set(shared)      # keywords whose first results are the OR query's too
        self.queries = []

    def get(self, path, params=None):
        if path != "/search/repositories":
            if path.endswith("/readme"):
                raise GitHubError('http 404: {"message":"Not Found"}')
            return []
        query = params["q"]
        self.queries.append(query)
        head = query.split(" in:name")[0]
        if " OR " in head:
            return {"total_count": OR_TOTAL,
                    "items": [_item(f"or/bt{i}", "backtesting toolkit") for i in range(30)]}
        if head in self.fail:
            raise GitHubError('http 403: {"message":"API rate limit exceeded for 203.0.113.7."}')
        items = [_item(f"{head}/r{i}", f"{head} implementation") for i in range(30)]
        if head in self.shared:
            items = [_item(f"or/bt{i}", "backtesting toolkit") for i in range(3)] + items
        return {"total_count": TOTALS[head], "items": items}


def _collect(client, pool=30, **cfg):
    cfg.setdefault("keyword_fair_share", True)
    stats: list = []
    works = collect_track_a_git_works(
        _theme(), config=GitCollectConfig(per_page=pool, max_repos=pool, **cfg),
        client=client, stats_out=stats)
    return works, stats


def _strong_counts(works) -> dict:
    rows = pool_keyword_breakdown(KEYWORDS, [w.source_meta["theme_fit_matched"] for w in works])
    return {r["keyword"]: r["strong"] for r in rows}


def _seats(stats) -> dict:
    return {s["label"]: s["seated"] for s in stats}


def test_the_single_or_query_stays_the_default():
    # Measured 2026-10-02 and not adopted as the default: see GitCollectConfig.keyword_fair_share.
    assert GitCollectConfig().keyword_fair_share is False


def test_single_or_query_reproduces_the_observed_pool():
    works, stats = _collect(_PerKeywordClient(), keyword_fair_share=False)
    assert _strong_counts(works) == {"whipsaw": 0, "hysteresis": 0, "trend-following": 0,
                                     "regime-filter": 0, "backtesting": 30}
    assert [s["label"] for s in stats] == [SEARCH_LEG_ALL]


def test_turns_follow_the_observed_counts():
    stats = [{"total_count": OR_TOTAL}] + [{"total_count": TOTALS[k]} for k in KEYWORDS]
    assert _assign_leg_turns(stats) == [2, 1, 1, 0, 1, 0]
    assert [s.get("served_by_or") for s in stats[1:]] == [False, False, True, False, True]


def test_crowded_out_keywords_reach_the_pool():
    works, stats = _collect(_PerKeywordClient())
    assert len(works) == 30
    # Five keywords, six seats each: the two frequent keywords' twelve stay with the OR query.
    assert _seats(stats) == {SEARCH_LEG_ALL: 12, "whipsaw": 6, "hysteresis": 6,
                             "trend-following": 0, "regime-filter": 6, "backtesting": 0}
    counts = _strong_counts(works)
    assert counts["whipsaw"] == 6 and counts["hysteresis"] == 6 and counts["regime-filter"] == 6
    assert counts["backtesting"] == 12
    assert stats[1]["total_count"] == 1_762


def test_frequent_keywords_are_not_given_a_search_share():
    # Measured 2026-10-02 and not kept: `backtesting` searched alone returned freqtrade and
    # TradingAgents, which took the top of the ranking from the OR query's two-keyword matches.
    works, _ = _collect(_PerKeywordClient())
    assert not [w.title for w in works if w.title.startswith(("backtesting/", "trend-following/"))]


def test_a_leg_skips_repositories_another_leg_already_seated():
    works, stats = _collect(_PerKeywordClient(shared={"whipsaw"}))
    names = [w.title for w in works]
    assert len(names) == len(set(names))
    assert _seats(stats)["whipsaw"] == 6      # its turn is not lost to the duplicates


def test_small_pool_keeps_the_same_proportions():
    works, stats = _collect(_PerKeywordClient(), pool=10)
    assert _seats(stats) == {SEARCH_LEG_ALL: 4, "whipsaw": 2, "hysteresis": 2,
                             "trend-following": 0, "regime-filter": 2, "backtesting": 0}
    assert len(works) == 10


def test_each_anchor_records_the_search_that_seated_it():
    works, _ = _collect(_PerKeywordClient())
    legs = {w.title: w.source_meta["search_leg"] for w in works}
    assert legs["whipsaw/r0"] == "whipsaw"
    assert legs["or/bt0"] == SEARCH_LEG_ALL


def test_failed_keyword_search_is_reported_and_its_share_goes_to_the_or_query():
    works, stats = _collect(_PerKeywordClient(fail={"regime-filter"}))
    assert len(works) == 30
    failed = next(s for s in stats if s["label"] == "regime-filter")
    assert failed["error"] == "http 403: rate limit exceeded" and failed["seated"] == 0
    assert _seats(stats)[SEARCH_LEG_ALL] == 18 and _seats(stats)["whipsaw"] == 6
    text = pool_summary(KEYWORDS, [w.source_meta for w in works], stats)
    assert "検索に失敗したキーワード: regime-filter（http 403: rate limit exceeded）" in text


def test_failed_or_query_still_raises():
    class _Down(_PerKeywordClient):
        def get(self, path, params=None):
            raise GitHubError("network error: unreachable")

    with pytest.raises(GitHubError):
        _collect(_Down())


def test_single_keyword_keeps_the_single_search():
    theme = _theme(include=["whipsaw"])
    assert build_track_a_git_search_legs(theme) == [(SEARCH_LEG_ALL, build_track_a_git_query(theme))]


def test_keyword_legs_carry_excludes_and_the_freshness_bar():
    legs = dict(build_track_a_git_search_legs(_theme(include=["whipsaw", "regime filter"],
                                                    exclude=["crypto"])))
    assert legs["whipsaw"].startswith("whipsaw in:name,description,readme NOT crypto pushed:>")
    assert legs["regime filter"].startswith('"regime filter" in:name,description,readme NOT crypto')


def test_summary_prints_how_the_pool_was_fetched():
    works, stats = _collect(_PerKeywordClient())
    text = pool_summary(KEYWORDS, [w.source_meta for w in works], stats)
    first = text.splitlines()[0]
    assert first.startswith("検索の内訳")
    assert f"{SEARCH_LEG_ALL} 該当 483,226 件→12 件" in first
    assert "whipsaw 該当 1,762 件→6 件" in first
    assert "backtesting 該当 167,043 件→全語 OR に含めて取得" in first


def test_summary_is_silent_about_a_single_search():
    works, stats = _collect(_PerKeywordClient(), keyword_fair_share=False)
    assert "検索の内訳" not in pool_summary(KEYWORDS, [w.source_meta for w in works], stats)
