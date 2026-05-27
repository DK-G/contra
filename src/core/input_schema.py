"""Input schema validation and normalization (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class InputValidationError(ValueError):
    """Raised when input payload fails validation."""


@dataclass
class Scope:
    field: str
    scale: str
    time_range: str


@dataclass
class Keywords:
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


@dataclass
class ThemeInput:
    theme_overview: str
    goal: str
    why_problem: str
    approach_type: str
    assumptions: List[str]
    scope: Scope
    keywords: Keywords = field(default_factory=Keywords)
    concern: Optional[str] = None


APPROACH_TYPES = {"theory", "experiment", "application"}
SCALE_TYPES = {"small", "large", "theoretical"}
TIME_RANGE_TYPES = {"last_10_years", "no_limit"}

MIN_OVERVIEW_CHARS = 200
MAX_OVERVIEW_CHARS = 1200
MIN_ASSUMPTIONS = 2
MAX_ASSUMPTIONS = 5
MAX_KEYWORDS = 5


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise InputValidationError(f"{field_name} is required")


def _limit_list_size(values: List[str], field_name: str, max_size: int) -> None:
    if len(values) > max_size:
        raise InputValidationError(f"{field_name} must be <= {max_size}")


def validate_and_normalize(payload: dict) -> ThemeInput:
    """Validate raw dict and return normalized ThemeInput.

    Minimal rules based on docs/input_min_spec.md.
    """

    if not isinstance(payload, dict):
        raise InputValidationError("payload must be a dict")

    theme_overview = payload.get("theme_overview", "")
    goal = payload.get("goal", "")
    why_problem = payload.get("why_problem", "")
    approach_type = payload.get("approach_type", "")
    assumptions = payload.get("assumptions", []) or []
    scope = payload.get("scope", {}) or {}
    keywords = payload.get("keywords", {}) or {}
    concern = payload.get("concern", None)

    _require_non_empty(theme_overview, "theme_overview")
    _require_non_empty(goal, "goal")
    _require_non_empty(why_problem, "why_problem")
    _require_non_empty(approach_type, "approach_type")

    theme_len = len(theme_overview.strip())
    if theme_len < MIN_OVERVIEW_CHARS or theme_len > MAX_OVERVIEW_CHARS:
        raise InputValidationError(
            f"theme_overview must be {MIN_OVERVIEW_CHARS}-{MAX_OVERVIEW_CHARS} chars"
        )

    if approach_type not in APPROACH_TYPES:
        raise InputValidationError("approach_type is invalid")

    if not isinstance(assumptions, list):
        raise InputValidationError("assumptions must be a list")

    assumptions = [a.strip() for a in assumptions if isinstance(a, str) and a.strip()]
    if len(assumptions) < MIN_ASSUMPTIONS or len(assumptions) > MAX_ASSUMPTIONS:
        raise InputValidationError(
            f"assumptions must be {MIN_ASSUMPTIONS}-{MAX_ASSUMPTIONS} items"
        )

    field_value = scope.get("field", "")
    scale_value = scope.get("scale", "")
    time_value = scope.get("time_range", "")

    _require_non_empty(field_value, "scope.field")
    _require_non_empty(scale_value, "scope.scale")
    _require_non_empty(time_value, "scope.time_range")

    if scale_value not in SCALE_TYPES:
        raise InputValidationError("scope.scale is invalid")
    if time_value not in TIME_RANGE_TYPES:
        raise InputValidationError("scope.time_range is invalid")

    include = keywords.get("include", []) or []
    exclude = keywords.get("exclude", []) or []

    if not isinstance(include, list) or not isinstance(exclude, list):
        raise InputValidationError("keywords include/exclude must be lists")

    include = [k.strip() for k in include if isinstance(k, str) and k.strip()]
    exclude = [k.strip() for k in exclude if isinstance(k, str) and k.strip()]

    _limit_list_size(include, "keywords.include", MAX_KEYWORDS)
    _limit_list_size(exclude, "keywords.exclude", MAX_KEYWORDS)

    if concern is not None and not isinstance(concern, str):
        raise InputValidationError("concern must be string or null")

    return ThemeInput(
        theme_overview=theme_overview.strip(),
        goal=goal.strip(),
        why_problem=why_problem.strip(),
        approach_type=approach_type,
        assumptions=assumptions,
        scope=Scope(field=field_value.strip(), scale=scale_value, time_range=time_value),
        keywords=Keywords(include=include, exclude=exclude),
        concern=concern.strip() if isinstance(concern, str) and concern.strip() else None,
    )
