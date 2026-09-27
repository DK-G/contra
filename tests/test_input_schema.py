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


# --- F-21: the tool's self-description must not drift from its validator -----------------
# Observed 3 times (2026-09-05 / 09-11 / 09-12): the approach_type description offered
# "system-building" (rejected by the validator) and `assumptions` sat outside `required`
# while the validator demanded 2-5 items. Each occurrence cost the caller a round trip.

def _theme_tools():
    from src.mcp_server import StdinMcpServer
    return [t for t in StdinMcpServer().list_tools()
            if "approach_type" in t["inputSchema"]["properties"]]


def test_every_schema_enum_is_exactly_the_validator_set():
    from src.core.input_schema import APPROACH_TYPES, SCALE_TYPES, TIME_RANGE_TYPES
    for tool in _theme_tools():
        props = tool["inputSchema"]["properties"]
        assert props["approach_type"]["enum"] == sorted(APPROACH_TYPES), tool["name"]
        assert props["scope_scale"]["enum"] == sorted(SCALE_TYPES), tool["name"]
        assert props["scope_time_range"]["enum"] == sorted(TIME_RANGE_TYPES), tool["name"]


def test_every_advertised_value_actually_validates():
    """The drift that hurt was a value the schema OFFERED and the validator refused."""
    for tool in _theme_tools():
        props = tool["inputSchema"]["properties"]
        for approach in props["approach_type"]["enum"]:
            for scale in props["scope_scale"]["enum"]:
                for rng in props["scope_time_range"]["enum"]:
                    d = _v(approach_type=approach)
                    d["scope"] = {"field": "CS", "scale": scale, "time_range": rng}
                    validate_and_normalize(d)
        assert props["approach_type"]["default"] in props["approach_type"]["enum"]
        assert props["scope_scale"]["default"] in props["scope_scale"]["enum"]


def test_assumptions_is_required_and_bounded_in_every_schema():
    from src.core.input_schema import MAX_ASSUMPTIONS, MIN_ASSUMPTIONS
    for tool in _theme_tools():
        schema = tool["inputSchema"]
        assert "assumptions" in schema["required"], tool["name"]
        prop = schema["properties"]["assumptions"]
        assert prop["minItems"] == MIN_ASSUMPTIONS and prop["maxItems"] == MAX_ASSUMPTIONS


def test_rejection_messages_name_the_allowed_set_and_the_value():
    with pytest.raises(InputValidationError) as e:
        validate_and_normalize(_v(approach_type="system-building"))
    assert "system-building" in str(e.value) and "application" in str(e.value)
    d = _v()
    d["scope"] = {"field": "CS", "scale": "micro", "time_range": "no_limit"}
    with pytest.raises(InputValidationError) as e:
        validate_and_normalize(d)
    assert "micro" in str(e.value) and "theoretical" in str(e.value)
    with pytest.raises(InputValidationError) as e:
        validate_and_normalize(_v(assumptions=[]))
    assert "got 0" in str(e.value)


# --- F-34 (2026-09-27): the schema's `required` set must be enough for the validator ------
# F-21's twin on another key: scope_field sat outside `required` while the validator demanded
# a non-empty scope.field. Every first call of the 2026-09-27 hindsight test (4/4, via
# byserendipity_discover) and the seihai 2026-09-26 byrepo call failed with
# "scope.field is required" and cost a round trip.

def _minimal_value(key, prop):
    from src.core.input_schema import MIN_OVERVIEW_CHARS
    if key == "theme_overview":
        return "x" * MIN_OVERVIEW_CHARS
    if prop.get("type") == "array":
        return ["item" + str(i) for i in range(prop.get("minItems", 0))]
    if "enum" in prop:
        return prop["default"]
    return "x"


def test_schema_required_args_alone_pass_the_validator():
    from src.mcp_server import _build_theme_input
    for tool in _theme_tools():
        schema = tool["inputSchema"]
        args = {k: _minimal_value(k, schema["properties"][k]) for k in schema["required"]}
        try:
            _build_theme_input(args)
        except InputValidationError as exc:
            raise AssertionError(f"{tool['name']}: schema-required args rejected: {exc}")


def test_scope_field_description_names_the_openalex_fields_where_it_drives_exclusion():
    """F-37: home exclusion keys on scope_field resolving to an OpenAlex Field, so the tools
    that exclude/scope by it say which names resolve."""
    for tool in _theme_tools():
        if tool["name"] not in ("byserendipity_discover", "bybridge_collect"):
            continue
        desc = tool["inputSchema"]["properties"]["scope_field"]["description"]
        assert "Neuroscience" in desc and "Engineering" in desc, tool["name"]
