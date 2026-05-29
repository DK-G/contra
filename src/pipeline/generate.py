"""Generation utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace as dc_replace
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


def _parse_json_object(text: str) -> Optional[dict]:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return None


def _llm_generate_track_a_text(
    theme: ThemeInput,
    work: Work,
    label: str,
    level: str,
    model: str,
) -> Optional[tuple]:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Generate three concise Japanese sentences for a Track A research paper report. "
                    "Return JSON: {relationship, summary, caution}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"テーマ: {theme.theme_overview[:200]}\n"
                    f"関係軸: {label}  関係度: {level}\n"
                    f"論文: {work.title}\n"
                    f"Abstract: {(work.abstract or '')[:300]}\n\n"
                    "relationship: 関係軸と関係度を踏まえた1文（40-80字）\n"
                    "summary: abstractの言い換え2文\n"
                    "caution: テーマの前提に対する注意点1文\n"
                    "JSON形式で返してください。"
                ),
            },
        ],
        "temperature": 0.4,
    }
    try:
        response = responses_create(payload)
        text = extract_output_text(response).strip()
        data = _parse_json_object(text)
        if data:
            r, s, c = data.get("relationship", ""), data.get("summary", ""), data.get("caution", "")
            if r and s and c:
                return r, s, c
    except OpenAIError:
        pass
    return None


def _llm_generate_track_b_text(
    theme: ThemeInput,
    work: Work,
    label: str,
    model: str,
) -> Optional[tuple]:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Generate three concise Japanese sentences for a Track B research paper "
                    "that has exactly one surprising connection to the theme. "
                    "Return JSON: {relationship, summary, caution}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"テーマ: {theme.theme_overview[:200]}\n"
                    f"接続点ラベル: {label}\n"
                    f"論文: {work.title}\n"
                    f"Abstract: {(work.abstract or '')[:300]}\n\n"
                    "relationship: 接続点を起点にした関係説明1文\n"
                    "summary: abstractの言い換え2文\n"
                    "caution: 異なるドメインからの転用リスク1文\n"
                    "JSON形式で返してください。"
                ),
            },
        ],
        "temperature": 0.4,
    }
    try:
        response = responses_create(payload)
        text = extract_output_text(response).strip()
        data = _parse_json_object(text)
        if data:
            r, s, c = data.get("relationship", ""), data.get("summary", ""), data.get("caution", "")
            if r and s and c:
                return r, s, c
    except OpenAIError:
        pass
    return None


def fill_track_entries(
    entries: List[OutputEntry],
    config: GenerationConfig | None = None,
    *,
    theme: ThemeInput | None = None,
    mode: str = "llm",
) -> List[OutputEntry]:
    """Fill relationship/summary/caution for pre-classified Track A/B entries."""
    cfg = config or GenerationConfig()
    result: List[OutputEntry] = []
    for idx, entry in enumerate(entries):
        relationship = entry.relationship
        summary = entry.abstract_summary
        caution = entry.caution

        if mode in ("llm", "plan_b") and theme and idx < cfg.llm_max_items:
            if entry.track == "A":
                llm_result = _llm_generate_track_a_text(
                    theme, entry.work, entry.label, entry.relationship_level, cfg.llm_model
                )
            else:
                llm_result = _llm_generate_track_b_text(
                    theme, entry.work, entry.label, cfg.llm_model
                )
            if llm_result:
                relationship, summary, caution = llm_result

        if not relationship:
            if entry.track == "A":
                level = entry.relationship_level or "中"
                relationship = f"関係軸「{entry.label}」で関係度「{level}」の関連性がある。"
            else:
                relationship = f"{entry.label} という1点でテーマに接続する。"
        if not summary:
            summary = _summarize(entry.work.abstract) if theme is None else _structured_summary(entry.work.abstract, cfg)
        if not caution:
            caution = _structured_caution(theme) if theme else cfg.caution_stub

        result.append(dc_replace(entry, relationship=relationship, abstract_summary=summary, caution=caution))
    return result


__all__ = ["GenerationConfig", "generate_entries", "fill_track_entries"]
