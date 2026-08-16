"""Tests for the Kaggle API client's credential handling and auth headers."""

from __future__ import annotations

import base64

from src.kaggle.client import KaggleClient, KaggleConfig


def test_new_token_uses_bearer_auth():
    client = KaggleClient(KaggleConfig(api_token="KGAT_abc123"))
    assert client.has_credentials is True
    assert client._headers("application/json")["Authorization"] == "Bearer KGAT_abc123"


def test_legacy_creds_use_basic_auth():
    client = KaggleClient(KaggleConfig(username="alice", key="secret"))
    assert client.has_credentials is True
    header = client._headers("application/json")["Authorization"]
    assert header.startswith("Basic ")
    assert base64.b64decode(header.split(" ", 1)[1]).decode() == "alice:secret"


def test_new_token_takes_precedence_over_legacy():
    client = KaggleClient(KaggleConfig(api_token="KGAT_win", username="alice", key="secret"))
    assert client._headers("application/json")["Authorization"] == "Bearer KGAT_win"


def test_no_credentials_means_no_auth_header():
    client = KaggleClient(KaggleConfig())
    assert client.has_credentials is False
    assert "Authorization" not in client._headers("application/json")


def test_incomplete_legacy_creds_are_not_usable():
    # username without key (or vice versa) can't form basic auth
    assert KaggleClient(KaggleConfig(username="alice")).has_credentials is False
    assert KaggleClient(KaggleConfig(key="secret")).has_credentials is False


def test_build_url_appends_query():
    client = KaggleClient(KaggleConfig())
    url = client._build_url("/datasets/list", {"search": "mahjong", "sortBy": "votes"})
    assert url == "https://www.kaggle.com/api/v1/datasets/list?search=mahjong&sortBy=votes"
