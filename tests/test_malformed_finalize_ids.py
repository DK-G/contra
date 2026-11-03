"""F-79 (seihai 2026-11-02): W4400018352x, a copying slip among 61 submitted ids, was scored and
counted in 「採点 61 件」 without a word. It is named and left out of the batch."""

from __future__ import annotations

from src.mcp_server import StdinMcpServer, _split_malformed_ids


THEME = {"theme_overview": "Fixed costs of acting and when not to act. " * 6, "goal": "g", "why_problem": "w",
         "approach_type": "experiment", "assumptions": ["a", "b"], "scope_field": "Economics",
         "scope_scale": "small", "scope_time_range": "last_10_years", "keywords_include": ["cost"],
         "concern": "c", "no_history": True}


def _cand(wid: str) -> dict:
    return {"id": wid, "purpose_sim": 0.01, "mechanism_dist": 0.9, "structural_depth": 0.6}


def test_only_ids_shaped_like_a_work_but_off_are_split_out():
    ok = ["W1", "https://openalex.org/W2", "doi:10.1/x", "", None]
    bad = ["W4400018352x", "w123", "https://openalex.org/W5 ", "https://api.openalex.org/works/W6"]
    kept, malformed = _split_malformed_ids([{"id": i} for i in ok + bad] + ["not a dict"])
    assert malformed == ["W4400018352x", "w123", "https://api.openalex.org/works/W6"]
    assert len(kept) == len(ok) + 2  # the padded URL id is accepted; the bare string stays


def test_finalize_names_the_id_and_does_not_count_it():
    args = {**THEME, "candidates": [_cand("W1"), _cand("W2"), _cand("W4400018352x")]}
    text = StdinMcpServer().handle_tool_call("delegate_finalize", args)["content"][0]["text"]
    assert "採点 2 件" in text
    assert "受け付けない id 1 件" in text and "W4400018352x" in text


def test_all_malformed_is_reported_as_empty_with_the_ids():
    args = {**THEME, "candidates": [_cand("W9x")]}
    text = StdinMcpServer().handle_tool_call("delegate_finalize", args)["content"][0]["text"]
    assert text.startswith("candidates が空です") and "W9x" in text
