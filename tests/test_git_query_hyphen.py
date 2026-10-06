"""F-42: a hyphenated include keyword searched ON ITS OWN is sent to GitHub as a phrase.

seihai sends keywords such as `trend-following`, `regime-filter`, `novelty-search`. GitHub's
repository search splits an unquoted hyphenated word into separate words (measured 2026-10-06:
`trend-following` 280,891 matches with `apache/tvm` in the top 4; `"trend-following"` 10,204),
while the relevance matcher reads the same keyword as a phrase.

The per-keyword searches (F-41-R, opt-in) now quote it. The OR query does not: the same quoting
was measured there the same day and changed the pool for the worse without changing what was
returned (see build_track_a_git_search_legs), so the default output is untouched.
"""

from __future__ import annotations

import pytest

from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.git_collect import (
    _clean_token,
    build_track_a_git_query,
    build_track_a_git_search_legs,
)
from src.pipeline.theme_fit import keyword_fit


def _theme(include, exclude=()) -> ThemeInput:
    return ThemeInput(
        theme_overview="Suppress the stop-and-reverse whipsaw of a trend-following rule.",
        goal="Find implementations.", why_problem="The whipsaw erases the edge.",
        approach_type="system-building", assumptions=[],
        scope=Scope(field="quantitative finance", scale="strategy", time_range="recent"),
        keywords=Keywords(include=list(include), exclude=list(exclude)),
    )


@pytest.mark.parametrize("token, sent", [
    ("trend-following", '"trend-following"'),
    ("regime-filter", '"regime-filter"'),
    ("novelty-search", '"novelty-search"'),
    ("best-arm identification", '"best-arm identification"'),   # already a phrase: unchanged
    ("whipsaw", "whipsaw"),
    ("backtesting", "backtesting"),
    ('"trend-following"', '"trend-following"'),                 # caller's own quotes: not doubled
    ("language:python", "language:python"),                     # qualifiers pass through
    ("stars:>50", "stars:>50"),
    ("-", "-"),                                                 # a bare dash is not a phrase
])
def test_hyphenated_keywords_are_quoted_when_asked(token, sent):
    assert _clean_token(token, quote_hyphen=True) == sent


@pytest.mark.parametrize("token", ["trend-following", "regime-filter", "whipsaw"])
def test_the_default_spelling_is_unchanged(token):
    assert _clean_token(token) == token


def test_the_or_query_is_left_as_it_was():
    # Measured and not adopted: quoting here handed the pool to the one unquoted general keyword.
    query = build_track_a_git_query(
        _theme(["whipsaw", "hysteresis", "trend-following", "regime-filter", "backtesting"]))
    assert query.startswith(
        "whipsaw OR hysteresis OR trend-following OR regime-filter OR backtesting in:name")


def test_observed_2026_10_02_keyword_searches_send_the_hyphenated_keywords_as_phrases():
    legs = dict(build_track_a_git_search_legs(
        _theme(["whipsaw", "hysteresis", "trend-following", "regime-filter", "backtesting"])))
    assert legs["trend-following"].startswith('"trend-following" in:name')
    assert legs["regime-filter"].startswith('"regime-filter" in:name')
    assert legs["whipsaw"].startswith("whipsaw in:name")


def test_the_search_and_the_relevance_matcher_agree_on_what_the_keyword_means():
    # What the unquoted search used to fetch ("trend" and "following" apart) earns no credit
    # from the matcher; what the quoted search fetches does, with a hyphen or a space.
    fit = lambda text: keyword_fit(["trend-following"], [], text, scale=30)["coverage"]  # noqa: E731
    assert fit("Open deep learning compiler stack. Following the trend of ML systems") == 0.0
    assert fit("Closed-form trend-following analytics") == 1.0
    assert fit("crypto trend following bot") == 1.0


def test_fair_share_leg_labels_keep_the_callers_spelling():
    legs = build_track_a_git_search_legs(_theme(["whipsaw", "trend-following"]))
    assert [label for label, _ in legs][1:] == ["whipsaw", "trend-following"]
    assert legs[2][1].startswith('"trend-following" in:name')
