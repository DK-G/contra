"""F-86 (survey 2026-10-24/10-29/11-05/11-07): an output entry sent without a relationship
rendered 「2) テーマとの関連性: （記入なし）」 and the result never said so. It is named in one line."""

from __future__ import annotations

from src.mcp_server import StdinMcpServer
from src.pipeline.delegate import unwritten_relationship_line


THEME = {"theme_overview": "Which viewers skip a short video ad and which complete it. " * 4, "goal": "g",
         "why_problem": "w", "approach_type": "experiment", "assumptions": ["a", "b"],
         "scope_field": "Business", "scope_scale": "small", "scope_time_range": "last_10_years",
         "keywords_include": ["video"], "concern": "c", "no_history": True}


def _cand(wid: str, ps: float, md: float, **prose) -> dict:
    return {"id": wid, "title": f"title {wid}", "abstract": "Animals leave a patch early.", "year": 2001,
            "venue": "J", "cited_by_count": 1, "doi": None, "purpose_sim": ps, "mechanism_dist": md,
            "structural_depth": 0.7, **prose}


def _finalize(cands: list) -> str:
    args = {**THEME, "candidates": cands, "count": 3}
    return StdinMcpServer().handle_tool_call("delegate_finalize", args)["content"][0]["text"]


def _batch(**w1_prose) -> list:
    return ([_cand("W101", 0.7, 0.85, **w1_prose), _cand("W102", 0.68, 0.8, summary="要約だけ")]
            + [_cand(f"W2{i:02d}", 0.2, 0.3) for i in range(10)])


def test_rendered_entries_without_relationship_are_named():
    text = _finalize(_batch(relationship="patch leaving mirrors skipping",
                            theme_quote="which viewers skip", source_quote="Animals leave a patch"))
    line = next(l for l in text.splitlines() if "F-86" in l)
    assert "出力 2 本のうち 1 本" in line and "W102" in line and "W101" not in line


def test_no_line_when_every_rendered_entry_has_relationship():
    prose = {"relationship": "r", "theme_quote": "which viewers skip", "source_quote": "Animals leave a patch"}
    cands = [_cand("W101", 0.7, 0.85, **prose), _cand("W102", 0.68, 0.8, **prose)]
    cands += [_cand(f"W2{i:02d}", 0.2, 0.3) for i in range(10)]
    assert "F-86" not in _finalize(cands)


def test_grounding_failures_and_unrendered_are_left_out():
    rendered = {"W1", "W2"}
    mats = [{"id": "W1"}, {"id": "W2", "relationship": " "}, {"id": "W3"}]
    line = unwritten_relationship_line(mats, rendered, grounding_failed_ids={"W1"})
    assert line is not None and "1 本" in line and "W2" in line and "W1," not in line and "W3" not in line
    assert unwritten_relationship_line(mats, rendered, grounding_failed_ids={"W1", "W2"}) is None
