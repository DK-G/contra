"""Track A / Track B classification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from src.core.models import OutputEntry, ThemeInput, Work
from src.openai_client import OpenAIError, extract_output_text, responses_create

_RELATIONSHIP_LEVELS = ["高", "中高", "中", "中低", "低"]
_LEVEL_RANK = {level: i for i, level in enumerate(_RELATIONSHIP_LEVELS)}
_DEFAULT_AXES = ["手法の参照", "前提条件の検証", "反証・対立仮説", "測定手法の転用", "制約条件の対比", "理論的基盤"]


def _score_work(work: Work, include: Sequence[str], exclude: Sequence[str]) -> int:
    text = f"{work.title} {work.abstract or ''}".lower()
    score = sum(1 for t in include if t and t.lower() in text)
    score -= sum(1 for t in exclude if t and t.lower() in text)
    return score


def _llm_call(payload: dict) -> Optional[str]:
    try:
        return extract_output_text(responses_create(payload)).strip()
    except OpenAIError:
        return None


def _parse_array(text: str) -> Optional[list]:
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return None


def _generate_axis_labels(theme: ThemeInput, model: str) -> List[str]:
    text = _llm_call({
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Generate 6-8 concise Japanese relationship axis labels (5-10 chars each) "
                    "for a research theme. Return JSON array of strings only."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"テーマ: {theme.theme_overview[:400]}\n"
                    f"目的: {theme.goal}\n"
                    f"分野: {theme.scope.field}\n"
                    f"キーワード: {', '.join(theme.keywords.include)}\n\n"
                    "このテーマに対して論文が持ちうる関係軸ラベルを6〜8個生成してください。"
                    "JSON配列のみ返してください。"
                ),
            },
        ],
        "temperature": 0.5,
    })
    if text:
        items = _parse_array(text)
        if items:
            labels = [str(x) for x in items if x][:8]
            if labels:
                return labels
    return list(_DEFAULT_AXES)


def _classify_a_labels(
    candidates: List[Work],
    theme: ThemeInput,
    axis_labels: List[str],
    model: str,
) -> Dict[str, Tuple[str, str]]:
    papers_input = [
        {"id": w.id, "title": w.title, "abstract": (w.abstract or "")[:300]}
        for w in candidates
    ]
    text = _llm_call({
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Classify each paper for the research theme. "
                    "Assign relationship_level (高/中高/中/中低/低) and axis_label (from the given list). "
                    "Return JSON array: [{id, relationship_level, axis_label}]"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"テーマ: {theme.theme_overview[:300]}\n"
                    f"目的: {theme.goal}\n"
                    f"関係軸リスト: {json.dumps(axis_labels, ensure_ascii=False)}\n\n"
                    f"論文:\n{json.dumps(papers_input, ensure_ascii=False)}\n\n"
                    "JSON配列のみ返してください。"
                ),
            },
        ],
        "temperature": 0.3,
    })
    if text:
        items = _parse_array(text)
        if items:
            result: Dict[str, Tuple[str, str]] = {}
            for item in items:
                if not isinstance(item, dict):
                    continue
                wid = str(item.get("id", ""))
                level = str(item.get("relationship_level", "中"))
                label = str(item.get("axis_label", ""))
                if wid:
                    valid_level = level if level in _RELATIONSHIP_LEVELS else "中"
                    valid_label = label if label in axis_labels else (axis_labels[0] if axis_labels else "関連")
                    result[wid] = (valid_level, valid_label)
            return result
    return {}


def classify_track_a(
    candidates: List[Work],
    theme: ThemeInput,
    model: str = "gpt-4o-mini",
    count: int = 10,
    use_llm: bool = True,
) -> List[OutputEntry]:
    include = list(theme.keywords.include or [])
    exclude = list(theme.keywords.exclude or [])
    scored = sorted(candidates, key=lambda w: _score_work(w, include, exclude), reverse=True)
    top_k = scored[:max(count * 3, 30)]

    axis_labels = _DEFAULT_AXES[:]
    label_map: Dict[str, Tuple[str, str]] = {}
    if use_llm and top_k:
        axis_labels = _generate_axis_labels(theme, model)
        label_map = _classify_a_labels(top_k, theme, axis_labels, model)

    entries: List[Tuple[int, str, str, Work]] = []
    for work in top_k:
        level, label = label_map.get(work.id, ("中", axis_labels[0] if axis_labels else "関連"))
        entries.append((_LEVEL_RANK.get(level, 2), level, label, work))

    entries.sort(key=lambda x: x[0])
    return [
        OutputEntry(
            work=work,
            relationship="",
            abstract_summary="",
            caution="",
            track="A",
            label=label,
            relationship_level=level,
        )
        for _, level, label, work in entries[:count]
    ]


def _classify_b_connections(
    candidates: List[Work],
    theme: ThemeInput,
    model: str,
    count: int,
) -> List[Tuple[str, str]]:
    papers_input = [
        {"id": w.id, "title": w.title, "abstract": (w.abstract or "")[:400]}
        for w in candidates[:50]
    ]
    text = _llm_call({
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Identify papers from a different domain that have exactly ONE surprising connection "
                    "point to the given research theme. "
                    "For each selected paper provide a concise Japanese connection_label (8-20 chars). "
                    f"Return at most {count} papers as JSON array: [{{id, connection_label}}]"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"研究テーマ: {theme.theme_overview[:300]}\n"
                    f"目的: {theme.goal}\n\n"
                    f"異ドメイン論文:\n{json.dumps(papers_input, ensure_ascii=False)}\n\n"
                    f"「1点だけ接続」する論文を最大{count}本選び、接続点ラベルを付けてください。"
                    "JSON配列のみ返してください。"
                ),
            },
        ],
        "temperature": 0.5,
    })
    if text:
        items = _parse_array(text)
        if items:
            result: List[Tuple[str, str]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                wid = str(item.get("id", ""))
                label = str(item.get("connection_label", "接続点"))
                if wid:
                    result.append((wid, label))
            return result[:count]
    return []


def classify_track_b(
    candidates: List[Work],
    theme: ThemeInput,
    model: str = "gpt-4o-mini",
    count: int = 10,
    use_llm: bool = True,
) -> List[OutputEntry]:
    id_to_work = {w.id: w for w in candidates}
    seen_ids: Set[str] = set()
    result: List[OutputEntry] = []

    if use_llm and candidates:
        for wid, label in _classify_b_connections(candidates, theme, model, count):
            work = id_to_work.get(wid)
            if work and wid not in seen_ids:
                seen_ids.add(wid)
                result.append(OutputEntry(
                    work=work,
                    relationship="",
                    abstract_summary="",
                    caution="",
                    track="B",
                    label=f"【接続点: {label}】",
                    relationship_level="",
                ))

    for work in candidates:
        if len(result) >= count:
            break
        if work.id not in seen_ids:
            seen_ids.add(work.id)
            result.append(OutputEntry(
                work=work,
                relationship="",
                abstract_summary="",
                caution="",
                track="B",
                label="【接続点: 偶発的な接点】",
                relationship_level="",
            ))

    return result[:count]


# Legacy stub preserved for backward compatibility
@dataclass
class ClassifiedWorks:
    related: list
    broad: list
    unrelated: list
    unrelated_chapters: dict


def classify_stub(
    works: Iterable[Work],
    include_keywords: Optional[Sequence[str]] = None,
    exclude_keywords: Optional[Sequence[str]] = None,
) -> ClassifiedWorks:
    include = list(include_keywords or [])
    exclude = list(exclude_keywords or [])
    scored = [(work, _score_work(work, include, exclude)) for work in works]
    scored.sort(key=lambda item: item[1], reverse=True)
    ordered = [w for w, _ in scored]
    total = len(ordered)
    related_count = max(1, round(total * 0.6)) if total else 0
    broad_count = max(0, round(total * 0.3))
    related = ordered[:related_count]
    broad = ordered[related_count: related_count + broad_count]
    unrelated = ordered[related_count + broad_count:]
    chapter_keys = ["反証・対立仮説", "測定・評価の地雷", "手法転用", "制約条件が真逆"]
    unrelated_chapters: Dict[str, List[Work]] = {k: [] for k in chapter_keys}
    for idx, work in enumerate(unrelated):
        key = chapter_keys[idx % len(chapter_keys)]
        unrelated_chapters[key].append(work)
    return ClassifiedWorks(
        related=related,
        broad=broad,
        unrelated=unrelated,
        unrelated_chapters=unrelated_chapters,
    )


__all__ = [
    "ClassifiedWorks",
    "classify_stub",
    "classify_track_a",
    "classify_track_b",
]
