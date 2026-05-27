"""Generation utilities (Phase 1 stub)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.core.models import OutputEntry, ThemeInput, Work
from src.openai_client import OpenAIError, extract_output_text, responses_create


@dataclass
class GenerationConfig:
    relationship_stub: str = "テーマとの関連が示唆される。"
    summary_stub: str = "abstract欠損"
    caution_stub: str = "データ/評価条件に依存する可能性。"
    max_summary_chars: int = 160
    llm_model: str = "gpt-4o-mini"
    llm_max_items: int = 20


def _summarize(abstract: str | None) -> str:
    if not abstract:
        return "abstract欠損"
    text = abstract.strip().replace("\n", " ")
    if len(text) <= 120:
        return text
    return text[:120].rsplit(" ", 1)[0] + "..."


def _relationship(work: Work, keywords: List[str]) -> str:
    text = f"{work.title} {work.abstract or ''}".lower()
    hits = [k for k in keywords if k and k.lower() in text]
    if hits:
        return f"キーワード一致（{', '.join(hits[:3])}）があるため関連性が高い。"
    return "キーワード一致は弱いが関連の可能性がある。"


def _sentence_chunks(text: str) -> List[str]:
    parts = [p.strip() for p in text.replace("\n", " ").split(".") if p.strip()]
    return [p + "." for p in parts]


def _structured_summary(abstract: str | None, cfg: GenerationConfig) -> str:
    if not abstract:
        return "abstract欠損"
    sentences = _sentence_chunks(abstract)
    if not sentences:
        return "abstract欠損"
    if len(sentences) >= 3:
        merged = " ".join(sentences[:3])
    else:
        merged = " ".join(sentences)
    if len(merged) > cfg.max_summary_chars:
        merged = merged[: cfg.max_summary_chars].rsplit(" ", 1)[0] + "..."
    return merged


def _structured_relationship(work: Work, theme: ThemeInput) -> str:
    text = f"{work.title} {work.abstract or ''}".lower()
    focus_terms = list(theme.keywords.include or [])
    if theme.scope.field:
        focus_terms.append(theme.scope.field)
    hits = [k for k in focus_terms if k and k.lower() in text]
    if hits:
        return f"テーマの観点（{', '.join(hits[:2])}）に関連している。"
    return "テーマの観点と周辺領域で関連が見込まれる。"


def _structured_caution(theme: ThemeInput) -> str:
    if theme.concern:
        return f"注意点: {theme.concern}"
    if theme.assumptions:
        return f"注意点: 前提「{theme.assumptions[0]}」が成り立つか要確認。"
    return "注意点: 評価条件の違いで結論が変わる可能性。"


def _llm_generate(theme: ThemeInput, work: Work, model: str) -> Optional[OutputEntry]:
    prompt = {
        "system": (
            "You generate three independent Japanese sentences: relationship, summary, caution. "
            "Do NOT mention 'keyword match' or copy raw abstract phrases. "
            "Relationship should cite a focus/angle (variables/conditions). "
            "Summary should be 2-3 sentences paraphrased. "
            "Caution should be a check point tied to user's assumptions/concerns."
        ),
        "user": (
            "Theme:\n"
            f"- overview: {theme.theme_overview}\n"
            f"- goal: {theme.goal}\n"
            f"- problem: {theme.why_problem}\n"
            f"- assumptions: {', '.join(theme.assumptions)}\n"
            f"- concern: {theme.concern or ''}\n"
            f"- include: {', '.join(theme.keywords.include)}\n"
            "\nPaper:\n"
            f"- title: {work.title}\n"
            f"- abstract: {work.abstract or ''}\n"
            "\nReturn JSON with keys: relationship, summary, caution."
        ),
    }
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]},
        ],
        "temperature": 0.4,
    }
    try:
        response = responses_create(payload)
    except OpenAIError:
        return None
    text = extract_output_text(response)
    if not text:
        return None
    try:
        data = __import__("json").loads(text)
    except Exception:
        return None
    relationship = data.get("relationship") or ""
    summary = data.get("summary") or ""
    caution = data.get("caution") or ""
    if not (relationship and summary and caution):
        return None
    return OutputEntry(
        work=work, relationship=relationship, abstract_summary=summary, caution=caution
    )


def generate_entries(
    works: List[Work],
    config: GenerationConfig | None = None,
    *,
    keywords: List[str] | None = None,
    theme: ThemeInput | None = None,
    mode: str = "simple",
) -> List[OutputEntry]:
    cfg = config or GenerationConfig()
    kw = keywords or []
    entries: List[OutputEntry] = []
    for idx, work in enumerate(works):
        if mode == "llm" and theme and idx < cfg.llm_max_items:
            llm_entry = _llm_generate(theme, work, cfg.llm_model)
            if llm_entry:
                entries.append(llm_entry)
                continue
        if mode == "structured" and theme:
            relationship = _structured_relationship(work, theme)
            summary = _structured_summary(work.abstract, cfg)
            caution = _structured_caution(theme)
        else:
            relationship = _relationship(work, kw) if kw else cfg.relationship_stub
            summary = _summarize(work.abstract)
            caution = cfg.caution_stub
        entries.append(
            OutputEntry(
                work=work,
                relationship=relationship,
                abstract_summary=summary,
                caution=caution,
            )
        )
    return entries


__all__ = ["GenerationConfig", "generate_entries"]
