"""Cross-run history dedup wired into the MCP/delegation handlers (parity with the CLI).

Tests the _history_exclusions / _history_adopt helpers that the byserendipity (raw + self-contained),
bybridge, and delegate_finalize handlers use, against a temp history dir.
"""

from __future__ import annotations

from src.core.models import Keywords, OutputEntry, Scope, ThemeInput, Work
from src.mcp_server import _history_adopt, _history_exclusions
from src.pipeline.history import compute_theme_hash, load_history


def _theme(overview: str = "o" * 60) -> ThemeInput:
    return ThemeInput(
        theme_overview=overview, goal="g", why_problem="w", approach_type="design",
        assumptions=[], scope=Scope(field="cs", scale="micro", time_range="no_limit"),
        keywords=Keywords(include=["x"], exclude=[]),
    )


def _entry(wid: str, title: str, doi=None) -> OutputEntry:
    w = Work(id=wid, title=title, year=2021, venue="V", doi=doi, cited_by_count=0, abstract="a")
    return OutputEntry(work=w, relationship="", abstract_summary="", caution="", track="B", label="l")


def test_exclusions_empty_when_no_file_uses_agent_supplied(tmp_path):
    ids, titles, dois = _history_exclusions(_theme(), {"used_ids": ["A"]}, history_dir=tmp_path)
    assert ids == {"A"} and titles == set() and dois == set()


def test_adopt_then_exclusions_round_trip(tmp_path):
    theme = _theme()
    n = _history_adopt(theme, {}, [_entry("W1", "Cascade Dynamics: a study", "10.1/x")],
                       history_dir=tmp_path)
    assert n == 1
    # persisted to the theme-hash file, normalized the way the collection dedup compares
    h = load_history(compute_theme_hash(theme.theme_overview), history_dir=tmp_path)
    assert h.used_ids == ["W1"]
    assert h.used_titles == ["cascade dynamics"]   # _norm_title: lowercase, text before ':'
    assert h.used_dois == ["10.1/x"]
    # a subsequent run's exclusions pick the adopted paper up (so it won't repeat)
    ids, titles, dois = _history_exclusions(theme, {}, history_dir=tmp_path)
    assert ids == {"W1"} and titles == {"cascade dynamics"} and dois == {"10.1/x"}


def test_exclusions_merges_file_and_agent(tmp_path):
    theme = _theme()
    _history_adopt(theme, {}, [_entry("W1", "T one")], history_dir=tmp_path)
    ids, _t, _d = _history_exclusions(theme, {"used_ids": ["AGENT"]}, history_dir=tmp_path)
    assert ids == {"W1", "AGENT"}


def test_no_history_skips_both_directions(tmp_path):
    theme = _theme()
    # adopt with no_history -> nothing persisted
    assert _history_adopt(theme, {"no_history": True}, [_entry("W1", "T")], history_dir=tmp_path) == 0
    # persist something normally, then exclusions with no_history ignores the file
    _history_adopt(theme, {}, [_entry("W2", "T two")], history_dir=tmp_path)
    ids, _t, _d = _history_exclusions(theme, {"no_history": True, "used_ids": ["A"]}, history_dir=tmp_path)
    assert ids == {"A"}   # only agent-supplied; file (W2) skipped


def test_adopt_no_entries_is_noop(tmp_path):
    assert _history_adopt(_theme(), {}, [], history_dir=tmp_path) == 0


# --- F-12: bybridge seed liveness gate ---------------------------------------
# A seed with no referenced_works structurally cannot contribute a bridge; 20/20 such
# records once filled the seed slots and the whole 2-hop scan returned nothing.

import src.mcp_server as mcp_mod
from src.core.models import Work as _W


def _seed_work(wid, refs):
    return _W(id=wid, title=wid, year=2024, venue="v", doi=None, cited_by_count=0,
              abstract="a", referenced_works=refs)


def _bybridge_args(**over):
    args = {
        "theme_overview": "t" * 200, "goal": "g", "why_problem": "w",
        "approach_type": "application", "assumptions": ["a", "b"],
        "scope_field": "f", "scope_scale": "small", "scope_time_range": "last_10_years",
        "keywords_include": [], "keywords_exclude": [],
        "no_history": True, "raw_only": True, "seed_count": 2,
    }
    args.update(over)
    return args


def test_dead_seeds_are_filtered_and_reported(monkeypatch):
    live = _seed_work("W1", ["R1", "R2"])
    dead1, dead2 = _seed_work("W2", []), _seed_work("W3", [])
    monkeypatch.setattr(mcp_mod, "collect_and_filter", lambda *a, **k: [dead1, live, dead2])
    monkeypatch.setattr(mcp_mod, "collect_citation_candidates", lambda *a, **k: [])
    server = mcp_mod.StdinMcpServer()
    result = server.handle_tool_call("bybridge_collect", _bybridge_args())
    text = "\n".join(b.get("text", "") for b in result["content"])
    assert "シード生存確認 (F-12)" in text and "2 件" in text     # both dead records named
    assert "W1" in text and "W2" not in text                      # only the live seed was used


def test_all_dead_seeds_explains_instead_of_empty_pool(monkeypatch):
    monkeypatch.setattr(mcp_mod, "collect_and_filter",
                        lambda *a, **k: [_seed_work("W2", []), _seed_work("W3", [])])
    server = mcp_mod.StdinMcpServer()
    result = server.handle_tool_call("bybridge_collect", _bybridge_args())
    text = "\n".join(b.get("text", "") for b in result["content"])
    assert "referenced_works が空" in text     # the F-12 shape is named, not a generic "not found"
