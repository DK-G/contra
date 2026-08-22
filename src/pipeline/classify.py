"""Track A / Track B classification."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from src.core.models import OutputEntry, ThemeInput, Work
from src.fulltext.base import effective_abstract
from src.openai_client import OpenAIError, extract_output_text, responses_create
from src.pipeline.concept_distance import ThemeProfile, near_domain_signal

_RELATIONSHIP_LEVELS = ["高", "中高", "中", "中低", "低"]
_LEVEL_RANK = {level: i for i, level in enumerate(_RELATIONSHIP_LEVELS)}
_DEFAULT_AXES = ["手法の参照", "前提条件の検証", "反証・対立仮説", "測定手法の転用", "制約条件の対比", "理論的基盤"]

# A user-declared exclude term is a stronger "demote this" signal than a single matched
# include term, so exclusions are weighted more heavily in the Track A keyword pre-ranking.
# What counts as off-topic is theme-specific and comes from theme.keywords.exclude — never
# from a hardcoded domain list (see spec.md §7 decision 2026-05-30 Step 8: near/far is relative).
_EXCLUDE_WEIGHT = 2


def _score_work(work: Work, include: Sequence[str], exclude: Sequence[str]) -> int:
    text = f"{work.title} {work.abstract or ''}".lower()
    score = sum(1 for t in include if t and t.lower() in text)
    score -= _EXCLUDE_WEIGHT * sum(1 for t in exclude if t and t.lower() in text)
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


def _parse_object(text: str) -> Optional[dict]:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            result = json.loads(text[start:end])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    return None


def _median(xs: Sequence[float]) -> float:
    """Median of a numeric sequence (0.0 if empty). Robust aggregator for vote-K scoring."""
    return float(statistics.median(xs)) if xs else 0.0


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


# Serendipity selection thresholds (see plan.md §6.2, spec.md §7 Step 9 redesign).
# SOLVENT framework: serendipity = purpose_sim * mechanism_dist.
# purpose_sim  : how well the candidate's problem STRUCTURE maps onto the theme purpose.
# mechanism_dist: how FAR the candidate's mechanism is from the theme mechanism.
# Target = purpose_sim high AND mechanism_dist high (same problem, different approach).
_PURPOSE_SIM_MIN = 0.20   # below this = essentially no problem-structure alignment -> reject
# History: 0.25 -> 0.40 (Step 9) to cut abstract-category matches. RELAXED 0.40 -> 0.20
# (R5, 2026-05-31): with the R2 structural-depth judge now doing the quality gate, a hard
# 0.40 floor was redundant DOUBLE-GATING that bisected borderline far candidates on rating
# flipping-noise (bynote: hard floors fail under rater noise; rely on rank/percentile +
# downstream judge). 0.20 only drops near-zero alignment; percentile gate + R2 judge select.
# R3 (2026-05-31): purpose_sim is scored as a DISCRETE anchored level, not a free 0-1 float.
# bynote (rater stability): a discrete ordinal scale + task-anchored criteria is the cheapest,
# most effective de-jitter — it removes within-band sampling noise (the run-to-run 0.7<->0.0
# flips seen on borderline far candidates) AND pins the "same-field -> low" calibration the
# model used to ignore. The three levels map 1:1 onto the prior HIGH/MEDIUM/LOW float bands,
# so the serendipity multiplication and the floors below are unchanged.
_PURPOSE_LEVELS = {"none": 0.10, "partial": 0.45, "strong": 0.70}
_NEAR_DOMAIN_MECH_CAP = 0.5  # mechanism_dist cap for same-L0/L1-domain papers (near_domain_signal)
_SERENDIPITY_GATE = 0.20  # absolute floor for the percentile gate (never pass below this)
_FALLBACK_FLOOR = 0.10    # relaxed floor for single-best fallback when nothing passes gate
# Output-quality floor (spec: 本数は質ゲート超え数, NOT a fixed count). count is a MAX cap;
# we emit only candidates clearing this absolute serendipity bar, so thin themes return a few
# strong units instead of padding to count with weak 0.3-level seeds (2026-05-31 regression).
# 0.35 ~= purpose_sim 0.5 (genuine structural alignment) x mechanism_dist 0.7 (far).
_OUTPUT_FLOOR = 0.35

_SCORE_CHUNK_SIZE = 8    # papers per LLM call. Smaller chunk = more per-paper attention
# (fewer dropped connection_label/serendipity_rationale fields) and keeps each request
# under the API timeout now that abstracts are sent at 500 chars (Step 9 Phase 2).
_SCORE_MAX_CANDIDATES = 60  # cap total candidates scored (cost/latency bound)
_SCORE_PM_MAX_ATTEMPTS = 2  # retry a chunk if gpt-4o-mini drops the relational spine fields

# R2 candidate-level hollow gate (spec §7 Step 9 Phase2; bynote H3: SOLVENT/BioDSA/AR
# all recommend gating hollow candidates BEFORE generation). A separate judge pass scores
# the survivors on Structural Depth (Gentner) and flags has_causal_pm.
# CALIBRATION (2026-05-30, user decision): serendipity has an inherently low base rate and
# the tool runs periodically as a "thought-seed" feed, so we favour RECALL of far candidates.
# Only TRULY hollow (pure shared-category/lexical, structural_depth < gate) are cut; a loose
# causal link (has_causal_pm=False) is recorded/surfaced as a caveat but does NOT reject —
# otherwise far-but-genuine analogies (e.g. quantum subdiffusion) get over-pruned.
_STRUCT_DEPTH_GATE = 0.50   # reject structural_depth (0-1, =judge 0-10/10) BELOW this. Raised
# 0.30->0.50 after a 3-point sweep (0.30/0.50/0.70) over 5 themes: 0.30 let the judge's 3-6
# "lacks-systematicity" category-matches through; 0.70 saturated ALL themes (gpt-4o-mini rarely
# awards >=7); 0.50 keeps the ~2/5 emit rate of 0.30 while cutting 60-75% of candidates as hollow,
# so survivors carry a genuine causal mechanism. Saturated themes are covered by re-runs (history
# dedup), per the quality-first policy. CLI-tunable via --struct-depth-gate.
_JUDGE_MAX_CANDIDATES = 20  # cap survivors sent to the judge (cost bound; survivors are few)


# ---------------------------------------------------------------------------
# Phase 2: Theme schema extraction + analogy-poor detection (Step 9, element E)
# ---------------------------------------------------------------------------

def _extract_theme_schema(theme: ThemeInput, model: str) -> dict:
    """Extract Purpose/Mechanism schema from the theme; detect analogy-poor themes.

    Returns dict: {purpose, mechanism, is_analogy_poor, poor_reason}

    Analogy-poor = understanding-oriented ("why does X happen naturally") or relies on
    implicit physical phenomena — cross-domain analogies require a transferable mechanism.
    System-building and design themes are NOT analogy-poor (spec §7 Step 9, element E).
    On LLM failure, returns a safe fallback (is_analogy_poor=False).
    """
    text = _llm_call({
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Extract the structural Purpose and Mechanism from a research theme.\n"
                    "- purpose: the abstract problem structure (e.g. 'optimize allocation under "
                    "uncertainty', 'improve retention through progressive difficulty calibration').\n"
                    "- mechanism: the intended solution approach / key lever "
                    "(e.g. 'predictive model + safety margins', 'UX difficulty curve + onboarding').\n"
                    "- is_analogy_poor: true ONLY IF the theme is purely UNDERSTANDING-ORIENTED "
                    "('why/how does phenomenon X happen naturally') rather than problem-solving, "
                    "OR if the mechanism is entirely implicit physical phenomena with no "
                    "transferable logic. Design, engineering, and optimization themes are NOT poor.\n"
                    "- poor_reason: brief Japanese explanation if is_analogy_poor; empty otherwise.\n"
                    'Return JSON only: {"purpose": "...", "mechanism": "...", '
                    '"is_analogy_poor": false, "poor_reason": ""}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"テーマ: {theme.theme_overview[:500]}\n"
                    f"目的: {theme.goal}\n"
                    f"分野: {theme.scope.field}\n"
                    f"アプローチ種別: {theme.approach_type}"
                ),
            },
        ],
        "temperature": 0.0,  # schema drives every candidate's score; determinize it (R5)
    })
    fallback = {
        "purpose": theme.goal,
        "mechanism": "",
        "is_analogy_poor": False,
        "poor_reason": "",
    }
    if not text:
        return fallback
    obj = _parse_object(text)
    if not obj:
        return fallback
    return {
        "purpose": str(obj.get("purpose") or theme.goal),
        "mechanism": str(obj.get("mechanism") or ""),
        "is_analogy_poor": bool(obj.get("is_analogy_poor", False)),
        "poor_reason": str(obj.get("poor_reason") or ""),
    }


# ---------------------------------------------------------------------------
# Phase 3: Structure-abduction PM scoring (Step 9, element A)
# ---------------------------------------------------------------------------

def _score_b_chunk_pm(
    papers_input: List[dict],
    theme_schema: dict,
    theme: ThemeInput,
    model: str,
    retry_feedback: str = "",
) -> Optional[list]:
    """Score papers via Purpose-Mechanism structure abduction (SOLVENT framework).

    Each paper's P/M is extracted FIRST, then compared to the theme schema.
    This avoids the LLM surface-keyword bias of one-shot similarity scoring.
    Returns JSON list with purpose_level (mapped to purpose_sim), mechanism_dist,
    connection_label, serendipity_rationale.

    `retry_feedback` (error-aware retry, STROT-style): when a previous attempt dropped the
    relational spine fields, this names the offending ids/fields so the model fixes them,
    rather than blindly re-rolling (more deterministic for gpt-4o-mini).
    """
    text = _llm_call({
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Score research papers for serendipitous cross-domain analogy "
                    "(SOLVENT / structure-abduction method).\n\n"
                    f"THEME PURPOSE: {theme_schema['purpose']}\n"
                    f"THEME MECHANISM: {theme_schema['mechanism']}\n\n"
                    "STEP 1 — Extract for each paper:\n"
                    "  paper_purpose: the SPECIFIC problem structure being solved. Be "
                    "concrete (e.g., 'measure height-induced sensor bias in condition X' "
                    "NOT just 'measure stability').\n"
                    "  paper_mechanism: the SPECIFIC approach used (e.g., 'cross-validate "
                    "3 indices via sensor array' NOT 'measurement study').\n\n"
                    "STEP 2 — Classify purpose structural alignment as a DISCRETE "
                    "LEVEL (purpose_level). Judge the CAUSAL STRUCTURE, NOT the topic "
                    "words. A coinciding topic word (e.g. both mention 'diffusion', "
                    "'spread', 'network', 'risk') is by itself NEITHER alignment NOR a "
                    "disqualifier — only the mapping of causal roles (what drives what) "
                    "counts. Pick EXACTLY ONE label — do NOT output an in-between "
                    "number:\n"
                    "  \"strong\": the paper's SPECIFIC causal mechanism maps onto the "
                    "theme's purpose — same causal chain, constraint type, or failure "
                    "mode — AND the paper is from a DIFFERENT FIELD/discipline than the "
                    "theme. The shared topic word may coincide; what makes it strong is "
                    "the transferable causal correspondence across distant fields.\n"
                    "  \"partial\": a real causal correspondence exists but is "
                    "incomplete, one-directional, or only loosely isomorphic.\n"
                    "  \"none\": NO transferable causal-role correspondence — the papers "
                    "share only a broad category/topic word with no mapped mechanism; "
                    "OR the paper is in the SAME FIELD/discipline as the theme (its "
                    "problem is solved by already-known methods, so no serendipity).\n\n"
                    "STEP 3 — Score mechanism_dist (0.0–1.0):\n"
                    "  How DIFFERENT is the paper's mechanism from the theme's?\n"
                    "  HIGH (0.7–1.0): Completely different domain/field/approach.\n"
                    "  LOW (0.0–0.3): Same field or very similar methodology.\n\n"
                    "STEP 3.5 — Extract paper_finding: the paper's SINGLE most important "
                    "CONCRETE result from the abstract, as a DIRECTION + MAGNITUDE/MECHANISM "
                    "(not a topic). Pull the actual numbers, effect sizes, scaling exponents, "
                    "or directional findings stated in the abstract (what increases/decreases "
                    "with what, and by how much). If the abstract has no numbers, name the "
                    "specific experimental/structural result (which variable drives which, and "
                    "in which direction).\n"
                    "  BAD  (topic, no finding): 「情報拡散を研究した」「対称性を扱う」\n"
                    "  GOOD (direction+magnitude): 「重なり合う保存則が多いほど電荷拡散が遅く"
                    "なる（異常サブ拡散; 2次元で ln(t)/√t, 3次元で 1/t^{3/4} に減衰・非ガウス的）」\n\n"
                    "STEP 4 — Build the bridge FROM paper_finding (STEP 3.5) and the "
                    "paper_purpose/paper_mechanism (STEP 1). Identify the ONE specific variable "
                    "on the paper side — it MUST carry the finding's direction/magnitude — and "
                    "the ONE specific variable on the theme side that map onto each other. Do "
                    "NOT fall back to generic category words here.\n"
                    "  The mapped paper-side variable MUST be a RELATION/MECHANISM that the "
                    "finding quantifies (e.g. 「保存則の数→拡散速度」: more X drives slower Y), "
                    "NOT a standalone object attribute (e.g. 「対称性をもつ」). Map by FUNCTION "
                    "(what drives what), not by surface attribute — otherwise the analogy is a "
                    "literal-similarity / mere-appearance match, not a structural one.\n\n"
                    "connection_label: 8–24 char Japanese chip for at-a-glance scanning. "
                    "It MUST express a RELATIONSHIP or PROCESS (the mechanism that "
                    "transfers), by either (i) containing a causal verb (律速する/分岐"
                    "する/駆動する/選択する/抑制する/予兆する) or (ii) using a 「AによるB」 "
                    "/ 「AがBを決める」 structure. Derive it by compressing your "
                    "serendipity_rationale into a chip.\n"
                    "  REJECTED (bare topic/field noun): 「情報の拡散」「交通予測」"
                    "「細胞間シグナル解析」「リスク評価」\n"
                    "  REQUIRED (relationship/process)  : 「対称性保存則が拡散速度を律速"
                    "する」「難易度漸増による長期定着」「臨界遷移の早期警告が分岐を予兆」\n"
                    "serendipity_rationale: ONE Japanese sentence stating the VARIABLE "
                    "CORRESPONDENCE that EMBEDS paper_finding's concrete direction/magnitude, "
                    "in this form:\n"
                    "  「論文の〈paper_finding を含む具体変数：方向＋数値/効果〉は、テーマの"
                    "〈theme側の局面〉における〈theme側の対応変数〉に相当する」\n"
                    "  - The 〈paper側の具体変数〉 MUST carry the STEP 3.5 finding (direction "
                    "＋ number/effect), NOT a generic restatement or a bare topic noun.\n"
                    "  - The 〈theme側の対応変数〉 MUST be a SPECIFIC theme-side lever/variable "
                    "taken from THIS theme's purpose/mechanism (e.g. a named driver the user can "
                    "act on), NOT a generic category noun. If you can only bind it to a vague "
                    "noun, the analogy is too shallow — prefer purpose_level=partial/none.\n"
                    "  - FORBIDDEN: 「両者とも○○に関わる」「○○という点で共通している」; abstracting "
                    "the finding away into a category noun (e.g. 「情報の伝播」); and stating only "
                    "the PAPER's own internal mechanism without binding it to a concrete theme-side "
                    "variable (e.g. 「社会的影響が伝播を駆動する」 with the theme side left generic — "
                    "the rationale must cross-map, not describe the paper alone).\n\n"
                    "GOOD example (paper_finding→rationale): finding=「保存則が多いほど"
                    "拡散が遅い（異常サブ拡散 ln(t)/√t〜1/t^{3/4}）」/ rationale=「論文の〈保存則が"
                    "多いほど拡散が遅い異常サブ拡散（ln(t)/√t〜1/t^{3/4}）〉は、テーマの〈拡散の分岐〉に"
                    "おける〈発信者の制約が拡散指数αに相当する律速要因〉に相当する」\n\n"
                    "EVERY paper in the array MUST have ALL fields populated. paper_finding, "
                    "connection_label and serendipity_rationale are REQUIRED and must "
                    "NEVER be empty or omitted, even for low-scoring papers.\n\n"
                    "purpose_pct: an INTEGER 0-100 refining alignment WITHIN the chosen "
                    "purpose_level band (e.g. two 'strong' papers may be 62 vs 88). This is "
                    "a tie-breaker only — the level still decides the gates. Use the full "
                    "range; do NOT cluster on round values.\n"
                    "mechanism_dist: give TWO decimals from the full 0-1 range (e.g. 0.73, "
                    "0.86) — do NOT default to 0.80.\n\n"
                    "Return JSON array:\n"
                    '[{"id":"...","paper_purpose":"...","paper_mechanism":"...",'
                    '"paper_finding":"...","purpose_level":"none|partial|strong",'
                    '"purpose_pct":0,"mechanism_dist":0.0,'
                    '"connection_label":"...","serendipity_rationale":"..."}]'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"テーマの分野（これと同じ分野の論文は purpose_level が none になりやすい）: "
                    f"{theme.scope.field}\n\n"
                    f"論文:\n{json.dumps(papers_input, ensure_ascii=False)}\n\n"
                    "各論文のPurpose/Mechanismを先に抽出し、テーマとの類推スコアをJSON配列のみで返してください。"
                    + (f"\n\n{retry_feedback}" if retry_feedback else "")
                ),
            },
        ],
        "temperature": 0.0,  # rating task: minimise sampling jitter (R5, 2026-05-31)
    })
    return _parse_array(text) if text else None


def _score_one_chunk_complete(
    papers_input: List[dict],
    chunk_ids: List[str],
    theme_schema: dict,
    theme: ThemeInput,
    model: str,
) -> Dict[str, Tuple[dict, bool]]:
    """Score one chunk once, with completeness-retry. Returns wid -> (row, is_complete).

    gpt-4o-mini stochastically drops the later relational fields (connection_label/
    serendipity_rationale/paper_finding) under the longer P/M+finding instruction.
    Error-aware retry (STROT-style): name the offending ids/fields and ask the model to
    fix them, keeping per paper the most complete row. Beats a blind re-roll for mini.
    """
    chunk_best: Dict[str, Tuple[dict, bool]] = {}
    feedback = ""
    for _ in range(_SCORE_PM_MAX_ATTEMPTS):
        items = _score_b_chunk_pm(papers_input, theme_schema, theme, model, retry_feedback=feedback)
        for wid, row, complete in _parse_pm_items(items):
            if wid not in chunk_best or (complete and not chunk_best[wid][1]):
                chunk_best[wid] = (row, complete)
        missing = [wid for wid in chunk_ids if wid not in chunk_best or not chunk_best[wid][1]]
        if not missing:
            break
        feedback = (
            "PREVIOUS ATTEMPT WAS INCOMPLETE. These paper ids had empty/omitted "
            "connection_label, serendipity_rationale, or paper_finding: "
            f"{json.dumps(missing, ensure_ascii=False)}. Re-output the FULL JSON array for "
            "ALL papers, and for these ids ensure paper_finding (concrete direction＋"
            "magnitude), connection_label, and serendipity_rationale (with the finding "
            "embedded in the variable correspondence) are ALL non-empty."
        )
    return chunk_best


def _score_b_candidates_pm(
    candidates: List[Work],
    theme_schema: dict,
    theme: ThemeInput,
    model: str,
    vote_k: int = 1,
) -> Dict[str, dict]:
    """Score Track B candidates via PM structure abduction, in chunks.

    Returns dict: work_id -> {purpose_sim, mechanism_dist, connection_label,
                               serendipity_rationale, paper_purpose, paper_mechanism}

    vote_k > 1 enables self-consistency (R5): each chunk is scored vote_k times and the
    numeric fields (purpose_sim/mechanism_dist) are reduced by MEDIAN, which damps the
    rating jitter that flips borderline candidates across the output floor. Text fields are
    taken from the most complete vote. vote_k=1 (default) keeps single-pass cost/behavior.
    """
    scores: Dict[str, dict] = {}
    pool = candidates[:_SCORE_MAX_CANDIDATES]
    k = max(1, vote_k)
    for start in range(0, len(pool), _SCORE_CHUNK_SIZE):
        chunk = pool[start:start + _SCORE_CHUNK_SIZE]
        # effective_abstract == (w.abstract or "")[:500] unless a full-text excerpt was
        # attached (--fulltext); then the cleaned excerpt is appended so the P/M mechanism
        # judgment has more material. Score formula and thresholds are unchanged (input only).
        papers_input = [
            {"id": w.id, "title": w.title, "abstract": effective_abstract(w)}
            for w in chunk
        ]
        chunk_ids = [w.id for w in chunk]
        if k == 1:
            chunk_best = _score_one_chunk_complete(papers_input, chunk_ids, theme_schema, theme, model)
            for wid, (row, _complete) in chunk_best.items():
                scores[wid] = row
            continue
        # Self-consistency: aggregate k independent scorings by median of the numeric fields.
        votes: Dict[str, dict] = defaultdict(
            lambda: {"purpose_sim": [], "mechanism_dist": [], "purpose_pct": [], "rows": []}
        )
        for _ in range(k):
            chunk_best = _score_one_chunk_complete(papers_input, chunk_ids, theme_schema, theme, model)
            for wid, (row, complete) in chunk_best.items():
                votes[wid]["purpose_sim"].append(row["purpose_sim"])
                votes[wid]["mechanism_dist"].append(row["mechanism_dist"])
                votes[wid]["purpose_pct"].append(row.get("purpose_pct", 0))
                votes[wid]["rows"].append((row, complete))
        for wid, v in votes.items():
            rep = dict(max(v["rows"], key=lambda rc: rc[1])[0])  # prefer a complete row for text
            rep["purpose_sim"] = _median(v["purpose_sim"])
            rep["mechanism_dist"] = _median(v["mechanism_dist"])
            rep["purpose_pct"] = _median(v["purpose_pct"])
            rep["fine_rank"] = round((rep["purpose_pct"] / 100.0) * rep["mechanism_dist"], 4)
            scores[wid] = rep
    return scores


def _parse_pm_items(items: Optional[list]) -> List[Tuple[str, dict, bool]]:
    """Parse a _score_b_chunk_pm response into (work_id, score_row, is_complete) tuples.

    is_complete = the relational spine survived (connection_label + serendipity_rationale
    both non-empty). Incomplete rows are kept as a fallback but lose to complete ones.
    """
    out: List[Tuple[str, dict, bool]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        wid = str(item.get("id") or "")
        if not wid:
            continue
        level = item.get("purpose_level")
        if isinstance(level, str) and level.strip().lower() in _PURPOSE_LEVELS:
            purpose_sim = _PURPOSE_LEVELS[level.strip().lower()]
        else:
            # backward-compat: a raw float purpose_sim is still accepted (older payloads / fallback)
            try:
                purpose_sim = float(item.get("purpose_sim", 0.0))
            except (TypeError, ValueError):
                purpose_sim = 0.0
        try:
            mechanism_dist = float(item.get("mechanism_dist", 0.0))
        except (TypeError, ValueError):
            continue
        label = str(item.get("connection_label") or "")
        rationale = str(item.get("serendipity_rationale") or "")
        complete = bool(label and rationale)
        # F-10 residue (2026-08-22 ruling, package B): a fine within-band percentage breaks
        # the ties the 3-level anchors create (observed: every hit at 0.80 x 0.70 = 0.56).
        # The anchors still drive every GATE (R3's anti-jitter decision stands); purpose_pct
        # only orders candidates the anchors cannot separate.
        try:
            purpose_pct = max(0, min(100, int(item.get("purpose_pct", 0) or 0)))
        except (TypeError, ValueError):
            purpose_pct = 0
        out.append((wid, {
            "purpose_sim": max(0.0, min(1.0, purpose_sim)),
            "mechanism_dist": max(0.0, min(1.0, mechanism_dist)),
            "purpose_pct": purpose_pct,
            "fine_rank": round((purpose_pct / 100.0) * max(0.0, min(1.0, mechanism_dist)), 4),
            "connection_label": label or "構造的接続",
            "serendipity_rationale": rationale,
            "paper_purpose": str(item.get("paper_purpose") or ""),
            "paper_mechanism": str(item.get("paper_mechanism") or ""),
            "paper_finding": str(item.get("paper_finding") or ""),
        }, complete))
    return out


# ---------------------------------------------------------------------------
# Phase 2 (R2): candidate-level hollow gate — Structural Depth judge
# ---------------------------------------------------------------------------

def _judge_one_pass(judged_input: List[dict], theme_schema: dict, model: str) -> Dict[str, dict]:
    """One judge call. Returns wid -> {structural_depth, applicability, has_causal_pm,
    judge_reason} normalized to 0-1. Empty on LLM failure (fail-open)."""
    text = _llm_call({
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a STRICT judge of cross-domain analogy quality "
                    "(Gentner structure-mapping + SOLVENT). For each candidate you get the "
                    "theme's purpose/mechanism and the candidate's extracted paper_purpose / "
                    "paper_mechanism / paper_finding and a proposed_mapping (variable "
                    "correspondence). Score each:\n\n"
                    f"THEME PURPOSE: {theme_schema['purpose']}\n"
                    f"THEME MECHANISM: {theme_schema['mechanism']}\n\n"
                    "- structural_depth (0–10): how well-defined and meaningful is the object-"
                    "to-object mapping? Calibrated bands: 0-2 = vague/superficial/HOLLOW, rests "
                    "on a shared CATEGORY or attribute ('both involve diffusion/risk/networks') "
                    "with little explanatory power. 3-6 = individual objects map plausibly but it "
                    "LACKS SYSTEMATICITY — no connected higher-order causal relation is carried "
                    "over (a category match dressed up). 7-9 = the causal MECHANISMS of both "
                    "domains are aligned. 10 = deep one-to-one parallel connectivity of FUNCTIONAL "
                    "ROLES with a transferable mechanism.\n"
                    "- applicability (0–10): how concretely could this analogy inform the theme? "
                    "0 = misleading/unhelpful; 10 = directly enables a concrete, testable "
                    "hypothesis for the theme.\n"
                    "- has_causal_pm (true/false): does the candidate have an EXPLICIT causal "
                    "Purpose→Mechanism link with a TRANSFERABLE mechanism? false if the paper is "
                    "purely observational / understanding-oriented (reports WHAT happens with no "
                    "transferable HOW/WHY), or the mapping rests on a shared category/attribute "
                    "rather than a relation.\n"
                    "- judge_reason: ONE short Japanese sentence.\n\n"
                    "Be harsh: most cross-domain pairings are hollow. Reserve high "
                    "structural_depth for genuine relational isomorphism.\n"
                    'Return JSON array only: [{"id":"...","structural_depth":0,'
                    '"applicability":0,"has_causal_pm":false,"judge_reason":"..."}]'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"候補:\n{json.dumps(judged_input, ensure_ascii=False)}\n\n"
                    "各候補を厳格に採点し、JSON配列のみで返してください。"
                ),
            },
        ],
        "temperature": 0.0,  # rating task: minimise sampling jitter (R5, 2026-05-31)
    })
    items = _parse_array(text) if text else None
    result: Dict[str, dict] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        wid = str(item.get("id") or "")
        if not wid:
            continue
        try:
            sd = float(item.get("structural_depth", 0.0))
            ap = float(item.get("applicability", 0.0))
        except (TypeError, ValueError):
            continue
        result[wid] = {
            "structural_depth": max(0.0, min(1.0, sd / 10.0)),
            "applicability": max(0.0, min(1.0, ap / 10.0)),
            "has_causal_pm": bool(item.get("has_causal_pm", True)),
            "judge_reason": str(item.get("judge_reason") or ""),
        }
    return result


def _judge_b_candidates(
    survivors: List[Tuple[Work, dict]],
    theme_schema: dict,
    theme: ThemeInput,
    model: str,
    vote_k: int = 1,
) -> Dict[str, dict]:
    """Judge each surviving candidate for analogy QUALITY (a separate pass, not folded into
    scoring — bynote H2: separate calls beat overloading one prompt for small models).

    Scores Structural Depth (Gentner: are the object mappings deep & one-to-one, or a hollow
    shared-category match?) and Applicability, and flags whether an explicit causal Purpose→
    Mechanism link exists (false = observational/understanding-oriented or surface-attribute
    mapping → hollow). Returns wid -> {structural_depth, applicability, has_causal_pm,
    judge_reason} with scores normalized to 0-1. Empty dict on LLM failure (fail-open).

    vote_k > 1 enables self-consistency (R5): the judge is run vote_k times and structural_depth
    /applicability are reduced by MEDIAN, has_causal_pm by MAJORITY (ties keep True = fail-open).
    This stabilizes the hollow gate's hard threshold so borderline candidates stop flipping in/
    out across runs. vote_k=1 (default) keeps single-call cost/behavior.
    """
    if not survivors:
        return {}
    judged_input = [
        {
            "id": w.id,
            "paper_purpose": s.get("paper_purpose", ""),
            "paper_mechanism": s.get("paper_mechanism", ""),
            "paper_finding": s.get("paper_finding", ""),
            "proposed_mapping": s.get("serendipity_rationale", ""),
        }
        for w, s in survivors[:_JUDGE_MAX_CANDIDATES]
    ]
    k = max(1, vote_k)
    if k == 1:
        return _judge_one_pass(judged_input, theme_schema, model)

    agg: Dict[str, dict] = defaultdict(lambda: {"sd": [], "ap": [], "causal": [], "reason": []})
    for _ in range(k):
        for wid, r in _judge_one_pass(judged_input, theme_schema, model).items():
            agg[wid]["sd"].append(r["structural_depth"])
            agg[wid]["ap"].append(r["applicability"])
            agg[wid]["causal"].append(bool(r["has_causal_pm"]))
            if r["judge_reason"]:
                agg[wid]["reason"].append(r["judge_reason"])
    result: Dict[str, dict] = {}
    for wid, a in agg.items():
        n = len(a["causal"])
        result[wid] = {
            "structural_depth": _median(a["sd"]),
            "applicability": _median(a["ap"]),
            # majority vote; tie keeps True (fail-open — has_causal_pm=False only adds a caveat)
            "has_causal_pm": sum(a["causal"]) * 2 >= n,
            "judge_reason": a["reason"][0] if a["reason"] else "",
        }
    return result


# ---------------------------------------------------------------------------
# Phase 4a: Percentile gate helper (Step 9, element D)
# ---------------------------------------------------------------------------

def _percentile_gate(scores: List[float], top_pct: float = 0.30, floor: float = 0.20) -> float:
    """Compute the quality gate as the top-top_pct percentile, never below floor.

    Example: 10 scores sorted desc [0.50,0.45,0.40,...]; top 30% = top 3; gate = 0.40.
    Combined with floor: max(0.40, 0.20) = 0.40.
    """
    if not scores:
        return floor
    sorted_desc = sorted(scores, reverse=True)
    k = max(1, int(len(sorted_desc) * top_pct))
    return max(sorted_desc[k - 1], floor)


# ---------------------------------------------------------------------------
# Phase 4b: MMR diversity re-ranking (Step 9, element D)
# ---------------------------------------------------------------------------

def _concept_jaccard(w1: Work, w2: Work) -> float:
    """Jaccard similarity of level-1+ concept names between two papers."""
    n1 = {t.name for t in w1.concept_tags if t.level >= 1 and t.name}
    n2 = {t.name for t in w2.concept_tags if t.level >= 1 and t.name}
    if not n1 or not n2:
        return 0.0
    return len(n1 & n2) / len(n1 | n2)


def _maxmin_diversify(works: List[Work], k: int) -> List[Work]:
    """Farthest-point (MAX-MIN) selection over concept space: pick k works that are mutually
    most distant, where distance = 1 - concept Jaccard (level-1+ concept names).

    The merged Track B pool (LLM keyword queries + citation 2-hop) can exceed the scoring
    cap; truncating it by list order would drop the far citation candidates (appended last)
    and spend the P/M budget on near-duplicate clusters. MAX-MIN instead spreads the budget
    across distinct concept regions: it seeds with works[0] (stable input order -> deterministic,
    R5) and greedily adds the work whose MINIMUM distance to the already-selected set is the
    LARGEST. See collection research memo §具体設計 step 3.
    """
    if k <= 0:
        return []
    if len(works) <= k:
        return list(works)
    selected: List[Work] = [works[0]]
    remaining: List[Work] = list(works[1:])
    # Track each remaining work's HIGHEST similarity to any selected work (= its lowest distance).
    max_sim: Dict[str, float] = {w.id: _concept_jaccard(w, selected[0]) for w in remaining}
    while len(selected) < k and remaining:
        # Pick the work with the lowest max-similarity (largest min-distance) to the selected set.
        best = min(remaining, key=lambda w: max_sim[w.id])
        selected.append(best)
        remaining.remove(best)
        for w in remaining:
            sim = _concept_jaccard(w, best)
            if sim > max_sim[w.id]:
                max_sim[w.id] = sim
    return selected


def _mmr_rerank(
    scored: List[Tuple[float, str, dict]],
    id_to_work: Dict[str, Work],
    lam: float = 0.7,
    count: int = 10,
) -> List[Tuple[float, str, dict]]:
    """MMR diversity re-ranking using concept Jaccard as the redundancy signal.

    lam=0.7 slightly favours serendipity score over diversity.
    At each step picks the candidate that maximises:
      lam * serendipity  -  (1 - lam) * max_sim_to_selected
    """
    if len(scored) <= 1:
        return scored[:count]

    remaining = list(scored)
    selected: List[Tuple[float, str, dict]] = []

    while remaining and len(selected) < count:
        if not selected:
            best = max(remaining, key=lambda x: x[0])
        else:
            def _mmr_val(cand: Tuple[float, str, dict]) -> float:
                ser = cand[0]
                w = id_to_work.get(cand[1])
                if w is None:
                    return -1.0
                max_sim = max(
                    _concept_jaccard(w, id_to_work[s[1]])
                    for s in selected
                    if s[1] in id_to_work
                ) if selected else 0.0
                return lam * ser - (1.0 - lam) * max_sim
            best = max(remaining, key=_mmr_val)
        selected.append(best)
        remaining.remove(best)

    return selected




def _update_diag(diag: Optional[dict], **kw) -> None:
    """M3 saturation telemetry hook (no-op when diag is None)."""
    if diag is not None:
        diag.update(kw)


def _record_rejections(diag, before_ids, after_ids, *, floor, threshold, value_of) -> None:
    """F-09: append one (id, floor, value, threshold) row per candidate dropped at a stage.

    The post-gate used to report only pass COUNTS ("採点 4 / 通過 1") — the caller could
    reproduce the scoring but never the rejections, so its own calibration loop was blind
    (field_observations_seihai.md F-09, the same observability gap as bybridge's F-02).
    No-op when diag is None. `value_of` maps a work id to the measured value at this floor.
    """
    if diag is None:
        return
    rejections = diag.setdefault("rejections", [])
    for wid in before_ids:
        if wid not in after_ids:
            value = value_of(wid)
            rejections.append({
                "id": wid,
                "floor": floor,
                "value": round(value, 3) if isinstance(value, (int, float)) else value,
                "threshold": round(threshold, 3) if isinstance(threshold, (int, float)) else threshold,
            })


# --- Deterministic post-gates (no LLM) -------------------------------------
# Stage (b) of the MCP-client delegation design
# (docs/research/mcp_subscription_delegation.md): the hard numeric floors are
# factored out of select_track_b so the SAME code applies them whether the
# purpose_sim / mechanism_dist / structural_depth came from contra's own LLM
# pass or from a delegated agent. These functions never call the LLM.

def _serendipity_scored(
    scores: Dict[str, dict],
    id_to_work: Dict[str, Work],
    theme_profile: Optional[ThemeProfile],
) -> Tuple[List[Tuple[float, str, dict]], int]:
    """Anomaly filter + near-domain mechanism cap + serendipity = purpose_sim * mech_dist."""
    all_scored: List[Tuple[float, str, dict]] = []
    anomaly_count = 0
    for wid, s in scores.items():
        work = id_to_work.get(wid)
        if work is None:
            continue
        purpose_sim = s["purpose_sim"]
        mechanism_dist = s["mechanism_dist"]
        # Anomaly filter: no genuine purpose-structure alignment.
        if purpose_sim < _PURPOSE_SIM_MIN:
            anomaly_count += 1
            continue
        # Near-domain cap: same L0/L1 domain -> cap mechanism_dist (anti false-serendipity).
        if theme_profile is not None and near_domain_signal(work, theme_profile):
            mechanism_dist = min(mechanism_dist, _NEAR_DOMAIN_MECH_CAP)
        all_scored.append((purpose_sim * mechanism_dist, wid, s))
    return all_scored, anomaly_count


def _apply_causal_cap(
    all_scored: List[Tuple[float, str, dict]],
) -> List[Tuple[float, str, dict]]:
    """Reflect the judge's own verdict in the grade (F-10, field_observations_seihai.md).

    When the hollow judge says has_causal_pm=False the label already reads "構造対応ゆるめ"
    — yet the same candidate could carry purpose_sim 0.70 = the "strong" level, so the prose
    caveat and the numeric grade contradicted each other head-on (observed 2026-08-21: four
    candidates across two themes, all 0.56 = 0.80 x 0.70 with the loose label). A candidate
    the judge itself calls loose is capped at the "partial" level; the serendipity product is
    rescaled by the same factor so ranking stays consistent with the displayed scores. The
    uncapped value is kept in `purpose_sim_uncapped` for diagnostics.
    """
    cap = _PURPOSE_LEVELS["partial"]
    out: List[Tuple[float, str, dict]] = []
    for ser, wid, s in all_scored:
        purpose = s.get("purpose_sim", 0.0)
        if s.get("has_causal_pm") is False and purpose > cap:
            s["purpose_sim_uncapped"] = purpose
            s["purpose_sim"] = cap
            if purpose:
                ser = ser * (cap / purpose)
                # keep the fine tie-breaker consistent with the demoted grade
                if s.get("fine_rank"):
                    s["fine_rank"] = round(s["fine_rank"] * (cap / purpose), 4)
        out.append((ser, wid, s))
    return out


def _hollow_filter(
    all_scored: List[Tuple[float, str, dict]],
    struct_depth_gate: float,
) -> Tuple[List[Tuple[float, str, dict]], int, int]:
    """Hollow gate: reject structural_depth below the gate. Fail-open when unjudged.

    A loose causal link (has_causal_pm is False) is surfaced as a caveat, not rejected.
    """
    kept: List[Tuple[float, str, dict]] = []
    hollow_count = 0
    loose_causal_count = 0
    for ser, wid, s in all_scored:
        depth = s.get("structural_depth")
        if depth is not None and depth < struct_depth_gate:
            hollow_count += 1
            continue
        if s.get("has_causal_pm") is False:
            loose_causal_count += 1
        kept.append((ser, wid, s))
    return kept, hollow_count, loose_causal_count


def _quality_gate_and_build(
    all_scored: List[Tuple[float, str, dict]],
    id_to_work: Dict[str, Work],
    theme_profile: Optional[ThemeProfile],
    *,
    count: int,
    gate: float,
    output_floor: float,
    emit_fallback: bool,
    scored_n: int,
    anomaly_count: int,
    hollow_count: int,
    diag: Optional[dict] = None,
) -> List[OutputEntry]:
    """Percentile gate + output floor + fallback/M3 + MMR diversity + build entries."""
    # Step 4: Percentile gate (top-30% or absolute floor, whichever is higher)
    ser_vals = [x[0] for x in all_scored]
    effective_gate = _percentile_gate(ser_vals, top_pct=0.30, floor=gate)
    passed = [(ser, wid, s) for ser, wid, s in all_scored if ser >= effective_gate]
    qualified = [(ser, wid, s) for ser, wid, s in passed if ser >= output_floor]
    # F-09: per-candidate rejection rows for the two serendipity floors.
    ser_by_id = {wid: ser for ser, wid, _s in all_scored}
    _record_rejections(
        diag, ser_by_id.keys(), {wid for _s, wid, _d in passed},
        floor="percentile_gate(serendipity)", threshold=effective_gate,
        value_of=ser_by_id.get,
    )
    _record_rejections(
        diag, {wid for _s, wid, _d in passed}, {wid for _s, wid, _d in qualified},
        floor="output_floor(serendipity)", threshold=output_floor,
        value_of=ser_by_id.get,
    )
    print(
        f"[info] gate: percentile-top30%={effective_gate:.3f} (floor={gate:.2f}) "
        f"-> 通過 {len(passed)}/{len(all_scored)} 件; "
        f"出力品質フロア{output_floor:.2f}超 {len(qualified)} 件 (上限{count})"
    )

    # Fallback when nothing clears the output-quality bar (M3 suppresses weak single-best).
    if not qualified:
        if not emit_fallback:
            print("[info] Track B: 0件（output_floor超え無し・fallback抑止＝飽和扱い）")
            _update_diag(diag, status="saturated", reason="no_qualified", scored=scored_n,
                         anomaly=anomaly_count, hollow=hollow_count, passed=len(passed), qualified=0)
            return []
        fallback_pool = sorted(
            all_scored, key=lambda x: (x[0], x[2].get("fine_rank", 0.0)), reverse=True
        )
        best_list = [(s, w, d) for s, w, d in fallback_pool if s >= _FALLBACK_FLOOR][:1]
        if best_list:
            ser, wid, s = best_list[0]
            s = dict(s)
            s["serendipity_rationale"] = f"（fallback）{s.get('serendipity_rationale', '')}"
            work = id_to_work[wid]
            mech_dist = min(s["mechanism_dist"], _NEAR_DOMAIN_MECH_CAP) \
                if theme_profile is not None and near_domain_signal(work, theme_profile) \
                else s["mechanism_dist"]
            print(f"[info] fallback: 1件返却 (ser={ser:.3f}, ゲート未満だが >= {_FALLBACK_FLOOR})")
            _update_diag(diag, status="fallback", reason="weak_best", scored=scored_n,
                         anomaly=anomaly_count, hollow=hollow_count, passed=len(passed), qualified=0)
            return [OutputEntry(
                work=work,
                relationship="",
                abstract_summary="",
                caution="",
                track="B",
                label=f"【接続点: {s['connection_label']}（fallback）】",
                relationship_level="",
                distance_score=round(mech_dist, 2),
                structure_score=round(s["purpose_sim"], 2),
                serendipity_score=round(ser, 2),
                usefulness_hypothesis=s["serendipity_rationale"],
            )]
        print(f"[info] Track B: 0件（ゲート未通過、fallback閾値 {_FALLBACK_FLOOR} 未満）")
        _update_diag(diag, status="saturated", reason="below_fallback_floor", scored=scored_n,
                     anomaly=anomaly_count, hollow=hollow_count, passed=len(passed), qualified=0)
        return []

    # Step 5: MMR diversity re-ranking for count > 1 (over the output-qualified set)
    if count > 1 and len(qualified) > 1:
        final = _mmr_rerank(qualified, id_to_work, lam=0.7, count=count)
    else:
        # F-10 residue: the discrete anchors tie every hit at the same product (0.56);
        # fine_rank (within-band pct x mechanism) orders what the anchors cannot separate.
        final = sorted(
            qualified, key=lambda x: (x[0], x[2].get("fine_rank", 0.0)), reverse=True
        )[:count]
    _record_rejections(
        diag, {wid for _s, wid, _d in qualified}, {wid for _s, wid, _d in final},
        floor=f"not_selected(count={count})", threshold=count,
        value_of=ser_by_id.get,
    )

    # Step 6: Build OutputEntry list
    result: List[OutputEntry] = []
    for serendipity, wid, s in final:
        work = id_to_work[wid]
        is_near = theme_profile is not None and near_domain_signal(work, theme_profile)
        mech_dist = min(s["mechanism_dist"], _NEAR_DOMAIN_MECH_CAP) if is_near else s["mechanism_dist"]
        result.append(OutputEntry(
            work=work,
            relationship="",
            abstract_summary="",
            caution="",
            track="B",
            label=_b_label(s),
            relationship_level="",
            distance_score=round(mech_dist, 2),
            structure_score=round(s["purpose_sim"], 2),
            serendipity_score=round(serendipity, 2),
            usefulness_hypothesis=s.get("serendipity_rationale", ""),
        ))
    _update_diag(diag, status="ok", scored=scored_n, anomaly=anomaly_count, hollow=hollow_count,
                 passed=len(passed), qualified=len(qualified))
    return result


def apply_post_gates(
    scores: Dict[str, dict],
    id_to_work: Dict[str, Work],
    *,
    theme_profile: Optional[ThemeProfile] = None,
    count: int = 1,
    gate: float = _SERENDIPITY_GATE,
    struct_depth_gate: float = _STRUCT_DEPTH_GATE,
    output_floor: float = _OUTPUT_FLOOR,
    emit_fallback: bool = True,
    diag: Optional[dict] = None,
) -> List[OutputEntry]:
    """Deterministic post-gate (no LLM) over agent-supplied score rows (delegation stage b).

    Each row in `scores` (keyed by work id) must carry `purpose_sim`, `mechanism_dist`,
    `connection_label`, `serendipity_rationale`; optionally `structural_depth` and
    `has_causal_pm` (the hollow judge's verdict — fail-open if absent). Re-applies the same
    hard floors as `select_track_b`: anomaly / near-domain cap / serendipity / hollow /
    percentile / output-floor / fallback / M3. Whatever the agent claims, violations are
    dropped here — the decision-layer floor under the (smart but fallible) agent layer.
    """
    if not scores:
        _update_diag(diag, status="empty_pool", scored=0, anomaly=0, hollow=0, passed=0, qualified=0)
        return []
    all_scored, anomaly_count = _serendipity_scored(scores, id_to_work, theme_profile)
    # F-09: name every rejected candidate and the floor it hit — the caller scores the
    # candidates itself, so the measured value + threshold is what calibrates its next run.
    _record_rejections(
        diag, scores.keys(), {wid for _s, wid, _d in all_scored},
        floor="anomaly(purpose_sim)", threshold=_PURPOSE_SIM_MIN,
        value_of=lambda wid: scores[wid].get("purpose_sim"),
    )
    if not all_scored:
        _update_diag(diag, status="saturated", reason="all_anomaly", scored=len(scores),
                     anomaly=anomaly_count, hollow=0, passed=0, qualified=0)
        return []
    # F-10: agent-supplied rows may carry has_causal_pm — same cap as the LLM path.
    all_scored = _apply_causal_cap(all_scored)
    kept, hollow_count, _loose = _hollow_filter(all_scored, struct_depth_gate)
    _record_rejections(
        diag, {wid for _s, wid, _d in all_scored}, {wid for _s, wid, _d in kept},
        floor="hollow(structural_depth)", threshold=struct_depth_gate,
        value_of=lambda wid: scores[wid].get("structural_depth"),
    )
    if not kept:
        _update_diag(diag, status="saturated", reason="all_hollow", scored=len(scores),
                     anomaly=anomaly_count, hollow=hollow_count, passed=0, qualified=0)
        return []
    return _quality_gate_and_build(
        kept, id_to_work, theme_profile,
        count=count, gate=gate, output_floor=output_floor, emit_fallback=emit_fallback,
        scored_n=len(scores), anomaly_count=anomaly_count, hollow_count=hollow_count, diag=diag,
    )


def select_track_b(
    candidates: List[Work],
    theme: ThemeInput,
    model: str = "gpt-4o-mini",
    *,
    count: int = 1,
    gate: float = _SERENDIPITY_GATE,
    use_llm: bool = True,
    theme_profile: Optional[ThemeProfile] = None,
    struct_depth_gate: float = _STRUCT_DEPTH_GATE,
    output_floor: float = _OUTPUT_FLOOR,
    vote_k: int = 1,
    emit_fallback: bool = True,
    diag: Optional[dict] = None,
) -> List[OutputEntry]:
    """Select Track B entries via Purpose-Mechanism analogy scoring (SOLVENT, spec §7 Step 9).

    Pipeline:
    1. Theme schema extraction: Purpose + Mechanism + analogy-poor detection.
       Analogy-poor themes (understanding-oriented / implicit physics) return [] with
       an informational message — 0 is correct, not a bug (element E).
    2. PM structure abduction: each candidate's P/M is extracted first, THEN compared
       to the theme schema. Avoids LLM surface-keyword bias (element A).
    3. serendipity = purpose_sim * effective_mechanism_dist
       Same-domain papers (near_domain_signal) get mechanism_dist capped at
       _NEAR_DOMAIN_MECH_CAP to prevent false-serendipity (element B).
    4. Percentile gate: max(top-30% threshold, gate floor). Adaptive, few high-quality
       outputs, never pads volume (element D / plan.md §5.2).
    5. MMR diversity re-ranking for count > 1 (concept Jaccard, element D).
    6. Fallback: if nothing passes the gate, returns the single best paper with
       serendipity >= _FALLBACK_FLOOR with a "(fallback)" note (element D).

    `gate` acts as the ABSOLUTE FLOOR; the percentile threshold is computed dynamically
    from the scored distribution (so it adapts to each theme's candidate pool).
    `theme_profile` (ThemeProfile from concept_distance) supplies the near_domain_signal.
    """
    def _diag(**kw):
        # M3 saturation telemetry: let the caller distinguish "no good NEW candidate this run"
        # (theme saturated -> graceful note, no weak fallback report) from analogy-poor themes.
        if diag is not None:
            diag.update(kw)

    if not candidates:
        _diag(status="empty_pool", scored=0, anomaly=0, hollow=0, passed=0, qualified=0)
        return []
    if not use_llm:
        _diag(status="ok")
        return classify_track_b(candidates, theme, model, count=count, use_llm=False)

    # Step 1: Theme schema extraction + analogy-poor detection
    print("[info] テーマのPurpose/Mechanismスキーマを抽出中...")
    theme_schema = _extract_theme_schema(theme, model)
    print(f"[info] purpose  : {theme_schema['purpose']}")
    print(f"[info] mechanism: {theme_schema['mechanism']}")
    if theme_schema["is_analogy_poor"]:
        print(f"[warn] analogy-poor テーマ: {theme_schema['poor_reason']}")
        print("[info] Track B: 0件（このテーマは構造的類推が生じにくい性質のため）")
        _diag(status="analogy_poor", scored=0, anomaly=0, hollow=0, passed=0, qualified=0)
        return []

    # Diversify before scoring: when the merged pool (keyword + citation 2-hop) exceeds the
    # scoring cap, MAX-MIN concept-Jaccard selection picks the mutually most-distant subset so
    # the P/M budget covers diverse domains instead of truncating by arbitrary list order — the
    # far citation-2-hop candidates are appended last and would otherwise be cut (element D).
    if len(candidates) > _SCORE_MAX_CANDIDATES:
        before = len(candidates)
        candidates = _maxmin_diversify(candidates, _SCORE_MAX_CANDIDATES)
        print(f"[info] MAX-MIN 多様化: {before} -> {len(candidates)} 件 (concept-Jaccard 最遠選抜)")

    id_to_work = {w.id: w for w in candidates}

    # Step 2: PM structure abduction scoring
    capped = min(len(candidates), _SCORE_MAX_CANDIDATES)
    vote_note = f" (self-consistency x{vote_k})" if vote_k > 1 else ""
    print(f"[info] P/M structure abduction: {capped} 件をスコアリング中{vote_note}...")
    scores = _score_b_candidates_pm(candidates, theme_schema, theme, model, vote_k=vote_k)
    print(f"[info] スコア取得: {len(scores)} 件")

    # Step 3: anomaly filter + near-domain cap + serendipity (deterministic post-gate).
    all_scored, anomaly_count = _serendipity_scored(scores, id_to_work, theme_profile)
    print(f"[info] Anomaly除外 (purpose_sim<{_PURPOSE_SIM_MIN}): {anomaly_count} 件")
    print(f"[info] serendipity 候補: {len(all_scored)} 件")
    if not all_scored:
        print("[info] Track B: 0件（有効スコア候補なし）")
        _diag(status="saturated", reason="all_anomaly", scored=len(scores),
              anomaly=anomaly_count, hollow=0, passed=0, qualified=0)
        return []

    # Step 3.5 (R2): candidate-level hollow gate. A separate LLM judge pass scores the
    # survivors on Structural Depth + causal Purpose-Mechanism; the deterministic
    # _hollow_filter then drops the hollow ones (fail-open when unjudged).
    print(f"[info] hollow ゲート: {len(all_scored)} 件を judge 評価中 (structural depth)...")
    judged = _judge_b_candidates(
        [(id_to_work[wid], s) for _, wid, s in all_scored], theme_schema, theme, model,
        vote_k=vote_k,
    )
    for _ser, wid, s in all_scored:
        j = judged.get(wid)
        if j is not None:
            s["structural_depth"] = j["structural_depth"]
            s["applicability"] = j["applicability"]
            s["has_causal_pm"] = j["has_causal_pm"]
            s["judge_reason"] = j["judge_reason"]
    # F-10: the judge's has_causal_pm verdict must reach the numeric grade, not just the label.
    all_scored = _apply_causal_cap(all_scored)
    all_scored, hollow_count, loose_causal_count = _hollow_filter(all_scored, struct_depth_gate)
    print(
        f"[info] hollow 除外 (structural_depth<{struct_depth_gate:.2f}): {hollow_count} 件 "
        f"-> 残 {len(all_scored)} 件 (うち因果ゆるめ {loose_causal_count} 件=思考のタネとして保持)"
    )
    if not all_scored:
        print("[info] Track B: 0件（全候補が hollow と判定）")
        _diag(status="saturated", reason="all_hollow", scored=len(scores),
              anomaly=anomaly_count, hollow=hollow_count, passed=0, qualified=0)
        return []

    # Steps 4-6: percentile gate / output floor / fallback / MMR / build (deterministic).
    return _quality_gate_and_build(
        all_scored, id_to_work, theme_profile,
        count=count, gate=gate, output_floor=output_floor, emit_fallback=emit_fallback,
        scored_n=len(scores), anomaly_count=anomaly_count, hollow_count=hollow_count, diag=diag,
    )


def _b_label(s: dict) -> str:
    """Track B connection chip. Surface the judge's verdict as an honesty signal: when the
    candidate lacks an explicit causal Purpose-Mechanism link (has_causal_pm=False) it is a
    looser, thought-seed analogy rather than a tight isomorphism (R2/#2, display-only)."""
    base = s.get("connection_label", "構造的接続")
    if s.get("has_causal_pm") is False:
        return f"【接続点（構造対応ゆるめ・思考のタネ）: {base}】"
    return f"【接続点: {base}】"


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


__all__ = [
    "classify_track_a",
    "classify_track_b",
    "select_track_b",
    "apply_post_gates",
]
