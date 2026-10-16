"""F-57: an argument a tool does not declare is named in the result instead of vanishing.

seihai passed byserendipity's `materials_max_chars` to bybridge (2026-10-15, 10-16); the server
ignored it without a word, and the result went to a file at 62k / 90k chars.
"""

from __future__ import annotations

from src.mcp_server import StdinMcpServer


def test_unknown_argument_is_named():
    note = StdinMcpServer()._ignored_args_note(
        "bybridge_collect", {"theme_overview": "x", "materials_max_chars": 45000})
    assert "materials_max_chars" in note and "bybridge_collect" in note and "F-57" in note


def test_declared_arguments_say_nothing():
    s = StdinMcpServer()
    assert s._ignored_args_note("byserendipity_discover",
                                {"theme_overview": "x", "materials_max_chars": 45000}) == ""
    assert s._ignored_args_note("bybridge_collect", {}) == ""
    assert s._ignored_args_note("no_such_tool", {"a": 1}) == ""


def test_note_reaches_the_result():
    from test_full_batch_submission import _mmr_batch
    res = StdinMcpServer().handle_tool_call("delegate_finalize", {
        "theme_overview": "探索の打ち切り規則を設計する。" * 20,
        "goal": "決着しない側の打ち切り規則", "why_problem": "枠が有限であるため",
        "approach_type": "application", "assumptions": ["打ち切りは推定量を歪める", "一律は最適でない"],
        "scope_field": "statistics", "scope_scale": "small", "scope_time_range": "no_limit",
        "count": 3, "no_history": True, "grounded_only": False, "candidates": _mmr_batch(),
        "materials_max_chars": 45000,
    })
    assert res["content"][-1]["text"].startswith("⚠ delegate_finalize はこの引数を受け付けません")
    assert "materials_max_chars" in res["content"][-1]["text"]
