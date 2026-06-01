"""Generation utilities."""

from __future__ import annotations

import json
import re
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



def _structured_caution(theme: ThemeInput) -> str:
    if theme.concern:
        return f"注意点: {theme.concern}"
    if theme.assumptions:
        return f"注意点: 前提「{theme.assumptions[0]}」が成り立つか要確認。"
    return "注意点: 評価条件の違いで結論が変わる可能性。"



_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _numeric_tokens(text: str) -> set:
    """Numbers in text, with comma decimal separators normalised to dots ('6,0' -> '6.0')."""
    return set(_NUM_RE.findall((text or "").replace(",", ".")))


def _unsupported_numbers(hypothesis: str, abstract: str) -> set:
    """Numbers cited in the hypothesis that do NOT appear in the abstract.

    Guards against R1's specificity push making the model FABRICATE statistics (e.g. an
    invented '85%') to satisfy the 'name the concrete finding' instruction. We only allow
    figures grounded verbatim in the source abstract; anything else is treated as suspect.
    """
    return _numeric_tokens(hypothesis) - _numeric_tokens(abstract)


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
    """Return 4-part (relationship, summary, hypothesis, caution) for a Track A paper."""
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Generate a 4-part Japanese writeup for a Track A research paper. "
                    "Return JSON: {summary, relationship, hypothesis, caution}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"テーマ: {theme.theme_overview[:200]}\n"
                    f"テーマの仮説: {'; '.join(theme.assumptions)}\n"
                    f"テーマの不安点: {theme.concern or 'なし'}\n"
                    f"関係軸: {label}  関係度: {level}\n"
                    f"論文タイトル: {work.title}\n"
                    f"Abstract: {(work.abstract or '')[:500]}\n\n"
                    "以下の制約を守ってJSON形式で返してください。\n"
                    "summary: abstractを自分の言葉で言い換えた2文。数値や実験条件があれば含めること。\n"
                    "relationship: 関係軸と関係度を踏まえた1文（40-80字）。abstractの具体的な手法・対象・条件を1つ以上引用すること。\n"
                    "hypothesis: この論文の知見をあなたのテーマにどう持ち込めるか、具体的な転用仮説を1〜2文で。論文固有の内容に基づくこと。\n"
                    "caution: テーマの仮説または不安点のうち、この論文の前提条件と食い違う点を具体的に1文で指摘すること。「初期体験が重要」などの汎用文は禁止。\n"
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
            s = data.get("summary", "")
            r = data.get("relationship", "")
            h = data.get("hypothesis", "")
            c = data.get("caution", "")
            if r and s and h and c:
                return r, s, h, c
    except OpenAIError:
        pass
    return None


def _llm_generate_track_b_text(
    theme: ThemeInput,
    work: Work,
    label: str,
    model: str,
    rationale: str = "",
) -> Optional[tuple]:
    """Return 4-part (relationship, summary, hypothesis, caution) for a Track B paper.

    The 'hypothesis' (役に立つ可能性の仮説) is the core field: it juxtaposes the user's
    problem frame and the distant paper's solution frame (bisociation) and translates how
    the distant finding might help, standing in for the user's domain sagacity.
    """
    abstract_full = work.abstract or ""

    def _payload(extra: str) -> dict:
        return {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Generate a 4-part Japanese writeup for a Track B paper from a DISTANT domain "
                        "that shares one transferable relational structure with the theme. "
                        "You are given a pre-identified VARIABLE CORRESPONDENCE (接続の構造) between "
                        "the paper and the theme — treat it as the SPINE of the hypothesis, and flesh "
                        "it out with the paper's concrete findings from the abstract. "
                        "Return JSON: {summary, relationship, hypothesis, caution}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"【接続の構造】← この変数対応を仮説の背骨にせよ\n"
                        f"{rationale or '（未指定：Abstractから構造的対応を自分で同定すること）'}\n"
                        f"接続点ラベル: {label}\n\n"
                        f"【論文】\n"
                        f"タイトル: {work.title}\n"
                        f"Abstract: {(work.abstract or '')[:500]}\n\n"
                        f"【テーマ】\n"
                        f"概要: {theme.theme_overview[:200]}\n"
                        f"目的: {theme.goal}\n"
                        f"不安点: {theme.concern or 'なし'}\n\n"
                        "以下の制約を守ってJSON形式で返してください。\n"
                        "summary: Abstractを忠実に日本語へ翻訳し2〜3文に凝縮する。言い換え・解釈・推測を加えず、"
                        "原文の主張と具体的発見（数値・効果量・実験条件があれば保持）をそのまま訳すこと。"
                        "原文にない情報を足さないこと。\n"
                        "relationship: 接続点ラベルが指す『関係構造』が、なぜ表層分野は違えどテーマと一致するのかを1文で。表層キーワードの一致でなく構造の一致を述べること。\n"
                        f"hypothesis: ★中核。【接続の構造】に示された〈論文側の変数〉↔〈テーマ側の変数〉の対応を背骨とし、"
                        "(1) その〈論文側の変数〉を、Abstractの具体的な発見・数値・効果量・実験手法のいずれかで肉付けして名指しし、"
                        "(2) それがテーマの〈対応する局面〉に何を示唆するかを述べること（1〜2文）。"
                        "【接続の構造】に方向や数値・効果量・指数（例: 「多いほど遅くなる」「ln(t)/√t」）が含まれていれば、"
                        "それを hypothesis 本文に明示的に引用すること（抽象化して落とさない）。"
                        "数値はAbstractに逐語的に存在するものだけを引用し、Abstractに無い数値を創作しないこと。"
                        "数値が無ければ方向性（増減・大小）と論文の方法論的特徴（実験設計・比較条件・対象）で述べること。\n"
                        f"テーマの不安点（{theme.concern or '上記不安点'}）の言い換えや、論文の具体的内容に触れない汎用的転用仮説は禁止。\n"
                        "caution: この論文をテーマに転用する際に崩れる前提（対象母集団・実験条件・文化的文脈などの具体的な差異）を1文で指摘すること。「転用に注意」などの汎用文は禁止。\n"
                        + (f"\n{extra}" if extra else "")
                    ),
                },
            ],
            "temperature": 0.4,
        }

    # Numeric grounding (R1/#3): the specificity push can make the model fabricate stats.
    # Verify the hypothesis cites only numbers present in the abstract; if not, regenerate
    # once naming the ungrounded figures, then keep the best-grounded attempt.
    best: Optional[tuple] = None
    best_unsupported = None
    extra = ""
    for _ in range(2):
        try:
            data = _parse_json_object(extract_output_text(responses_create(_payload(extra))).strip())
        except OpenAIError:
            break
        if not data:
            break
        r = data.get("relationship", "")
        s = data.get("summary", "")
        h = data.get("hypothesis", "")
        c = data.get("caution", "")
        if not (r and s and h and c):
            break
        unsupported = _unsupported_numbers(h, abstract_full)
        if best is None or len(unsupported) < best_unsupported:
            best = (r, s, h, c)
            best_unsupported = len(unsupported)
        if not unsupported:
            break
        nums = "、".join(sorted(unsupported))
        extra = (
            f"前回の hypothesis に Abstract へ存在しない数値（{nums}）が含まれていた。"
            "Abstract に逐語的に無い数値は一切書かず、定量が無ければ方向性と方法論的特徴のみで述べ直すこと。"
        )
    return best


def fill_track_entries(
    entries: List[OutputEntry],
    config: GenerationConfig | None = None,
    *,
    theme: ThemeInput | None = None,
    mode: str = "llm",
) -> List[OutputEntry]:
    """Fill 4-part (summary/relationship/hypothesis/caution) for pre-classified Track A/B entries."""
    cfg = config or GenerationConfig()
    result: List[OutputEntry] = []
    for idx, entry in enumerate(entries):
        relationship = entry.relationship
        summary = entry.abstract_summary
        caution = entry.caution
        hypothesis = entry.usefulness_hypothesis

        if mode in ("llm", "plan_b") and theme and idx < cfg.llm_max_items:
            if entry.track == "A":
                llm_result = _llm_generate_track_a_text(
                    theme, entry.work, entry.label, entry.relationship_level, cfg.llm_model
                )
            else:
                llm_result = _llm_generate_track_b_text(
                    theme, entry.work, entry.label, cfg.llm_model, entry.usefulness_hypothesis
                )
            if llm_result:
                relationship, summary, hypothesis, caution = llm_result

        if not relationship:
            if entry.track == "A":
                level = entry.relationship_level or "中"
                relationship = f"関係軸「{entry.label}」で関係度「{level}」の関連性がある。"
            else:
                relationship = f"{entry.label} という関係構造でテーマに接続する。"
        if not summary:
            summary = _summarize(entry.work.abstract) if theme is None else _structured_summary(entry.work.abstract, cfg)
        if not hypothesis:
            hypothesis = "この論文の知見をテーマの具体的局面に転用できるか要検討。"
        if not caution:
            caution = _structured_caution(theme) if theme else cfg.caution_stub

        result.append(dc_replace(
            entry,
            relationship=relationship,
            abstract_summary=summary,
            usefulness_hypothesis=hypothesis,
            caution=caution,
        ))
    return result


__all__ = ["GenerationConfig", "fill_track_entries"]
