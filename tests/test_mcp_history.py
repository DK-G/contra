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

import pytest

import src.mcp_server as mcp_mod
from src.core.models import Work as _W


@pytest.fixture(autouse=True)
def _no_openalex(monkeypatch):
    """Keep the bybridge end-to-end cases OFF the network.

    These tests stub the collectors but not the two id-resolving helpers the diagnostics block
    and the bridge liveness gate call. Both fail soft, so the assertions used to survive — until
    OpenAlex started returning 429, at which point the F-11 fetch caveat was appended to the
    result body and the materials case could no longer parse its own JSON payload. Observed on
    unmodified HEAD, so this is test hygiene, not a behaviour change: stub them and the suite
    stops depending on whether api.openalex.org happens to be reachable.
    """
    monkeypatch.setattr(mcp_mod, "resolve_work_labels", lambda *a, **k: {})
    monkeypatch.setattr(mcp_mod, "filter_live_bridges", lambda b, *a, **k: (set(b), []))
    from src.openalex import client as _client
    _client.reset_run_stats()


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


# --- C(iii): seed language gate ----------------------------------------------

def _lang_seed(wid, refs, language):
    w = _seed_work(wid, refs)
    w.language = language
    return w


def test_off_language_seeds_are_dropped_and_reported(monkeypatch):
    en = _lang_seed("W_EN", ["R1"], "en")
    ja = _lang_seed("W_JA", ["R2"], "ja")
    nolang = _lang_seed("W_NONE", ["R3"], None)      # fail-open: missing code is kept
    monkeypatch.setattr(mcp_mod, "collect_and_filter", lambda *a, **k: [ja, en, nolang])
    monkeypatch.setattr(mcp_mod, "collect_citation_candidates", lambda *a, **k: [])
    result = mcp_mod.StdinMcpServer().handle_tool_call("bybridge_collect", _bybridge_args(seed_count=3))
    text = "\n".join(b.get("text", "") for b in result["content"])
    assert "シード言語ゲート (C(iii))" in text and "1 件" in text
    assert "W_EN" in text and "W_NONE" in text and "W_JA" not in text


def test_seed_language_null_disables_gate(monkeypatch):
    ja = _lang_seed("W_JA", ["R2"], "ja")
    monkeypatch.setattr(mcp_mod, "collect_and_filter", lambda *a, **k: [ja])
    monkeypatch.setattr(mcp_mod, "collect_citation_candidates", lambda *a, **k: [])
    result = mcp_mod.StdinMcpServer().handle_tool_call(
        "bybridge_collect", _bybridge_args(seed_language=None))
    text = "\n".join(b.get("text", "") for b in result["content"])
    assert "W_JA" in text and "シード言語ゲート" not in text


# --- Plan X: bybridge delegation materials mode -------------------------------

def test_materials_mode_returns_scoreable_json_with_bridge_signals(monkeypatch):
    import json as _json
    seed = _seed_work("S1", ["B1"])
    seed.language = "en"
    cand = _seed_work("W_CAND", ["B1"])
    cand.abstract = "cross-domain abstract"
    monkeypatch.setattr(mcp_mod, "collect_and_filter", lambda *a, **k: [seed])
    monkeypatch.setattr(mcp_mod, "collect_citation_candidates", lambda *a, **k: [cand])
    result = mcp_mod.StdinMcpServer().handle_tool_call(
        "bybridge_collect", _bybridge_args(materials=True))
    text = "\n".join(b.get("text", "") for b in result["content"])
    assert "delegate_finalize" in text and "接地契約" in text      # scoring + grounding instructions
    payload = text[text.index("["):]
    mats = _json.loads(payload)
    assert mats[0]["id"] == "W_CAND"
    assert "bridge_signals" in mats[0]
    assert mats[0]["bridge_signals"]["shared_bridge_count"] == 1
