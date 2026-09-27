"""F-37 (2026-09-27): say what scope_field resolved to, and say it loudly when it resolved to nothing.

Home-domain exclusion keys on ``scope_field`` resolving to an OpenAlex Field
(``resolve_field_ids``). When it resolves to nothing the exclusion is silently off: in the
2026-09-27 hindsight test "Satellite navigation (GNSS positioning)" matched no Field and five
GNSS papers came back as far-domain candidates; "Neurology" (a Subfield name, under both
Medicine and Neuroscience) matched no Field either. And when it resolves broadly
("Biomedical engineering (...)" -> the whole Engineering Field) two of three facets were
rejected as home_converged with no line saying what "home" had been taken to mean.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

import src.mcp_server as mcp_mod
from src.core.models import Work


def _args(scope_field: str, **over) -> Dict[str, Any]:
    args = {
        "theme_overview": "Estimate a smartphone position every epoch from raw measurements. " * 4,
        "goal": "robust positioning", "why_problem": "multipath and cycle slips",
        "approach_type": "application", "assumptions": ["a" * 5, "b" * 5],
        "scope_field": scope_field, "scope_scale": "small", "scope_time_range": "no_limit",
        "raw_only": True, "no_history": True,
        "facets": [{"domain": "geochronology", "pseudo_abstract": "age-depth model with outliers"}],
        "structure": "a latent trajectory observed through sparse biased measurements",
    }
    args.update(over)
    return args


def _stub_collection(monkeypatch, seen: Dict[str, Any]) -> None:
    def _collect(theme, spec, cfg=None, **k):
        seen["home_field_ids"] = k.get("home_field_ids")
        stats = k.get("stats_out")
        if stats is not None:
            stats.append({"domain": "geochronology", "status": "ok", "returned": 50,
                          "kept": 20, "selected": 1})
        return [Work(id="W1", title="t", year=2020, venue="v", doi=None, cited_by_count=0,
                     abstract="an abstract")]
    monkeypatch.setattr(mcp_mod, "collect_track_b_from_spec", _collect)


def _text(res) -> str:
    return "\n".join(b.get("text", "") for b in res["content"])


def test_unresolved_scope_field_is_named_and_the_exclusion_reported_off(monkeypatch):
    seen: Dict[str, Any] = {}
    _stub_collection(monkeypatch, seen)
    text = _text(mcp_mod.StdinMcpServer().handle_tool_call(
        "byserendipity_discover", _args("Satellite navigation (GNSS positioning)")))
    assert seen["home_field_ids"] == []
    note = [l for l in text.splitlines() if "scope_field" in l]
    assert note and "Satellite navigation (GNSS positioning)" in note[0]
    assert "ホーム除外" in note[0] and "行われていません" in note[0]
    assert "Engineering" in text            # the valid Field names are offered


def test_subfield_named_scope_points_to_its_parent_fields(monkeypatch):
    monkeypatch.setattr("src.pipeline.query.load_subfield_taxonomy_rows",
                        lambda path=None: [("2728", "Neurology", "27"), ("2808", "Neurology", "28")])
    _stub_collection(monkeypatch, {})
    text = _text(mcp_mod.StdinMcpServer().handle_tool_call("byserendipity_discover", _args("Neurology")))
    assert "Subfield" in text and "Medicine" in text and "Neuroscience" in text


def test_resolved_scope_names_the_field_used_for_exclusion(monkeypatch):
    seen: Dict[str, Any] = {}
    _stub_collection(monkeypatch, seen)
    text = _text(mcp_mod.StdinMcpServer().handle_tool_call(
        "byserendipity_discover",
        _args("Biomedical engineering (mechanical ventilation and respiratory mechanics)")))
    assert seen["home_field_ids"] == ["22"]
    note = [l for l in text.splitlines() if "scope_field" in l]
    assert note and "Engineering" in note[0] and "行われていません" not in note[0]


def test_zero_harvest_path_carries_the_scope_note(monkeypatch):
    def _none(theme, spec, cfg=None, **k):
        k["stats_out"].append({"domain": "geochronology", "status": "棄却 (home_converged)",
                               "returned": 50, "kept": 0, "selected": 0})
        return []
    monkeypatch.setattr(mcp_mod, "collect_track_b_from_spec", _none)
    text = _text(mcp_mod.StdinMcpServer().handle_tool_call(
        "byserendipity_discover", _args("Biomedical engineering")))
    note = [l for l in text.splitlines() if "scope_field" in l]
    assert note and "Engineering" in note[0]


# --- bybridge: the same scope_field scopes the lexical seed queries -----------------------

@pytest.fixture
def bridge_offline(monkeypatch):
    monkeypatch.setattr(mcp_mod, "resolve_work_labels", lambda *a, **k: {})
    monkeypatch.setattr(mcp_mod, "filter_live_bridges", lambda b, *a, **k: (set(b), []))
    monkeypatch.setattr(mcp_mod, "collect_seeds_semantic_report", lambda *a, **k: ([], None))
    seed = Work(id="S1", title="s", year=2024, venue="v", doi=None, cited_by_count=0,
                abstract="a", referenced_works=["B1"])
    cand = Work(id="C1", title="c", year=2024, venue="v", doi=None, cited_by_count=0,
                abstract="a", referenced_works=["B1"])
    seen: Dict[str, Any] = {}

    def _seeds(*a, **k):
        seen["scope_ids"] = k.get("home_field_ids")
        return [seed]
    monkeypatch.setattr(mcp_mod, "collect_and_filter", _seeds)
    monkeypatch.setattr(mcp_mod, "collect_citation_candidates", lambda *a, **k: [cand])
    from src.openalex import client as _client
    _client.reset_run_stats()
    return seen


def test_bybridge_names_an_unresolved_scope_and_the_unscoped_seeds(bridge_offline):
    text = _text(mcp_mod.StdinMcpServer().handle_tool_call("bybridge_collect", _args(
        "Satellite navigation (GNSS positioning)", min_seeds=0, seed_count=2)))
    assert bridge_offline["scope_ids"] == []
    note = [l for l in text.splitlines() if "scope_field" in l and "行われていません" in l]
    assert note and "シード" in note[0]
