"""Tests for input_schema.validate_and_normalize."""

import pytest
from src.core.input_schema import validate_and_normalize, InputValidationError

_OVERVIEW = "a" * 200

_BASE = {
    "theme_overview": _OVERVIEW,
    "goal": "目的",
    "why_problem": "問題意識",
    "approach_type": "experiment",
    "assumptions": ["仮説1", "仮説2"],
    "scope": {"field": "CS", "scale": "small", "time_range": "last_10_years"},
    "keywords": {"include": [], "exclude": []},
}


def _v(**overrides):
    d = dict(_BASE)
    d.update(overrides)
    return d


def test_valid_payload_returns_theme_input():
    result = validate_and_normalize(_v())
    assert result.approach_type == "experiment"
    assert result.scope.field == "CS"


def test_missing_theme_overview_raises():
    with pytest.raises(InputValidationError):
        validate_and_normalize(_v(theme_overview=""))


def test_theme_too_short_raises():
    with pytest.raises(InputValidationError):
        validate_and_normalize(_v(theme_overview="short"))


def test_theme_too_long_raises():
    with pytest.raises(InputValidationError):
        validate_and_normalize(_v(theme_overview="a" * 1201))


def test_theme_at_min_length_passes():
    validate_and_normalize(_v(theme_overview="a" * 200))


def test_theme_at_max_length_passes():
    validate_and_normalize(_v(theme_overview="a" * 1200))


def test_invalid_approach_type_raises():
    with pytest.raises(InputValidationError):
        validate_and_normalize(_v(approach_type="unknown"))


def test_all_valid_approach_types():
    for t in ("theory", "experiment", "application"):
        r = validate_and_normalize(_v(approach_type=t))
        assert r.approach_type == t


def test_too_few_assumptions_raises():
    with pytest.raises(InputValidationError):
        validate_and_normalize(_v(assumptions=["only one"]))


def test_too_many_assumptions_raises():
    with pytest.raises(InputValidationError):
        validate_and_normalize(_v(assumptions=["a", "b", "c", "d", "e", "f"]))


def test_invalid_scale_raises():
    d = _v()
    d["scope"] = {"field": "CS", "scale": "invalid", "time_range": "last_10_years"}
    with pytest.raises(InputValidationError):
        validate_and_normalize(d)


def test_invalid_time_range_raises():
    d = _v()
    d["scope"] = {"field": "CS", "scale": "small", "time_range": "ancient"}
    with pytest.raises(InputValidationError):
        validate_and_normalize(d)


def test_concern_none_allowed():
    result = validate_and_normalize(_v(concern=None))
    assert result.concern is None


def test_concern_string_preserved():
    result = validate_and_normalize(_v(concern="心配事"))
    assert result.concern == "心配事"


def test_concern_empty_string_becomes_none():
    result = validate_and_normalize(_v(concern=""))
    assert result.concern is None


def test_keywords_whitespace_stripped():
    d = _v()
    d["keywords"] = {"include": ["  kw1  "], "exclude": []}
    result = validate_and_normalize(d)
    assert result.keywords.include == ["kw1"]


def test_empty_keyword_strings_dropped():
    d = _v()
    d["keywords"] = {"include": ["", "  ", "kw1"], "exclude": []}
    result = validate_and_normalize(d)
    assert result.keywords.include == ["kw1"]
