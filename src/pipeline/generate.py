"""Generation utilities."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace as dc_replace
from typing import List, Optional

from src.core.models import OutputEntry, ThemeInput, Work
from src.openai_client import OpenAIError, extract_output_text, responses_create


# Abstract budget for the single-paper generation calls. Findings worth citing (rates,
# effect sizes, the core mechanism) often sit mid/late in an abstract; the old 500-char
# cut starved the hypothesis of exactly that material and forced hollow paraphrase. A
# single-paper call has ample token headroom, so we feed (almost) the whole abstract.
_GEN_ABSTRACT_CHARS = 2000


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
    if work.publication_type and work.publication_type.endswith("_repository"):
        source_kind = f"{work.venue}リポジトリ"
    elif work.publication_type in {"hf_model", "hf_dataset", "hf_space"}:
        source_kind = work.venue
    elif work.publication_type in {"zenodo_record", "datacite_doi"}:
        source_kind = "研究成果物"
    else:
        source_kind = "研究論文"
    source_body = (work.abstract or "")[:_GEN_ABSTRACT_CHARS]
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    f"Generate a 4-part Japanese writeup for a Track A {source_kind}. "
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
                    f"{source_kind}名: {work.title}\n"
                    f"内容: {source_body}\n\n"
                    "以下の制約を守ってJSON形式で返してください。\n"
                    f"summary: この{source_kind}の目的・機能・前提を自分の言葉で2文に要約する。数値や環境条件があれば含めること。\n"
                    f"relationship: 関係軸と関係度を踏まえた1文（40-80字）。この{source_kind}の具体的な手法・対象・制約を1つ以上引用すること。\n"
                    f"hypothesis: この{source_kind}の知見や実装をあなたのテーマにどう持ち込めるか、具体的な転用仮説を1〜2文で。固有の機能や制約に基づくこと。\n"
                    f"caution: テーマの仮説または不安点のうち、この{source_kind}の前提条件と食い違う点を具体的に1文で指摘すること。「初期体験が重要」などの汎用文は禁止。\n"
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
                        "あなたは遠い分野の論文を『自分の研究テーマに転用できる関係構造はあるか』という視点で読む"
                        "専門アナリストである。話題・分野の表層一致ではなく、機能・因果の関係構造を1対1で対応づけ、"
                        "転用可能で検証可能な仮説と、その転用が破断する境界条件を出す。"
                        "出力は JSON {summary, relationship, hypothesis, caution}（4キーのみ、日本語）。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"【接続の構造（事前同定された変数対応）】\n"
                        f"{rationale or '（未指定：Abstractから構造的対応を自分で同定すること）'}\n"
                        f"接続点ラベル: {label}\n\n"
                        f"【論文】\n"
                        f"タイトル: {work.title}\n"
                        f"Abstract: {(work.abstract or '')[:_GEN_ABSTRACT_CHARS]}\n\n"
                        f"【テーマ】\n"
                        f"概要: {theme.theme_overview[:200]}\n"
                        f"目的: {theme.goal}\n"
                        f"不安点: {theme.concern or 'なし'}\n\n"
                        "■ 出力前に必ず内部で実行する手順（思考過程は出力しない）:\n"
                        "S1 抽出: 論文側の中核 object と高次の因果/機構関係（例『AがBを生む』『CがDを抑える』）、"
                        "およびテーマ側の object を取り出す。\n"
                        "S2 写像: 論文側 object ↔ テーマ側 object を〈機能役割のみ〉で1対1対応させる"
                        "（表層・属性・話題での対応は不可）。対応が成立しない要素は caution へ回す。\n"
                        "S3 背骨命名: 両者に保存される因果/機構＝Shared Relational Structure を1つ命名する。\n\n"
                        "■ 上記をもとに、次の4キーをJSONで返す:\n"
                        "summary: Abstractを忠実に日本語へ翻訳し2〜3文に凝縮する。言い換え・解釈・推測を加えず、"
                        "原文の主張と具体的発見（数値・効果量・実験条件があれば保持）をそのまま訳す。原文にない情報を足さない。\n"
                        "relationship: S3 の Shared Relational Structure を1文で述べる。"
                        "『論文側〈X〉とテーマ側〈Y〉が、同じ〈因果/機構の関係〉で対応する』形にすること。\n"
                        "  禁止: 『両方とも〜を扱う/〜が重要』式のカテゴリ・話題一致の言い換え、表層キーワードの一致。\n"
                        "hypothesis: ★中核。S2 の写像を背骨に、論文側の機構を Abstract の具体発見（数値・効果量・手法・方向）で"
                        "名指しして肉付けし、テーマ側の対応局面へ candidate inference として射影する。次の3点を1〜2文に含める:"
                        " [主張＝二値で検証可能な命題] / [因果連鎖＝論文機構→テーマ変数] / [測定可能な変数・指標]。"
                        "【接続の構造】に方向・数値・効果量・指数（例『多いほど遅くなる』『ln(t)/√t』）があれば本文に明示引用する"
                        "（抽象化して落とさない）。数値はAbstractに逐語的に存在するものだけを引用し創作しない；"
                        "数値が無ければ方向性（増減・大小）と方法論的特徴（実験設計・比較条件・対象）で述べる。\n"
                        "  禁止: 『〜の可能性がある/重要な要因となる』等の bloat、論文に無い能力の創作、"
                        "『〜という手法群が役立つ』式のカテゴリ一般化（必ず当該論文固有の機構を名指す）、"
                        f"テーマ不安点（{theme.concern or '上記不安点'}）の単なる言い換え。\n"
                        "caution: 論文側機構の動作前提・制約・失敗モードを1つ抽出し、テーマ環境に照らして"
                        "〈S2 のどの1対1対応が破断するか〉を具体的に1文で述べる。\n"
                        "  禁止: 『対象母集団/文化的背景が違うため注意』『さらなる検証が必要』『データが必要』等の定型・紋切り型。\n"
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
