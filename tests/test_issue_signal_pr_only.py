"""F-78 (survey 2026-11-02 metagumo): the issues endpoint also lists PRs, so an active repo whose
newest 5 items were all PRs was reported as "no issues (zero-issue trap)" and scored 0."""

from __future__ import annotations

from src.pipeline.git_collect import _fetch_issue_signal


def _issue(n: int, state: str = "open", user: str = "u") -> dict:
    return {"number": n, "state": state, "user": {"login": user}, "body": "text", "labels": []}


def _pr(n: int) -> dict:
    return {**_issue(n), "pull_request": {"url": "x"}}


class Client:
    def __init__(self, items):
        self.items, self.calls = items, []

    def get(self, path, params):
        self.calls.append(params)
        return self.items[: params["per_page"]]


def test_prs_first_reaches_back_for_real_issues_in_one_call():
    client = Client([_pr(i) for i in range(8)] + [_issue(20, "closed", "a"), _issue(21, "open", "b")])
    score, summary, open_count, closed_count, reporters = _fetch_issue_signal(client, "o/r", 5, 1000, "o")
    assert len(client.calls) == 1
    assert "ゼロIssue" not in summary and summary.startswith("直近5件はすべてPR・それより前の issue 2件")
    assert (open_count, closed_count, reporters) == (1, 1, 2) and score == 9


def test_only_prs_in_the_wide_page_is_unconfirmed_not_the_trap():
    client = Client([_pr(i) for i in range(30)])
    score, summary, *_ = _fetch_issue_signal(client, "o/r", 5, 1000, "o")
    assert score == 3 and summary == "issues未確認 (直近30件はすべてPR)"


def test_newest_sample_with_an_issue_is_scored_as_before():
    items = [_pr(1), _issue(2), _pr(3), _pr(4), _pr(5)] + [_issue(i, "closed") for i in range(10, 20)]
    _, summary, open_count, closed_count, _ = _fetch_issue_signal(Client(items), "o/r", 5, 1000, "o")
    assert (open_count, closed_count) == (1, 0)
    # F-84: the count is the sample's, not the repository's total.
    assert summary == "直近5件のうち issue 1件 / open 1 / closed 0"


def test_empty_repo_still_hits_the_trap():
    assert _fetch_issue_signal(Client([]), "o/r", 5, 1000, "o")[:2] == (0, "issuesなし (警告: ゼロIssueの罠)")
