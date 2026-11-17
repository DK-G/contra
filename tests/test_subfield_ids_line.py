"""F-90 (llm-evolve 2026-11-17): a caller aims every facet at a branch of mathematics and keeps or
drops candidates by branch. byserendipity raw can name each candidate's OpenAlex Subfield on one
grouped line, opt-in (`subfield_line`). The exclusion stays per Field (F-37 declined a
Subfield-level exclusion), and the default output does not change."""

from __future__ import annotations

from typing import Any, Dict

import src.mcp_server as mcp_mod
from src.core.models import Work
from src.mcp_server import StdinMcpServer, _subfield_ids_line


def _w(wid: str, sub: str | None, field: str | None = "Mathematics") -> Work:
    meta: Dict[str, Any] = {}
    if sub:
        meta["primary_topic_subfield_name"] = sub
    if field:
        meta["primary_topic_field_name"] = field
    return Work(id=f"https://openalex.org/{wid}", title=wid, year=2020, venue="v", doi=None,
                cited_by_count=0, abstract="an abstract", source_meta=meta)


def test_groups_ids_by_subfield_with_field_largest_first():
    line = _subfield_ids_line([
        _w("W1", "Algebra and Number Theory"), _w("W2", "Geometry and Topology"),
        _w("W3", "Geometry and Topology"), _w("W4", None, None),
        _w("W5", "Statistics and Probability", "Mathematics")])
    body = line.split("）: ", 1)[1]
    assert body.startswith("Geometry and Topology（Mathematics） 2: W2, W3 ／ ")
    assert "Algebra and Number Theory（Mathematics） 1: W1" in body
    assert "不明 1: W4" in body
    assert "除外には使っていません" in line


def _args(**over) -> Dict[str, Any]:
    args = {
        "theme_overview": "Improve a small local language model by merging fine-tuned weights. " * 4,
        "goal": "higher benchmark scores", "why_problem": "merges interfere",
        "approach_type": "theory", "assumptions": ["a" * 5, "b" * 5],
        "scope_field": "Computer Science", "scope_scale": "small", "scope_time_range": "no_limit",
        "raw_only": True, "no_history": True,
        "facets": [{"domain": "optimal transport", "pseudo_abstract": "coupling two measures"}],
        "structure": "combine several solutions into one without destroying each one's gains",
    }
    args.update(over)
    return args


def _stub(monkeypatch) -> None:
    def _collect(theme, spec, cfg=None, **k):
        return [_w("W7", "Geometry and Topology"), _w("W8", "Analysis")]
    monkeypatch.setattr(mcp_mod, "collect_track_b_from_spec", _collect)


def _text(res) -> str:
    return "\n".join(b.get("text", "") for b in res["content"])


def test_line_appears_only_when_asked(monkeypatch):
    _stub(monkeypatch)
    off = _text(StdinMcpServer().handle_tool_call("byserendipity_discover", _args()))
    on = _text(StdinMcpServer().handle_tool_call("byserendipity_discover", _args(subfield_line=True)))
    assert "OpenAlex Subfield" not in off
    assert "OpenAlex Subfield" in on
    assert "Geometry and Topology（Mathematics） 1: W7" in on
    # display only: the Field line and the materials are the same either way
    strip = lambda t: "\n".join(l for l in t.splitlines() if "OpenAlex Subfield" not in l)
    assert strip(on) == strip(off)


def test_schema_declares_subfield_line_off_by_default():
    tools = {t["name"]: t for t in StdinMcpServer().list_tools()}
    props = tools["byserendipity_discover"]["inputSchema"]["properties"]
    assert props["subfield_line"]["default"] is False
