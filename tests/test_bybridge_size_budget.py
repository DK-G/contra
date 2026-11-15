"""F-88 (2026-11-15): bybridge takes a size budget.

seihai passed ``materials_max_chars`` to bybridge six weeks running; it was not declared (F-57
named it each time) and the result went to a file at 56.9k-61.9k chars even with lean and a
250-300 char abstract cut, because ``bridge_signals`` outweighed the abstracts.
"""
import json
import re

import pytest

import src.mcp_server as mcp_mod
from src.core.models import Work


@pytest.fixture
def bridge_offline(monkeypatch):
    monkeypatch.setattr(mcp_mod, "resolve_work_labels", lambda *a, **k: {})
    monkeypatch.setattr(mcp_mod, "filter_live_bridges", lambda b, *a, **k: (set(b), []))
    monkeypatch.setattr(mcp_mod, "collect_seeds_semantic_report", lambda *a, **k: ([], None))
    from src.openalex import client as _client
    _client.reset_run_stats()


def _materials(text: str):
    i = text.index("[\n{")
    return json.loads(text[i:text.rindex("\n]") + 2])


def _run(monkeypatch, **over) -> str:
    seed = Work(id="S1", title="s", year=2024, venue="v", doi=None, cited_by_count=0,
                abstract="a", referenced_works=["B1"])
    cands = [Work(id=f"https://openalex.org/W{i:08d}", title=f"candidate title {i}", year=2024,
                  venue="Journal of Things", doi=f"https://doi.org/10.1000/{i}", cited_by_count=i,
                  abstract="Background sentence here. " * 10 + f"The result {i} is stated at the end.",
                  referenced_works=["B1"]) for i in range(60)]
    monkeypatch.setattr(mcp_mod, "collect_and_filter", lambda *a, **k: [seed])
    monkeypatch.setattr(mcp_mod, "collect_citation_candidates", lambda *a, **k: cands)
    args = {"theme_overview": "t" * 200, "goal": "g", "why_problem": "w",
            "approach_type": "application", "assumptions": ["a", "b"], "scope_field": "medicine",
            "materials": True, "materials_lean": True, "no_history": True, "min_seeds": 0,
            "seed_count": 2}
    args.update(over)
    res = mcp_mod.StdinMcpServer().handle_tool_call("bybridge_collect", args)
    return "\n".join(b.get("text", "") for b in res["content"])


def test_without_budget_the_output_is_unchanged(monkeypatch, bridge_offline):
    text = _run(monkeypatch)
    mats = _materials(text)
    assert all(isinstance(m["bridge_signals"], dict) for m in mats)
    assert all(mcp_mod.BRIDGE_SIGNAL_ROW_KEY not in m for m in mats)
    assert "F-88" not in text and "F-57" not in text


def test_budget_is_declared_and_rows_carry_the_same_values(monkeypatch, bridge_offline):
    full = _materials(_run(monkeypatch))
    text = _run(monkeypatch, materials_max_chars=200_000)
    assert "F-57" not in text                       # declared now, so not named as ignored
    mats = _materials(text)
    assert len(mats) == 60
    order = mcp_mod.BRIDGE_SIGNAL_ROW_ORDER
    for f, m in zip(full, mats):
        assert "bridge_signals" not in m
        assert m[mcp_mod.BRIDGE_SIGNAL_ROW_KEY] == [f["bridge_signals"].get(k) for k in order]
    assert "bridge_signals_row (F-88)" in text and ", ".join(order) in text
    assert "収まりました" in text and "抄録は切っていません" in text


def test_budget_fits_by_cutting_abstracts_from_the_end(monkeypatch, bridge_offline):
    uncut = len(_run(monkeypatch, materials_max_chars=200_000))
    budget = uncut - 3000
    text = _run(monkeypatch, materials_max_chars=budget)
    assert len(text) <= budget
    mats = _materials(text)
    assert all(m["abstract"].startswith("…") and m["abstract"].endswith("stated at the end.")
               for m in mats)
    assert re.search(r"抄録の末尾を \d+ 字にしました", text)


def test_budget_that_cannot_be_met_says_so(monkeypatch, bridge_offline):
    text = _run(monkeypatch, materials_max_chars=5_000)
    assert "⚠ 大きさの予算 (materials_max_chars 5,000 字) に収まりません" in text
    assert len(_materials(text)) == 60
