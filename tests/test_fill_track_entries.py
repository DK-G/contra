"""Integration-style tests for fill_track_entries with LLM calls mocked."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.models import Keywords, OutputEntry, Scope, ThemeInput, Work
from src.pipeline import generate
from src.pipeline.generate import GenerationConfig, fill_track_entries


def _theme():
    return ThemeInput(
        theme_overview="遊びの初期体験が離脱を左右する。",
        goal="初回体験の改善仮説を得る",
        why_problem="初見で面白さが伝わらない。",
        approach_type="design",
        assumptions=["初回の理解が継続率に影響する"],
        scope=Scope(field="HCI", scale="small", time_range="recent"),
        keywords=Keywords(include=["onboarding"]),
        concern="論文の条件がゲーム体験へ転用できるか",
    )


def _work(work_id, abstract="Participants improved retention by 12 percent."):
    return Work(
        id=work_id,
        title=f"Paper {work_id}",
        year=2024,
        venue="TestConf",
        doi=None,
        cited_by_count=3,
        abstract=abstract,
    )


def test_fill_track_entries_uses_mocked_llm_for_track_a_and_b():
    calls = []

    def fake_track_a(theme, work, label, level, model):
        calls.append(("A", theme.goal, work.id, label, level, model))
        return (
            "A relationship",
            "A summary",
            "A hypothesis",
            "A caution",
        )

    def fake_track_b(theme, work, label, model, rationale=""):
        calls.append(("B", theme.goal, work.id, label, rationale, model))
        return (
            "B relationship",
            "B summary",
            "B hypothesis",
            "B caution",
        )

    original_track_a = generate._llm_generate_track_a_text
    original_track_b = generate._llm_generate_track_b_text
    generate._llm_generate_track_a_text = fake_track_a
    generate._llm_generate_track_b_text = fake_track_b

    try:
        entries = [
            OutputEntry(
                work=_work("A1"),
                relationship="",
                abstract_summary="",
                caution="",
                track="A",
                label="近接アンカー",
                relationship_level="高",
            ),
            OutputEntry(
                work=_work("B1"),
                relationship="",
                abstract_summary="",
                caution="",
                track="B",
                label="【接続点: 回復ループ】",
                usefulness_hypothesis="paper_finding -> theme variable",
            ),
        ]

        result = fill_track_entries(
            entries,
            GenerationConfig(llm_model="mock-model", llm_max_items=10),
            theme=_theme(),
            mode="llm",
        )
    finally:
        generate._llm_generate_track_a_text = original_track_a
        generate._llm_generate_track_b_text = original_track_b

    assert calls == [
        ("A", "初回体験の改善仮説を得る", "A1", "近接アンカー", "高", "mock-model"),
        (
            "B",
            "初回体験の改善仮説を得る",
            "B1",
            "【接続点: 回復ループ】",
            "paper_finding -> theme variable",
            "mock-model",
        ),
    ]
    assert result[0].relationship == "A relationship"
    assert result[0].abstract_summary == "A summary"
    assert result[0].usefulness_hypothesis == "A hypothesis"
    assert result[0].caution == "A caution"
    assert result[1].relationship == "B relationship"
    assert result[1].abstract_summary == "B summary"
    assert result[1].usefulness_hypothesis == "B hypothesis"
    assert result[1].caution == "B caution"
    assert entries[0].relationship == ""


def test_fill_track_entries_falls_back_when_mocked_llm_returns_none():
    original_track_b = generate._llm_generate_track_b_text
    generate._llm_generate_track_b_text = lambda *args, **kwargs: None

    try:
        entry = OutputEntry(
            work=_work("B2", abstract="Short abstract."),
            relationship="",
            abstract_summary="",
            caution="",
            track="B",
            label="【接続点: 失敗からの回復】",
        )

        result = fill_track_entries(
            [entry],
            GenerationConfig(llm_max_items=10),
            theme=_theme(),
            mode="llm",
        )
    finally:
        generate._llm_generate_track_b_text = original_track_b

    assert result[0].relationship == "【接続点: 失敗からの回復】 という関係構造でテーマに接続する。"
    assert result[0].abstract_summary == "Short abstract."
    assert result[0].usefulness_hypothesis == "この論文の知見をテーマの具体的局面に転用できるか要検討。"
    assert result[0].caution == "注意点: 論文の条件がゲーム体験へ転用できるか"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
