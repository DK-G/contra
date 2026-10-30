"""F-74 (survey 2026-10-28, EX shogi): the history file is keyed by the theme_overview hash, and the
survey rewrites its description each run, so the 10-14 and 10-21 output sat under other hashes and
would have come back unless the caller handed 23 ids over by hand. `history_key` names the file."""

from __future__ import annotations

from test_mcp_history import _entry, _theme

from src.mcp_server import StdinMcpServer, _history_adopt, _history_exclusions


def test_rewritten_overview_sees_the_history_through_the_key(tmp_path):
    args = {"history_key": "exshogi"}
    assert _history_adopt(_theme("first description " * 5), args, [_entry("W1", "A title", "10.1/x")],
                          history_dir=tmp_path) == 1
    ids, titles, dois = _history_exclusions(_theme("rewritten description " * 5), args, history_dir=tmp_path)
    assert ids == {"W1"} and titles == {"a title"} and dois == {"10.1/x"}


def test_without_the_key_each_overview_keeps_its_own_history(tmp_path):
    _history_adopt(_theme("first description " * 5), {}, [_entry("W1", "A title")], history_dir=tmp_path)
    assert _history_exclusions(_theme("rewritten description " * 5), {}, history_dir=tmp_path)[0] == set()
    assert _history_exclusions(_theme("first description " * 5), {}, history_dir=tmp_path)[0] == {"W1"}


def test_key_is_trimmed_and_blank_means_no_key(tmp_path):
    _history_adopt(_theme("first description " * 5), {"history_key": " exshogi "}, [_entry("W1", "A title")],
                   history_dir=tmp_path)
    assert _history_exclusions(_theme("other " * 20), {"history_key": "exshogi"}, history_dir=tmp_path)[0] == {"W1"}
    assert _history_exclusions(_theme("other " * 20), {"history_key": "  "}, history_dir=tmp_path)[0] == set()


def test_no_history_still_wins(tmp_path):
    args = {"history_key": "exshogi", "no_history": True}
    assert _history_adopt(_theme(), args, [_entry("W1", "A title")], history_dir=tmp_path) == 0
    assert _history_exclusions(_theme(), args, history_dir=tmp_path)[0] == set()


def test_the_three_tools_declare_it():
    tools = {t["name"]: t for t in StdinMcpServer().list_tools()}
    for name in ("byserendipity_discover", "bybridge_collect", "delegate_finalize"):
        assert "history_key" in tools[name]["inputSchema"]["properties"]
