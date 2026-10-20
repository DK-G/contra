"""F-65 (survey 2026-10-19 メタグモ): two papers from Computer Science venues passed a Computer
Science home exclusion. OpenAlex filed them under Decision Sciences and Social Sciences by
content, which the caller could not see. byserendipity raw names each candidate's Field on one
grouped line (a per-candidate key cost 65 chars of every abstract head under the budget)."""

from __future__ import annotations

from src.core.models import Work
from src.mcp_server import _field_ids_line


def _w(wid: str, field: str | None) -> Work:
    meta = {"primary_topic_field_name": field} if field else {}
    return Work(id=f"https://openalex.org/{wid}", title=wid, year=2020, venue="v", doi=None,
                cited_by_count=0, abstract=None, source_meta=meta)


def test_groups_ids_by_field_largest_first():
    line = _field_ids_line([_w("W1", "Decision Sciences"), _w("W2", "Medicine"),
                            _w("W3", "Medicine"), _w("W4", None)])
    body = line.split("）: ", 1)[1]
    assert body == "Medicine 2: W2, W3 ／ Decision Sciences 1: W1 ／ 不明 1: W4"
    assert "ホーム除外はこの Field で判定" in line
