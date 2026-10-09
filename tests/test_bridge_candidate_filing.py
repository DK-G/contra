"""F-44: bybridge reports where OpenAlex files each cross-domain candidate.

seihai 2026-10-02 / 2026-10-09: the caller classified 60 candidates by hand to learn that 46 and
about 35 of them were the theme's own subject under a sibling Field. Measured on 10/02: the Topic
holding 25 of the 60 candidates sat in the roster 0 times and in the semantic leg's retrieval
twice, so the home exclusion (roster Fields + Topics the roster holds twice) let it through.
Replayed on two saved 2026-10-06 runs, a shared Topic was the drift on one (23 of 60) and the
subject's papers shared no Topic on the other (0 of 60) — so the lines carry no verdict.
"""

from __future__ import annotations

import json

import src.mcp_server as mcp_mod
from src.core.models import Work
from src.pipeline.bridge_diagnostics import (
    TOPIC_SEEN_NONE,
    TOPIC_SEEN_ROSTER,
    TOPIC_SEEN_SEED_POOL,
    candidate_filing,
    candidate_filing_tag,
    render_candidate_filing,
)

_TOPICS = {
    "T1": ("Financial Markets and Investment Strategies", "Economics, Econometrics and Finance"),
    "T2": ("Stock Market Forecasting Methods", "Decision Sciences"),
    "T3": ("Corporate Finance and Governance", "Business, Management and Accounting"),
    "T4": ("Forecasting Techniques and Applications", "Decision Sciences"),
}


def _work(wid: str, topic: str = "", title: str = "", refs=()) -> Work:
    meta = {}
    if topic:
        name, field = _TOPICS[topic]
        meta = {"primary_topic_id": topic, "primary_topic_name": name,
                "primary_topic_field_name": field, "primary_topic_field_id": field[:3]}
    return Work(id=wid, title=title or wid, year=2024, venue="v", doi=None, cited_by_count=0,
                abstract="a", referenced_works=list(refs), source_meta=meta)


def _oct02():
    """The 2026-10-02 shape: T2 holds 25 of 60 candidates, 0 roster seeds, 2 retrieved seeds."""
    seeds = [_work(f"s{i}", "T1") for i in range(19)] + [_work("s19", "T3", "a stray seed")]
    pool = seeds + [_work("p1", "T2"), _work("p2", "T2")]
    cands = ([_work(f"a{i}", "T2") for i in range(25)] + [_work(f"b{i}", "T3") for i in range(18)]
             + [_work(f"c{i}", "T4") for i in range(15)] + [_work("d0"), _work("d1")])
    return seeds, pool, cands


def test_counts_candidates_by_field_and_topic():
    seeds, pool, cands = _oct02()
    f = candidate_filing(cands, seeds, pool)
    assert f.total == 60 and f.unfiled == 2
    assert f.fields[0] == ("Decision Sciences", 40)
    assert f.fields[1] == ("Business, Management and Accounting", 18)
    assert [t[:3] for t in f.topics[:2]] == [
        ("Stock Market Forecasting Methods", "Decision Sciences", 25),
        ("Corporate Finance and Governance", "Business, Management and Accounting", 18)]


def test_topic_seen_levels():
    seeds, pool, cands = _oct02()
    f = candidate_filing(cands, seeds, pool)
    assert f.seen == {TOPIC_SEEN_ROSTER: 18, TOPIC_SEEN_SEED_POOL: 25, TOPIC_SEEN_NONE: 17}
    assert sum(f.seen.values()) == f.total


def test_roster_wins_over_seed_pool():
    seeds = [_work("s0", "T2")]
    f = candidate_filing([_work("c", "T2")], seeds, seeds + [_work("p", "T2")])
    assert f.seen[TOPIC_SEEN_ROSTER] == 1 and f.seen[TOPIC_SEEN_SEED_POOL] == 0


def test_unfiled_candidate_is_none_not_a_match():
    f = candidate_filing([_work("c")], [_work("s")], [_work("p")])
    assert f.seen[TOPIC_SEEN_NONE] == 1 and f.unfiled == 1
    assert candidate_filing_tag(_work("c"), f) == {
        "openalex_field": "", "openalex_topic": "", "topic_seen": TOPIC_SEEN_NONE}


def test_tag_per_candidate():
    seeds, pool, cands = _oct02()
    f = candidate_filing(cands, seeds, pool)
    assert candidate_filing_tag(cands[0], f) == {
        "openalex_field": "Decision Sciences", "openalex_topic": "Stock Market Forecasting Methods",
        "topic_seen": TOPIC_SEEN_SEED_POOL}
    assert candidate_filing_tag(cands[25], f)["topic_seen"] == TOPIC_SEEN_ROSTER
    assert candidate_filing_tag(cands[45], f)["topic_seen"] == TOPIC_SEEN_NONE


def test_render_names_counts_and_the_roster_seed():
    seeds, pool, cands = _oct02()
    text = render_candidate_filing(candidate_filing(cands, seeds, pool))
    assert text.startswith("- 交差候補の分類 (F-44): 交差候補 60 件")
    assert "Decision Sciences 40／Business, Management and Accounting 18" in text
    assert "Topic 未分類 2 件" in text
    assert "Stock Market Forecasting Methods（Decision Sciences）25 件［名簿に絞る前のシード候補と同じ Topic］" in text
    assert "18 件［名簿のシードと同じ Topic: a stray seed］" in text
    assert "名簿のシードと同じ Topic 18 件" in text and "同じ Topic 25 件" in text
    assert "どちらにも無い Topic 17 件" in text


def test_render_gives_no_verdict():
    seeds, pool, cands = _oct02()
    text = render_candidate_filing(candidate_filing(cands, seeds, pool))
    assert "⚠" not in text
    assert "同じ Topic でも主題とは限りません" in text


def test_render_empty_when_no_candidates():
    assert render_candidate_filing(candidate_filing([], [_work("s", "T1")])) == ""


def test_long_field_tail_is_summarised():
    cands = [_work(f"c{i}", "T1") for i in range(3)]
    for i, name in enumerate(["F1", "F2", "F3", "F4", "F5", "F6"]):
        w = _work(f"x{i}")
        w.source_meta = {"primary_topic_id": f"X{i}", "primary_topic_name": f"topic {i}",
                         "primary_topic_field_name": name}
        cands.append(w)
    text = render_candidate_filing(candidate_filing(cands, []))
    assert "／ほか 2 Field" in text


# --- the MCP path: the line is in the diagnostics, the tags are on every material -------------

def _run(monkeypatch, **extra):
    seeds = [_work(f"s{i}", "T1", refs=["B1", "B2"]) for i in range(4)]
    sem = [_work("m1", "T2", refs=["B1", "B2"]), _work("m2", "T2", refs=["B1"])]
    cands = [_work("c1", "T2", "technical rules", ["B1"]), _work("c2", "T3", "governance", ["B2"]),
             _work("c3", "", "unfiled", ["B1"])]
    monkeypatch.setattr(mcp_mod, "resolve_work_labels", lambda *a, **k: {})
    monkeypatch.setattr(mcp_mod, "filter_live_bridges", lambda b, *a, **k: (set(b), []))
    monkeypatch.setattr(mcp_mod, "collect_and_filter", lambda *a, **k: list(seeds))
    monkeypatch.setattr(mcp_mod, "collect_seeds_semantic_report",
                        lambda *a, **k: (list(sem), {"raw": 2, "supplied": 2}))
    # the roster keeps the lexical seeds only, so the semantic leg's Topic is seed-pool-only
    monkeypatch.setattr(mcp_mod, "merge_seed_pools", lambda *a, **k: list(seeds))
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
    return json.loads(text[text.index("[\n"):] if "[\n" in text else text[text.index("["):])


def test_mcp_diagnostics_line_and_material_tags(monkeypatch):
    text = _run(monkeypatch)
    assert "- 交差候補の分類 (F-44): 交差候補 3 件" in text
    assert "Stock Market Forecasting Methods（Decision Sciences）1 件［名簿に絞る前のシード候補と同じ Topic］" in text
    tags = {m["id"]: m["bridge_signals"] for m in _materials(text)}
    assert tags["c1"]["topic_seen"] == TOPIC_SEEN_SEED_POOL
    assert tags["c1"]["openalex_topic"] == "Stock Market Forecasting Methods"
    assert tags["c2"]["openalex_field"] == "Business, Management and Accounting"
    assert tags["c2"]["topic_seen"] == TOPIC_SEEN_NONE
    assert tags["c3"]["topic_seen"] == TOPIC_SEEN_NONE and tags["c3"]["openalex_topic"] == ""


def test_mcp_tags_survive_diagnostics_off(monkeypatch):
    text = _run(monkeypatch, diagnostics=False)
    assert "交差候補の分類 (F-44)" not in text
    assert all("topic_seen" in m["bridge_signals"] for m in _materials(text))
