"""F-45: a refused OpenAlex request carries the server's own reason.

seihai 2026-10-03: `search.semantic` answered 400 on 7 facets in 4 calls, down to a 35-word
query. contra printed "HTTP Error 400: Bad Request" and advised shortening, so the caller
shortened three times for nothing. The bodies below are the ones OpenAlex returned to a probe
on 2026-10-06 (an over-long query; a misspelt filter field).
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List

import pytest

import src.pipeline.collect as collect_mod
from src.core.models import Keywords, Scope, ThemeInput
from src.mcp_server import StdinMcpServer, _facet_breakdown_line
from src.openalex.client import (
    ERROR_REASON_MAX_CHARS,
    OpenAlexClient,
    OpenAlexConfig,
    OpenAlexError,
    refused_for_length,
)
from src.pipeline.collect import CollectConfig, collect_track_b_from_spec
from src.pipeline.serendipity_query import SerendipityFacet, SerendipitySpec

TOO_LONG = {
    "error": "Search query too long",
    "error_source": "openalex-api-proxy",
    "message": "Your search is too long (2820 characters; the limit is 1500). Very long "
               "pasted-text or Boolean searches are disproportionately expensive.",
}
BAD_FIELD = {
    "error": "Invalid query parameters error.",
    "message": "primary_topic.field.idd is not a valid field. Valid fields are underscore or "
               "hyphenated versions of: " + ", ".join(f"field_{i}.search" for i in range(400)),
}


def _client() -> OpenAlexClient:
    c = OpenAlexClient(OpenAlexConfig(min_interval_sec=0.0, max_retries=2, retry_backoff_sec=0.0))
    c._sleep = lambda s: None
    return c


def _refuse(monkeypatch, code: int, body: bytes) -> List[Any]:
    calls: List[Any] = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        raise urllib.error.HTTPError("https://api.openalex.org/works", code, "Bad Request", {},
                                     io.BytesIO(body))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def _theme() -> ThemeInput:
    return ThemeInput(
        theme_overview="t", goal="g", why_problem="w", approach_type="application",
        assumptions=[], scope=Scope(field="Economics", scale="small", time_range="last_10_years"),
        keywords=Keywords(include=["k"], exclude=[]), concern=None,
    )


# --- the client ---------------------------------------------------------------------------

def test_a_400_names_the_servers_reason_and_is_not_retried(monkeypatch):
    calls = _refuse(monkeypatch, 400, json.dumps(TOO_LONG).encode())
    with pytest.raises(OpenAlexError) as err:
        _client().get({"search.semantic": "x"})
    assert len(calls) == 1
    assert "HTTP Error 400" in str(err.value)
    assert "OpenAlex の応答: Search query too long — Your search is too long (2820 characters" in str(err.value)
    assert err.value.status == 400
    assert refused_for_length(err.value) is True


def test_a_400_about_something_else_is_told_apart_and_its_long_body_is_cut(monkeypatch):
    _refuse(monkeypatch, 400, json.dumps(BAD_FIELD).encode())
    with pytest.raises(OpenAlexError) as err:
        _client().get({"filter": "primary_topic.field.idd:17"})
    assert "primary_topic.field.idd is not a valid field" in str(err.value)
    assert len(err.value.reason) <= ERROR_REASON_MAX_CHARS + 1 and err.value.reason.endswith("…")
    assert refused_for_length(err.value) is False


@pytest.mark.parametrize("body", [b"", b"<html>Bad Request</html>"])
def test_a_400_without_a_json_reason_keeps_the_old_message_shape(monkeypatch, body):
    _refuse(monkeypatch, 400, body)
    with pytest.raises(OpenAlexError) as err:
        _client().get({})
    assert str(err.value).startswith("request failed: HTTP Error 400")
    if not body:
        assert "OpenAlex の応答" not in str(err.value)
        assert refused_for_length(err.value) is None      # no reason given: nothing is claimed


def test_an_error_raised_without_a_status_claims_nothing():
    assert refused_for_length(OpenAlexError("request failed: HTTP Error 400: Bad Request")) is None


# --- the byserendipity facet ----------------------------------------------------------------

def _run_facet(monkeypatch, exc: OpenAlexError):
    sent: List[str] = []

    class _Client:
        def get(self, params):
            sent.append(params["search.semantic"])
            raise exc

    class _FakeCollector:
        def __init__(self, cfg=None):
            self.client = _Client()

    monkeypatch.setattr(collect_mod, "Collector", _FakeCollector)
    spec = SerendipitySpec(structure="s" * 700,
                           facets=[SerendipityFacet(domain="far domain", pseudo_abstract="p" * 200)])
    stats: List[Dict[str, Any]] = []
    collect_track_b_from_spec(_theme(), spec, CollectConfig(), home_field_ids=["20"], stats_out=stats)
    return sent, stats


def _refused(reason: str) -> OpenAlexError:
    exc = OpenAlexError("request failed: HTTP Error 400: Bad Request — OpenAlex の応答: " + reason)
    exc.status, exc.reason = 400, reason
    return exc


def test_a_400_that_is_not_about_length_is_not_resent_shorter(monkeypatch):
    """10/03: three manual shortenings changed nothing; contra's own retry would not either."""
    sent, stats = _run_facet(monkeypatch, _refused("Invalid query parameters error. — x is not a valid field"))
    assert len(sent) == 1
    assert stats[0]["status"].startswith("取得失敗") and "x is not a valid field" in stats[0]["status"]


def test_a_400_about_length_still_gets_the_one_shorter_retry(monkeypatch):
    sent, stats = _run_facet(monkeypatch, _refused("Search query too long — Your search is too long"))
    assert len(sent) == 2 and len(sent[1]) < len(sent[0])
    assert "Search query too long" in stats[0]["status"]


# --- the guidance ---------------------------------------------------------------------------

def test_the_facet_line_no_longer_says_a_400_means_shorten():
    line = _facet_breakdown_line([{"domain": "far", "status": "取得失敗 (request failed: HTTP Error 400)",
                                   "returned": 0, "kept": 0, "selected": 0}])
    assert "400 は pseudo_abstract を短く" not in line
    assert "OpenAlex の応答" in line and "F-45" in line


def test_the_zero_harvest_message_sends_the_caller_to_the_reason(monkeypatch):
    import src.mcp_server as mcp_mod

    def _no_works(*a, **k):
        k["stats_out"].append({
            "domain": "far domain", "returned": 0, "kept": 0, "selected": 0,
            "status": "取得失敗 (request failed: HTTP Error 400: Bad Request — OpenAlex の応答: "
                      "Invalid query parameters error. — x is not a valid field)"})
        return []

    monkeypatch.setattr(mcp_mod, "collect_track_b_from_spec", _no_works)
    res = StdinMcpServer().handle_tool_call("byserendipity_discover", {
        "theme_overview": "Patch departure under a marginal value rule. " * 6,
        "goal": "find a stopping rule", "why_problem": "budget is finite",
        "approach_type": "application", "assumptions": ["a" * 5, "b" * 5],
        "scope_field": "economics", "scope_scale": "small", "scope_time_range": "no_limit",
        "raw_only": True, "no_history": True,
        "facets": [{"domain": "far domain", "pseudo_abstract": "foraging patch leaving"}],
        "structure": "a threshold that fires on a level rather than an edge",
    })
    text = res["content"][0]["text"]
    assert "クエリ長超過が最有力" not in text
    assert "それ以外の理由なら長さの問題ではない" in text
    assert "x is not a valid field" in text
