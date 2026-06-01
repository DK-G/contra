"""Tests for history.py — theme hash, load, and save."""

import tempfile
from pathlib import Path

from src.core.models import ThemeHistory
from src.pipeline.history import compute_theme_hash, load_history, save_history


def test_hash_is_deterministic():
    assert compute_theme_hash("テーマ概要") == compute_theme_hash("テーマ概要")


def test_hash_length_is_16():
    assert len(compute_theme_hash("any text")) == 16


def test_hash_differs_for_different_inputs():
    assert compute_theme_hash("テーマA") != compute_theme_hash("テーマB")


def test_load_returns_empty_when_file_missing():
    with tempfile.TemporaryDirectory() as tmp:
        h = load_history("nonexistent_hash", Path(tmp))
    assert h.used_ids == []
    assert h.used_titles == []
    assert h.used_dois == []


def test_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        base = ThemeHistory(theme_hash="abc123", used_ids=[], generated_at="")
        save_history(base, ["id1", "id2"], ["title1"], ["doi1"], Path(tmp))
        loaded = load_history("abc123", Path(tmp))
    assert "id1" in loaded.used_ids
    assert "id2" in loaded.used_ids
    assert "title1" in loaded.used_titles
    assert "doi1" in loaded.used_dois


def test_save_merges_with_existing():
    with tempfile.TemporaryDirectory() as tmp:
        base = ThemeHistory(theme_hash="abc", used_ids=[], generated_at="")
        save_history(base, ["id1"], [], [], Path(tmp))
        existing = load_history("abc", Path(tmp))
        save_history(existing, ["id2"], [], [], Path(tmp))
        loaded = load_history("abc", Path(tmp))
    assert "id1" in loaded.used_ids
    assert "id2" in loaded.used_ids


def test_save_deduplicates_ids():
    with tempfile.TemporaryDirectory() as tmp:
        base = ThemeHistory(theme_hash="abc", used_ids=[], generated_at="")
        save_history(base, ["id1", "id1"], [], [], Path(tmp))
        loaded = load_history("abc", Path(tmp))
    assert loaded.used_ids.count("id1") == 1


def test_empty_dois_not_saved():
    with tempfile.TemporaryDirectory() as tmp:
        base = ThemeHistory(theme_hash="abc", used_ids=[], generated_at="")
        save_history(base, ["id1"], ["title1"], ["", None], Path(tmp))  # type: ignore[list-item]
        loaded = load_history("abc", Path(tmp))
    assert "" not in loaded.used_dois


def test_generated_at_is_updated_on_save():
    with tempfile.TemporaryDirectory() as tmp:
        base = ThemeHistory(theme_hash="ts", used_ids=[], generated_at="")
        save_history(base, ["x"], [], [], Path(tmp))
        loaded = load_history("ts", Path(tmp))
    assert loaded.generated_at != ""
