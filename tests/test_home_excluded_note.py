"""F-71 (survey 2026-10-26 metagmo): the ecoacoustics facet's two target papers ("Long-duration,
false-colour spectrograms …") had Computer Science as their OpenAlex Field, so the home exclusion
(scope_field Computer Science) dropped them, and the breakdown only said "kept 9" of 27. The
breakdown now names how many the exclusion took and the first few in the endpoint's order."""

from __future__ import annotations

from test_same_abstract_dedup import _abstract, _raw, _run

from src.mcp_server import _facet_breakdown_line


def _home(raw, title):
    raw["title"] = raw["display_name"] = title
    raw["primary_topic"]["field"] = {"id": "https://openalex.org/fields/17",
                                     "display_name": "Computer Science"}
    return raw


def test_breakdown_names_what_the_home_exclusion_took(monkeypatch):
    page = ([_home(_raw("H1", "x", _abstract(90)),
                   "Long-duration, false-colour spectrograms for detecting species in large audio data-sets"),
             _home(_raw("H2", "y", _abstract(91)), "False-colour spectrograms of long duration acoustic recordings")]
            + [_raw(f"K{i}", f"kept {i}", _abstract(i)) for i in range(5)])
    _, stats = _run(monkeypatch, [page])
    assert stats[0]["home_excluded"] == 2
    line = _facet_breakdown_line(stats)
    assert "ホーム除外・重複後 5" in line
    assert ("（ホーム除外 2 件・類似度順の先頭: H1「Long-duration, false-colour spectrograms for detecting"
            in line)
    assert "（Computer Science） / H2「False-colour spectrograms of long duration acoustic recordings」（Computer Science））" in line


def test_head_is_capped_and_no_note_without_exclusions(monkeypatch):
    page = ([_home(_raw(f"H{i}", "x", _abstract(80 + i)), f"home {i}") for i in range(4)]
            + [_raw(f"K{i}", f"kept {i}", _abstract(i)) for i in range(8)])
    _, stats = _run(monkeypatch, [page])
    assert stats[0]["home_excluded"] == 4 and len(stats[0]["home_excluded_head"]) == 3
    assert "ホーム除外 4 件" in _facet_breakdown_line(stats)
    line = _facet_breakdown_line([{"domain": "d", "status": "ok", "returned": 5, "kept": 5, "selected": 5}])
    assert "ホーム除外 " not in line
