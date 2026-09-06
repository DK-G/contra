"""Tests for ProblemSearchPlan and Problem-Solution Fit scoring."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.core.models import Keywords, Scope, ThemeInput
from src.pipeline.problem_search import (
    build_github_query_specs,
    build_plain_query_specs,
    build_problem_search_plan,
    score_problem_solution_fit,
)


def _theme() -> ThemeInput:
    return ThemeInput(
        theme_overview="We need robust evaluation pipelines for medical imaging domain shift.",
        goal="Find reusable benchmark datasets and implementation examples.",
        why_problem="Hospital and scanner distribution shift reduces reliability.",
        approach_type="application",
        assumptions=["Domain shift is measurable", "Reusable benchmarks exist"],
        scope=Scope(field="medical imaging", scale="multi-site", time_range="recent"),
        keywords=Keywords(include=["medical imaging", "domain shift"], exclude=["gamification"]),
        concern="Benchmarks may not expose hospital-specific failure modes.",
    )


def test_build_problem_search_plan_extracts_problem_and_evidence_facets():
    plan = build_problem_search_plan(_theme())
    assert "medical imaging" in plan.problem_terms
    assert "domain shift" in plan.problem_terms
    assert "evaluation" in plan.capability_terms
    assert "dataset" in plan.artifact_terms
    assert "benchmark" in plan.evidence_terms


def test_build_problem_search_plan_does_not_call_llm_by_default():
    from src.pipeline import problem_search

    original_call = problem_search._call_llm_problem_search_plan

    def fail_if_called(*args, **kwargs):
        raise AssertionError("LLM problem plan should be opt-in")

    problem_search._call_llm_problem_search_plan = fail_if_called
    try:
        plan = build_problem_search_plan(_theme())
    finally:
        problem_search._call_llm_problem_search_plan = original_call

    assert "medical imaging" in plan.problem_terms


def test_build_problem_search_plan_can_merge_llm_facets_when_enabled():
    from src.pipeline import problem_search

    captured = {}
    original_call = problem_search._call_llm_problem_search_plan

    def fake_call(theme, fallback, model):
        captured["model"] = model
        captured["fallback_problem_terms"] = list(fallback.problem_terms)
        return json.dumps(
            {
                "problem_terms": ["scanner bias", "hospital shift"],
                "capability_terms": ["stress testing"],
                "artifact_terms": ["evaluation suite"],
                "evidence_terms": ["leaderboard"],
                "constraint_terms": ["site leakage"],
                "ecosystem_terms": ["pytorch"],
            }
        )

    problem_search._call_llm_problem_search_plan = fake_call
    try:
        plan = build_problem_search_plan(_theme(), use_llm=True, model="mock-model")
    finally:
        problem_search._call_llm_problem_search_plan = original_call

    assert captured["model"] == "mock-model"
    assert "medical imaging" in captured["fallback_problem_terms"]
    assert plan.problem_terms[:2] == ["scanner bias", "hospital shift"]
    assert "medical imaging" in plan.problem_terms
    assert "stress testing" in plan.capability_terms
    assert "pytorch" in plan.ecosystem_terms


def test_build_problem_search_plan_falls_back_when_llm_plan_fails():
    from src.pipeline import problem_search

    original_call = problem_search._call_llm_problem_search_plan

    def fake_call(*args, **kwargs):
        raise RuntimeError("no api key")

    problem_search._call_llm_problem_search_plan = fake_call
    try:
        llm_plan = build_problem_search_plan(_theme(), use_llm=True, model="mock-model")
    finally:
        problem_search._call_llm_problem_search_plan = original_call

    heuristic_plan = build_problem_search_plan(_theme())
    assert llm_plan == heuristic_plan


def test_query_specs_are_source_type_and_intent_units():
    plan = build_problem_search_plan(_theme())
    github_specs = build_github_query_specs(_theme(), plan)
    plain_specs = build_plain_query_specs("hf_model", _theme(), plan)
    assert len(github_specs) >= 3
    assert {spec.intent for spec in github_specs} >= {
        "problem_capability",
        "implementation_evidence",
        "evaluation_evidence",
    }
    assert all(spec.source_type == "github_repository" for spec in github_specs)
    assert all(spec.source_type == "hf_model" for spec in plain_specs)
    assert plain_specs[-1].intent == "problem_only"
    assert "medical imaging domain shift" in plain_specs[0].query


def test_github_query_specs_include_relaxed_problem_fallbacks():
    theme = ThemeInput(
        theme_overview="We need robust BERT text classification under domain shift.",
        goal="Find reusable benchmark implementations.",
        why_problem="Domain shift reduces classifier reliability.",
        approach_type="application",
        assumptions=[],
        scope=Scope(field="nlp", scale="small", time_range="recent"),
        keywords=Keywords(include=["bert", "text classification", "domain shift"], exclude=["course"]),
    )
    specs = build_github_query_specs(theme, build_problem_search_plan(theme))
    by_intent = {spec.intent: spec.query for spec in specs}
    assert "problem_specific_relaxed" in by_intent
    assert "problem_pair_relaxed" in by_intent
    assert "pushed:" not in by_intent["problem_specific_relaxed"]
    assert "bert" in by_intent["problem_specific_relaxed"]
    assert "domain shift" in by_intent["problem_specific_relaxed"]


def test_score_problem_solution_fit_prefers_problem_solving_evidence():
    theme = _theme()
    plan = build_problem_search_plan(theme)
    strong = score_problem_solution_fit(
        theme,
        text=(
            "Medical imaging domain shift benchmark dataset with evaluation pipeline, "
            "baseline metrics, examples, and known limitations for hospital scanner variation."
        ),
        source_type="zenodo_record",
        tags=["medical imaging", "benchmark", "dataset"],
        plan=plan,
    )
    weak = score_problem_solution_fit(
        theme,
        text="A general image gallery demo with no evaluation.",
        source_type="github_repository",
        tags=[],
        plan=plan,
    )
    assert strong.score > weak.score
    assert strong.problem_score > 0
    assert strong.evaluation_score > 0
    assert strong.matched_problem


def test_score_problem_solution_fit_caps_excluded_training_materials():
    theme = _theme()
    theme.keywords.exclude = ["course"]
    plan = build_problem_search_plan(theme)
    score = score_problem_solution_fit(
        theme,
        text=(
            "Medical imaging domain shift course with benchmark dataset, evaluation pipeline, "
            "implementation examples, and baseline metrics."
        ),
        source_type="zenodo_record",
        tags=["medical imaging", "domain shift"],
        plan=plan,
    )
    assert score.problem_score > 0
    assert score.score <= 25


def test_cli_track_a_uses_problem_search_when_enabled():
    from src.cli import main as cli_main

    captured = {}
    overview = (
        "We need to evaluate BERT text classifiers under domain shift across messy, "
        "real-world corpora where label distributions and writing styles vary by site. "
        "The goal of this scenario is to confirm that byrepo's Track A collector uses "
        "problem-oriented search when practical anchors are requested from the CLI."
    )

    def fake_collect_track_a(theme, config):
        captured["git_use_problem_search"] = config.git.use_problem_search
        captured["artifact_use_problem_search"] = config.artifacts.use_problem_search
        captured["git_use_llm_problem_plan"] = config.git.use_llm_problem_plan
        captured["artifact_use_llm_problem_plan"] = config.artifacts.use_llm_problem_plan
        return []

    def fake_collect_track_b(*args, **kwargs):
        return []

    def fake_select_track_b(*args, **kwargs):
        kwargs["diag"]["status"] = "saturated"
        kwargs["diag"]["reason"] = "no_qualified"
        return []

    original_collect_track_a = cli_main.collect_track_a_practical_works
    original_collect_track_b = cli_main.collect_track_b
    original_select_track_b = cli_main.select_track_b
    cli_main.collect_track_a_practical_works = fake_collect_track_a
    cli_main.collect_track_b = fake_collect_track_b
    cli_main.select_track_b = fake_select_track_b
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "theme.json"
            input_path.write_text(
                json.dumps(
                    {
                        "theme_overview": overview,
                        "goal": "Find reusable implementations.",
                        "why_problem": "Distribution shift reduces reliability.",
                        "approach_type": "application",
                        "assumptions": [
                            "Transformer-based classifiers are reusable across corpora.",
                            "Domain shift can be evaluated with practical benchmark code.",
                        ],
                        "scope": {"field": "nlp", "scale": "small", "time_range": "last_10_years"},
                        "keywords": {"include": ["bert", "text classification"], "exclude": []},
                    }
                ),
                encoding="utf-8",
            )
            exit_code = cli_main.main(
                [
                    "--input",
                    str(input_path),
                    "--out",
                    str(root / "out"),
                    "--track-a-count",
                    "1",
                    "--gen-mode",
                    "structured",
                    "--no-history",
                ]
            )
    finally:
        cli_main.collect_track_a_practical_works = original_collect_track_a
        cli_main.collect_track_b = original_collect_track_b
        cli_main.select_track_b = original_select_track_b

    assert exit_code == 0
    assert captured == {
        "git_use_problem_search": True,
        "artifact_use_problem_search": True,
        "git_use_llm_problem_plan": False,
        "artifact_use_llm_problem_plan": False,
    }


def test_cli_track_a_can_opt_into_llm_problem_plan():
    from src.cli import main as cli_main

    captured = {}
    overview = (
        "We need to evaluate BERT text classifiers under domain shift across messy, "
        "real-world corpora where label distributions and writing styles vary by site. "
        "The goal of this scenario is to confirm that byrepo can opt into LLM-assisted "
        "problem planning only when explicitly requested."
    )

    def fake_collect_track_a(theme, config):
        captured["git_use_llm_problem_plan"] = config.git.use_llm_problem_plan
        captured["artifact_use_llm_problem_plan"] = config.artifacts.use_llm_problem_plan
        captured["git_model"] = config.git.llm_problem_plan_model
        captured["artifact_model"] = config.artifacts.llm_problem_plan_model
        return []

    def fake_collect_track_b(*args, **kwargs):
        return []

    def fake_select_track_b(*args, **kwargs):
        kwargs["diag"]["status"] = "saturated"
        kwargs["diag"]["reason"] = "no_qualified"
        return []

    original_collect_track_a = cli_main.collect_track_a_practical_works
    original_collect_track_b = cli_main.collect_track_b
    original_select_track_b = cli_main.select_track_b
    cli_main.collect_track_a_practical_works = fake_collect_track_a
    cli_main.collect_track_b = fake_collect_track_b
    cli_main.select_track_b = fake_select_track_b
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "theme.json"
            input_path.write_text(
                json.dumps(
                    {
                        "theme_overview": overview,
                        "goal": "Find reusable implementations.",
                        "why_problem": "Distribution shift reduces reliability.",
                        "approach_type": "application",
                        "assumptions": [
                            "Transformer-based classifiers are reusable across corpora.",
                            "Domain shift can be evaluated with practical benchmark code.",
                        ],
                        "scope": {"field": "nlp", "scale": "small", "time_range": "last_10_years"},
                        "keywords": {"include": ["bert", "text classification"], "exclude": []},
                    }
                ),
                encoding="utf-8",
            )
            exit_code = cli_main.main(
                [
                    "--input",
                    str(input_path),
                    "--out",
                    str(root / "out"),
                    "--track-a-count",
                    "1",
                    "--track-a-llm-plan",
                    "--llm-model",
                    "mock-model",
                    "--gen-mode",
                    "structured",
                    "--no-history",
                ]
            )
    finally:
        cli_main.collect_track_a_practical_works = original_collect_track_a
        cli_main.collect_track_b = original_collect_track_b
        cli_main.select_track_b = original_select_track_b

    assert exit_code == 0
    assert captured == {
        "git_use_llm_problem_plan": True,
        "artifact_use_llm_problem_plan": True,
        "git_model": "mock-model",
        "artifact_model": "mock-model",
    }


def test_mcp_byrepo_uses_problem_search():
    from src import mcp_server

    captured = {}
    overview = (
        "We need to evaluate BERT text classifiers under domain shift across messy, "
        "real-world corpora where label distributions and writing styles vary by site. "
        "The goal of this scenario is to confirm that byrepo's Track A collector uses "
        "problem-oriented search when practical anchors are requested from MCP."
    )

    def fake_collect_track_a(theme, config):
        captured["git_use_problem_search"] = config.git.use_problem_search
        captured["artifact_use_problem_search"] = config.artifacts.use_problem_search
        captured["git_use_llm_problem_plan"] = config.git.use_llm_problem_plan
        captured["artifact_use_llm_problem_plan"] = config.artifacts.use_llm_problem_plan
        return []

    original_collect_track_a = mcp_server.collect_track_a_practical_works
    mcp_server.collect_track_a_practical_works = fake_collect_track_a
    try:
        result = mcp_server.StdinMcpServer()._execute_byrepo(
            {
                "theme_overview": overview,
                "goal": "Find reusable implementations.",
                "why_problem": "Distribution shift reduces reliability.",
                "assumptions": [
                    "Transformer-based classifiers are reusable across corpora.",
                    "Domain shift can be evaluated with practical benchmark code.",
                ],
                "scope_field": "nlp",
                "keywords_include": ["bert", "text classification"],
                "track_a_count": 1,
            }
        )
    finally:
        mcp_server.collect_track_a_practical_works = original_collect_track_a

    assert result["isError"] is False
    assert captured == {
        "git_use_problem_search": True,
        "artifact_use_problem_search": True,
        "git_use_llm_problem_plan": False,
        "artifact_use_llm_problem_plan": False,
    }


def test_mcp_byrepo_can_opt_into_llm_problem_plan():
    from src import mcp_server

    captured = {}
    overview = (
        "We need to evaluate BERT text classifiers under domain shift across messy, "
        "real-world corpora where label distributions and writing styles vary by site. "
        "The goal of this scenario is to confirm that byrepo MCP can opt into LLM-assisted "
        "problem planning only when explicitly requested."
    )

    def fake_collect_track_a(theme, config):
        captured["git_use_llm_problem_plan"] = config.git.use_llm_problem_plan
        captured["artifact_use_llm_problem_plan"] = config.artifacts.use_llm_problem_plan
        captured["git_model"] = config.git.llm_problem_plan_model
        captured["artifact_model"] = config.artifacts.llm_problem_plan_model
        return []

    original_collect_track_a = mcp_server.collect_track_a_practical_works
    mcp_server.collect_track_a_practical_works = fake_collect_track_a
    try:
        result = mcp_server.StdinMcpServer()._execute_byrepo(
            {
                "theme_overview": overview,
                "goal": "Find reusable implementations.",
                "why_problem": "Distribution shift reduces reliability.",
                "assumptions": [
                    "Transformer-based classifiers are reusable across corpora.",
                    "Domain shift can be evaluated with practical benchmark code.",
                ],
                "scope_field": "nlp",
                "keywords_include": ["bert", "text classification"],
                "track_a_count": 1,
                "use_llm_problem_plan": True,
                "llm_model": "mock-model",
            }
        )
    finally:
        mcp_server.collect_track_a_practical_works = original_collect_track_a

    assert result["isError"] is False
    assert captured == {
        "git_use_llm_problem_plan": True,
        "artifact_use_llm_problem_plan": True,
        "git_model": "mock-model",
        "artifact_model": "mock-model",
    }


def test_unified_practical_collector_shares_one_llm_problem_plan():
    from src.pipeline import practical_collect, problem_search
    from src.pipeline.artifact_collect import ArtifactCollectConfig
    from src.pipeline.git_collect import GitCollectConfig
    from src.pipeline.practical_collect import PracticalCollectConfig

    calls = []
    captured = {}
    original_call = problem_search._call_llm_problem_search_plan
    original_git = practical_collect.collect_track_a_git_works
    original_artifacts = practical_collect.collect_track_a_artifact_works

    def fake_call(theme, fallback, model):
        calls.append(model)
        return json.dumps({"problem_terms": ["scanner bias"]})

    def fake_git(theme, config, *args, problem_plan=None, **kwargs):
        captured["git_plan"] = problem_plan
        return []

    def fake_artifacts(theme, config, *args, problem_plan=None, **kwargs):
        captured["artifact_plan"] = problem_plan
        return []

    problem_search._call_llm_problem_search_plan = fake_call
    practical_collect.collect_track_a_git_works = fake_git
    practical_collect.collect_track_a_artifact_works = fake_artifacts
    try:
        practical_collect.collect_track_a_practical_works(
            _theme(),
            PracticalCollectConfig(
                git=GitCollectConfig(
                    use_problem_search=True,
                    use_llm_problem_plan=True,
                    llm_problem_plan_model="mock-model",
                ),
                artifacts=ArtifactCollectConfig(
                    use_problem_search=True,
                    use_llm_problem_plan=True,
                    llm_problem_plan_model="mock-model",
                ),
            ),
        )
    finally:
        problem_search._call_llm_problem_search_plan = original_call
        practical_collect.collect_track_a_git_works = original_git
        practical_collect.collect_track_a_artifact_works = original_artifacts

    assert calls == ["mock-model"]
    assert captured["git_plan"] is captured["artifact_plan"]
    assert captured["git_plan"].problem_terms[0] == "scanner bias"
