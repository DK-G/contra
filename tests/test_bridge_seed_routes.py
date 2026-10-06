"""F-46: bybridge reports which seed leg each pooled bridge and each candidate came through.

seihai 2026-10-06: the per-bridge meter read 42% / 30%, yet two off-topic lexical seeds cited
27 and 26 of the 50 pooled bridges while the semantic seeds cited 0-5 each, and about 45 of the
60 candidates were corporate finance. The replay that night (45 live bridges, 60 candidates)
split 30 / 15 / 0 bridges and 39 / 21 / 0 candidates between lexical-only, semantic-only and
both — and its SEMANTIC leg was the one that had drifted (voting theory), so the line names
both sides and does not tell the caller which to read.
"""

from __future__ import annotations

import json

import pytest

import src.mcp_server as mcp_mod
from src.core.models import Work
from src.pipeline.bridge_diagnostics import (
    ROUTE_BOTH,
    ROUTE_LEXICAL,
    ROUTE_NONE,
    ROUTE_SEMANTIC,
    candidate_route,
    render_seed_routes,
    seed_routes,
)


def _work(wid: str, refs, title: str = "") -> Work:
    return Work(id=wid, title=title or wid, year=2024, venue="v", doi=None, cited_by_count=0,
                abstract="a", referenced_works=list(refs))


def _small():
    seeds = [_work("L1", ["A1", "A2", "X"], "factor zoo"), _work("L2", ["A2", "A3"], "anomalies"),
             _work("S1", ["B1", "B2", "X"], "ranking and selection")]
    bridges = ["A1", "A2", "A3", "B1", "B2", "X", "ORPHAN"]
    cands = [_work("c1", ["A1"]), _work("c2", ["A2", "A3"]), _work("c3", ["B1"]),
             _work("c4", ["A1", "B2"]), _work("c5", ["X"]), _work("c6", ["ZZ"])]
    return seeds, cands, bridges


def test_pool_and_candidates_are_split_by_the_leg_of_the_citing_seeds():
    seeds, cands, bridges = _small()
    r = seed_routes(seeds, cands, bridges, {"S1"})
    assert r.bridges == {ROUTE_LEXICAL: 3, ROUTE_SEMANTIC: 2, ROUTE_BOTH: 1, ROUTE_NONE: 1}
    assert r.candidates == {ROUTE_LEXICAL: 2, ROUTE_SEMANTIC: 1, ROUTE_BOTH: 2, ROUTE_NONE: 1}
    assert [candidate_route(c, r.bridge_route) for c in cands] == [
        ROUTE_LEXICAL, ROUTE_LEXICAL, ROUTE_SEMANTIC, ROUTE_BOTH, ROUTE_BOTH, ROUTE_NONE]
    assert [s.title for s in r.top_seeds[ROUTE_LEXICAL]] == ["factor zoo", "anomalies"]
    assert [s.title for s in r.top_seeds[ROUTE_SEMANTIC]] == ["ranking and selection"]


def test_a_seed_found_by_both_legs_counts_as_semantic():
    seeds, cands, bridges = _small()
    r = seed_routes(seeds, cands, bridges, {"S1", "L2"})
    assert r.bridge_route["A3"] == ROUTE_SEMANTIC and r.bridge_route["A2"] == ROUTE_BOTH


def test_observed_2026_10_06_two_lexical_seeds_supply_over_half_the_contributions():
    # seihai's roster: two factor-zoo seeds citing 27 and 26 of the 50 pooled bridges, the
    # semantic seeds 0-5 each, about 100 contributions in all.
    pool = [f"B{i}" for i in range(50)]
    seeds = [_work("L1", pool[:27], "… and the Cross-Section of Expected Returns"),
             _work("L2", pool[20:46], "Navigating the factor zoo")]
    seeds += [_work(f"L{i}", pool[i:i + 3]) for i in range(3, 10)]            # 7 x 3 = 21
    sem = [_work(f"S{i}", pool[46:46 + n]) for i, n in enumerate([0, 0, 1, 2, 2, 3, 4, 4, 4, 4])]
    r = seed_routes(seeds + sem, [], pool, {w.id for w in sem})
    assert r.total_contribution == 27 + 26 + 21 + 24
    text = render_seed_routes(r)
    assert ("語彙側で bridge 寄与の大きいシード: … and the Cross-Section of Expected Returns（27 本）／"
            "Navigating the factor zoo（26 本）＝全シードの延べ寄与 98 本の 54%") in text
    assert r.bridges[ROUTE_SEMANTIC] == 4 and r.bridges[ROUTE_LEXICAL] == 46


def _replay_shape():
    # 2026-10-06 replay: 30 lexical-only and 15 semantic-only bridges, none shared;
    # 39 candidates through the first group alone, 21 through the second.
    lex_b = [f"A{i}" for i in range(30)]
    sem_b = [f"B{i}" for i in range(15)]
    seeds = [_work("L1", lex_b[:16], "factor zoo"), _work("L2", lex_b[14:], "anomalies"),
             _work("S1", sem_b[:10], "noisy votes"), _work("S2", sem_b[6:], "wrong opinions")]
    cands = ([_work(f"cl{i}", [lex_b[i % 30]]) for i in range(39)]
             + [_work(f"cs{i}", [sem_b[i % 15]]) for i in range(21)])
    return seed_routes(seeds, cands, lex_b + sem_b, {"S1", "S2"})


def test_replay_2026_10_06_reads_as_two_disjoint_ancestries():
    text = render_seed_routes(_replay_shape(), lexical_topic_fraction=0.0)
    assert "語彙由来シードだけが引用 30 本／semantic 由来シードだけ 15 本／両方 0 本" in text
    assert "語彙側の bridge だけを経由 39 件／semantic 側だけ 21 件／両方 0 件" in text
    assert "⚠" in text and "60 件は片方のレッグの祖先文献だけを経由" in text


def test_the_warning_names_both_sides_and_does_not_pick_one():
    # On the replay the semantic leg was the drifted one; "read the semantic side" would have
    # sent the caller to voting theory.
    text = render_seed_routes(_replay_shape(), lexical_topic_fraction=0.0)
    assert "どちらが主題かは" in text and "semantic 側が外れることもあります" in text
    assert "semantic 由来の bridge を経由する" not in text


@pytest.mark.parametrize("fraction", [None, 0.5, 1.0])
def test_no_warning_when_the_legs_agree_or_were_not_compared(fraction):
    text = render_seed_routes(_replay_shape(), lexical_topic_fraction=fraction)
    assert "⚠" not in text and "bridge の供給元 (F-46)" in text


def test_no_warning_when_every_candidate_crosses_both_sides():
    seeds = [_work("L1", ["A"]), _work("S1", ["B"])]
    r = seed_routes(seeds, [_work("c", ["A", "B"])], ["A", "B"], {"S1"})
    assert "⚠" not in render_seed_routes(r, lexical_topic_fraction=0.0)


# --- MCP wiring ---------------------------------------------------------------------------

def _topic_work(wid, refs, topic):
    w = _work(wid, refs)
    w.source_meta = {"primary_topic_name": topic, "primary_topic_id": topic,
                     "primary_topic_field_id": "20", "primary_topic_field_name": "Economics"}
    return w


def _run(monkeypatch, *, semantic: bool, **extra) -> str:
    lex = [_topic_work("L1", ["A1", "A2"], "Anomalies"), _topic_work("L2", ["A1", "A2"], "Anomalies")]
    sem = [_topic_work("S1", ["B1", "B2"], "Selection"), _topic_work("S2", ["B1", "B2"], "Selection")]
    cands = [_work("C1", ["A1"]), _work("C2", ["A2"]), _work("C3", ["B1"])]
    monkeypatch.setattr(mcp_mod, "resolve_work_labels", lambda *a, **k: {})
    monkeypatch.setattr(mcp_mod, "filter_live_bridges", lambda b, *a, **k: (set(b), []))
    monkeypatch.setattr(mcp_mod, "collect_and_filter", lambda *a, **k: list(lex))
    monkeypatch.setattr(mcp_mod, "collect_seeds_semantic_report",
                        lambda *a, **k: ((list(sem), {"raw": 2, "supplied": 2}) if semantic else ([], None)))
    monkeypatch.setattr(mcp_mod, "collect_citation_candidates", lambda *a, **k: list(cands))
    from src.openalex import client as _client
    _client.reset_run_stats()
    res = mcp_mod.StdinMcpServer().handle_tool_call("bybridge_collect", {
        "theme_overview": "t" * 200, "goal": "g", "why_problem": "w",
        "approach_type": "application", "assumptions": ["a", "b"], "scope_field": "economics",
        "no_history": True, "min_seeds": 0, "seed_count": 4, "bridge_count": 3,
        "materials": True, **extra,
    })
    return res["content"][0]["text"]


def _materials(text: str):
    return json.loads(text[text.index("\n["):])


def test_materials_carry_the_route_of_every_candidate_and_the_line(monkeypatch):
    text = _run(monkeypatch, semantic=True)
    assert "bridge の供給元 (F-46): bridge プール 4 本＝語彙由来シードだけが引用 2 本／semantic 由来シードだけ 2 本" in text
    assert "⚠ 2 つのレッグのシードはトピックが重なっておらず" in text
    assert text.index("bridge の供給元 (F-46)") < text.index("収集診断:")
    routes = {m["id"]: m["bridge_signals"]["seed_route"] for m in _materials(text)}
    assert routes == {"C1": ROUTE_LEXICAL, "C2": ROUTE_LEXICAL, "C3": ROUTE_SEMANTIC}
    assert "bridge_signals.seed_route は" in text.split("\n", 1)[0]


def test_the_route_tag_survives_diagnostics_off(monkeypatch):
    text = _run(monkeypatch, semantic=True, diagnostics=False)
    assert "bridge の供給元" not in text
    assert all("seed_route" in m["bridge_signals"] for m in _materials(text))


def test_one_leg_means_no_split_is_claimed(monkeypatch):
    text = _run(monkeypatch, semantic=False)
    assert "bridge の供給元" not in text and "seed_route" not in text
