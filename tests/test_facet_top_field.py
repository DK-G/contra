"""F-64 (survey 2026-10-17 salon-sites): the facet "Experimental particle physics and astrophysics"
came back as radio receivers and radar thresholds (Engineering 25/50, Physics 11/50 in the live
probe). The facet breakdown names each facet's most common OpenAlex Field so the drift is
visible against the facet's own name."""

from __future__ import annotations

from test_same_abstract_dedup import _abstract, _raw, _run

from src.mcp_server import _facet_breakdown_line


def _with_field(raw, name):
    raw["primary_topic"]["field"]["display_name"] = name
    return raw


def test_breakdown_names_the_facet_main_field(monkeypatch):
    page = ([_with_field(_raw(f"E{i}", f"eng {i}", _abstract(i)), "Engineering") for i in range(3)]
            + [_with_field(_raw(f"P{i}", f"phys {i}", _abstract(50 + i)), "Physics and Astronomy")
               for i in range(2)])
    _, stats = _run(monkeypatch, [page])
    assert stats[0]["top_field"] == {"name": "Engineering", "count": 3}
    assert "（主な分野 Engineering 3/5）" in _facet_breakdown_line(stats)


def test_no_note_without_the_record():
    line = _facet_breakdown_line([{"domain": "d", "status": "ok", "returned": 5, "kept": 5, "selected": 5}])
    assert "主な分野" not in line
