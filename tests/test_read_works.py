"""F-75 (survey 2026-10-14..10-31, seihai 2026-10-31): the caller re-fetched the abstracts it had to
read by hand, on every run. read_works takes the ids and returns echoable materials in one call."""

from __future__ import annotations

import json

import src.mcp_server as srv
from src.mcp_server import StdinMcpServer
from src.pipeline.delegate import verify_grounding


def _raw(wid: str, abstract: str = "alpha beta") -> dict:
    index = {w: [i] for i, w in enumerate(abstract.split())}
    return {"id": f"https://openalex.org/{wid}", "display_name": f"Title {wid}", "publication_year": 2020,
            "cited_by_count": 3, "abstract_inverted_index": index, "type": "article"}


def _call(monkeypatch, ids, results):
    calls = []

    class Client:
        def get(self, params):
            calls.append(params)
            return {"results": results}

    monkeypatch.setattr(srv, "OpenAlexClient", Client)
    result = StdinMcpServer().handle_tool_call("read_works", {"ids": ids})
    return result, result["content"][0]["text"], calls


def _materials(text: str) -> list:
    return json.loads(text[text.index("\n[\n") + 1:text.rindex("]") + 1])


def test_one_call_in_the_order_asked_with_the_full_abstract(monkeypatch):
    long_abstract = " ".join(f"w{i}" for i in range(400))
    result, text, calls = _call(monkeypatch, ["W2", "https://openalex.org/W1", "W2"],
                                [_raw("W1", long_abstract), _raw("W2")])
    assert not result["isError"] and len(calls) == 1
    assert calls[0]["filter"] == "ids.openalex:W2|W1" and calls[0]["per_page"] == 2
    mats = _materials(text)
    assert [m["id"] for m in mats] == ["https://openalex.org/W2", "https://openalex.org/W1"]
    assert mats[1]["abstract"] == long_abstract and "abstract_full_chars" not in mats[1]
    assert "referenced_works" not in mats[0] and "concept_tags" not in mats[0]


def test_names_ids_openalex_does_not_have_and_ids_of_the_wrong_shape(monkeypatch):
    _, text, _ = _call(monkeypatch, ["W1", "W9", "10.1/x"], [_raw("W1")])
    assert "OpenAlex に無い id（統合・削除された可能性）: W9" in text
    assert "id の形が違うので読みませんでした: 10.1/x" in text


def test_refuses_without_calling_when_nothing_is_readable_or_too_many(monkeypatch):
    for ids in ([], ["doi:1"], [f"W{i}" for i in range(51)]):
        result, _, calls = _call(monkeypatch, ids, [])
        assert result["isError"] and not calls


def test_a_returned_material_grounds_a_quote_from_anywhere_in_the_abstract(monkeypatch):
    abstract = "The deciding sentence is at the very middle of this abstract and nowhere else."
    _, text, _ = _call(monkeypatch, ["W1"], [_raw("W1", abstract)])
    theme = "テーマの文をそのまま抜粋する"
    assert not verify_grounding({**_materials(text)[0], "relationship": "x", "theme_quote": theme,
                                 "source_quote": "deciding sentence is at the very middle"}, theme)


def test_the_schema_declares_it(monkeypatch):
    _, text, _ = _call(monkeypatch, ["W1"], [_raw("W1")])
    assert "受け付けません" not in text
    assert any(t["name"] == "read_works" for t in StdinMcpServer().list_tools())
