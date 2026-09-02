"""Key-free (no-LLM) delegation path: contra as a material provider.

Stage (a) of the MCP-client delegation design
(``docs/research/mcp_subscription_delegation.md``): run a full ``bybridge`` loop
— collect → deterministic bridge ranking → structured 4-part assembly → markdown —
with **no LLM API key**. The LLM-dependent scoring (purpose_sim × mechanism_dist,
hollow judgement) and the polished 4-part authoring are left for the calling agent
(Max/Opus) to fill in later; here every step is deterministic so the loop completes
offline (OpenAlex collection only).

These functions are pure (they take already-collected candidates/bridges as input),
so they unit-test without network or LLM access.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from typing import Any, Dict, List, Optional, Sequence, Set

from src.core.models import (
    Concept,
    OutputDocument,
    OutputEntry,
    OutputSection,
    ThemeInput,
    Work,
)
from src.pipeline.classify import apply_post_gates
from src.pipeline.bridges import (
    annotate_bridge_signals,
    diversify_head_by_bridge,
    hybrid_bridge_rank_key,
    shared_bridge_count,
)
from src.pipeline.concept_distance import ThemeProfile, near_domain_signal
from src.pipeline.generate import GenerationConfig, fill_track_entries


def _l01_jaccard(work: Work, profile: Optional[ThemeProfile]) -> float:
    """Deterministic L0/L1 concept overlap between a work and the theme (0..1)."""
    if profile is None or not getattr(profile, "l01", None):
        return 0.0
    work_l01 = {tag.name for tag in work.concept_tags if tag.level <= 1 and tag.name}
    union = work_l01 | profile.l01
    if not union:
        return 0.0
    return len(work_l01 & profile.l01) / len(union)


def select_bridge_candidates_raw(
    cands: Sequence[Work],
    bridges: Set[str],
    *,
    profile: Optional[ThemeProfile] = None,
    count: int = 3,
    drop_near_domain: bool = True,
) -> List[Work]:
    """Deterministic, key-free candidate selection.

    Drops same-broad-domain (myopia) candidates via the deterministic L0/L1 Jaccard
    gate, then ranks by shared citation-bridge count (more shared bridges = stronger
    structural link). No LLM. This is the code-layer pre-filter; the agent layer adds
    purpose/mechanism judgement on top.
    """
    pool = list(cands)
    if drop_near_domain and profile is not None and not profile.is_empty():
        pool = [w for w in pool if not near_domain_signal(w, profile)]
    # Hybrid-first ranking (C(ii), 2026-08-22): when the caller annotated the pool with
    # annotate_hybrid_rank (theme relevance leading, citations demoted to a tie-breaker),
    # that score sorts first; unannotated pools fall back to the legacy structural order
    # (betweenness, then co-citation strength) because every hybrid score is 0.0.
    annotate_bridge_signals(pool, bridges)
    pool.sort(key=hybrid_bridge_rank_key, reverse=True)
    pool = diversify_head_by_bridge(pool, bridges, window=max(count, 0), per_bridge_cap=2)
    return pool[: max(count, 0)]


def build_bridge_entries(
    cands: Sequence[Work],
    bridges: Set[str],
    *,
    profile: Optional[ThemeProfile] = None,
    count: int = 3,
) -> List[OutputEntry]:
    """Build deterministic Track B entries (no LLM, no 4-part prose yet).

    distance_score comes from the deterministic L0/L1 Jaccard (far = high). The
    structure/serendipity scores require LLM judgement and stay at 0.0 for the
    delegated agent to fill.
    """
    chosen = select_bridge_candidates_raw(cands, bridges, profile=profile, count=count)
    entries: List[OutputEntry] = []
    for work in chosen:
        shared = shared_bridge_count(work, bridges)
        betweenness = int((work.source_meta or {}).get("bridge_betweenness", 0) or 0)
        distance = round(1.0 - _l01_jaccard(work, profile), 2)
        entries.append(
            OutputEntry(
                work=work,
                relationship="",
                abstract_summary="",
                caution="",
                track="B",
                label=f"引用ブリッジ（共有 {shared} 本 / 異分野 {betweenness}）",
                distance_score=distance,
                structure_score=0.0,
                serendipity_score=0.0,
            )
        )
    return entries


def assemble_keyless_bridge_document(
    theme: ThemeInput,
    cands: Sequence[Work],
    bridges: Set[str],
    *,
    profile: Optional[ThemeProfile] = None,
    count: int = 3,
    config: Optional[GenerationConfig] = None,
    section_title: str = "Track B: 引用ブリッジ候補（キー無し・構造整形）",
) -> OutputDocument:
    """Full key-free assembly: deterministic selection → structured 4-part fill → document.

    ``fill_track_entries(mode="structured")`` is fully deterministic (it never calls the
    LLM), so the entire document is produced without an API key.
    """
    entries = build_bridge_entries(cands, bridges, profile=profile, count=count)
    filled = fill_track_entries(entries, config or GenerationConfig(), theme=theme, mode="structured")
    section = OutputSection(title=section_title, track="B", entries=filled)
    return OutputDocument(theme=theme, sections=[section])


# --- Stage (c): accept agent scoring and finalize through the post-gate -----
#
# Contract for one delegated candidate (the agent returns a list of these). The
# metadata fields are the material contra handed out (so the Work can be rebuilt
# without re-collecting); the scoring fields are the agent's own judgement, which
# the deterministic post-gate then re-checks against the hard floors.
#
#   {
#     # --- candidate material (echoed back from contra) ---
#     "id": str,                       # required (OpenAlex/work id; the join key)
#     "title": str, "abstract": str|null,
#     "year": int, "venue": str, "doi": str|null, "cited_by_count": int,
#     "concepts": [str], "concept_tags": [{"name": str, "level": int, "score": float}],
#     "referenced_works": [str], "publication_type": str|null,
#     # --- agent scoring (the delegated LLM judgement) ---
#     "purpose_sim": float,            # required, 0..1
#     "mechanism_dist": float,         # required, 0..1
#     "structural_depth": float|null,  # optional hollow-judge verdict, 0..1
#     "has_causal_pm": bool|null,      # optional
#     "connection_label": str,         # optional (default below)
#     "serendipity_rationale": str,    # optional -> usefulness hypothesis
#     # --- optional agent prose (else deterministic structured fill) ---
#     "relationship": str, "summary": str, "caution": str,
#   }
AGENT_SCORE_REQUIRED = ("id", "purpose_sim", "mechanism_dist")


def _as_float(value: Any) -> float:
    return float(value)


def work_from_material(material: Dict[str, Any]) -> Work:
    """Rebuild a Work from the candidate material the agent echoes back."""
    tags = [
        Concept(name=str(t.get("name", "")), level=int(t.get("level", 0)), score=float(t.get("score", 0.0)))
        for t in (material.get("concept_tags") or [])
        if t.get("name")
    ]
    return Work(
        id=str(material["id"]),
        title=str(material.get("title", "")),
        year=int(material.get("year") or 0),
        venue=str(material.get("venue", "")),
        doi=material.get("doi"),
        cited_by_count=int(material.get("cited_by_count") or 0),
        abstract=material.get("abstract"),
        concepts=[str(c) for c in (material.get("concepts") or [])],
        concept_tags=tags,
        publication_type=material.get("publication_type"),
        referenced_works=[str(r) for r in (material.get("referenced_works") or [])],
    )


def material_from_work(work: Work) -> Dict[str, Any]:
    """Serialize a Work into the candidate-material dict the agent scores and echoes back.

    The inverse of :func:`work_from_material`: contra's key-free raw collection emits these so the
    calling agent can score them and pass the scored list to :func:`finalize_delegated_document`
    (the ``delegate_finalize`` MCP tool). Carries exactly the fields ``work_from_material`` reads,
    so a round-trip preserves the Work.
    """
    return {
        "id": work.id,
        "title": work.title,
        "abstract": work.abstract,
        "year": work.year,
        "venue": work.venue,
        "doi": work.doi,
        "cited_by_count": work.cited_by_count,
        "concepts": list(work.concepts or []),
        "concept_tags": [
            {"name": t.name, "level": t.level, "score": t.score}
            for t in (work.concept_tags or [])
        ],
        "referenced_works": list(work.referenced_works or []),
        "publication_type": work.publication_type,
    }


def score_row_from_material(material: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the post-gate score row from an agent-scored candidate."""
    row: Dict[str, Any] = {
        "purpose_sim": _as_float(material["purpose_sim"]),
        "mechanism_dist": _as_float(material["mechanism_dist"]),
        "connection_label": str(material.get("connection_label") or "構造的接続"),
        "serendipity_rationale": str(material.get("serendipity_rationale") or ""),
    }
    # F-10 residue: optional fine within-band percentage — breaks ties the discrete
    # grades create. Agent-supplied floats are usually continuous already, but agents
    # that mirror contra's anchor grid (0.80 x 0.70) benefit from the same tie-breaker.
    if material.get("purpose_pct") is not None:
        try:
            pct = max(0, min(100, int(material["purpose_pct"])))
            row["purpose_pct"] = pct
            row["fine_rank"] = round((pct / 100.0) * row["mechanism_dist"], 4)
        except (TypeError, ValueError):
            pass
    if material.get("structural_depth") is not None:
        row["structural_depth"] = _as_float(material["structural_depth"])
    if material.get("has_causal_pm") is not None:
        row["has_causal_pm"] = bool(material["has_causal_pm"])
    return row


# --- A1 (2026-08-22 ruling): the grounding contract — quote-then-claim ------
#
# F-04/F-05: relational prose returned by the tools was a free generation conditioned on
# the theme, not anchored in either text — it fabricated theme-side propositions ("需要の
# 変動" on a theme that never mentions demand) and source-side summaries. The fix follows
# the delegation architecture the user chose: the CALLING AGENT is the LLM, and contra is
# the deterministic verifier. Any agent-supplied relational prose must arrive with two
# verbatim quotes — one from the submitted theme text, one from the candidate's own
# title/abstract — and code (not a model) checks the quotes actually occur in those
# texts. Prose whose quotes fail verification is dropped (the deterministic structured
# fill takes over) and the failure is named in the output, F-09 style. Scores are NOT
# touched: the agent's judgement stands, only ungrounded prose is refused.

_QUOTE_MIN_CHARS = 10   # a quote shorter than this can't anchor a claim (single-word gaming)

# F-19 (2026-09-01, seihai): verification runs against the material the CALLER echoed back,
# NOT against contra's own record of the candidate. When the caller sends only `id` + its
# score fields, the haystack is empty and every quote — including a verbatim-correct one —
# is reported as "存在しない（逐語一致が必要）". That message reads as "your quote was
# fabricated" and sends the caller to re-check its own prose; the actual cause is the
# missing echo field, reported in a SEPARATE block with no causal link between the two.
# An empty haystack is not a mismatch — it is 照合不能 — and its cause must be named in
# the same sentence.
_UNVERIFIABLE_MARK = "照合不能"
_ECHO_REMEDY = "contra が返した候補材料を全欄 echo して、同じ引用のまま再投してください"


def _empty_fields(material: Dict[str, Any], keys: Sequence[str]) -> List[str]:
    """Which of ``keys`` the caller left empty/absent in the echoed material."""
    return [k for k in keys if not str(material.get(k) or "").strip()]


def has_unverifiable_failure(reasons: Sequence[str]) -> bool:
    """True when any failure reason is a missing-material 照合不能 (not a real mismatch)."""
    return any(_UNVERIFIABLE_MARK in str(r) for r in reasons)


def _norm_quote_space(text: str) -> str:
    """Whitespace-insensitive, case-insensitive normal form for verbatim matching.

    ALL whitespace is removed (not collapsed): an agent-side line break inside a Japanese
    phrase would otherwise insert a space that spaceless Japanese text can never match.
    Both haystack and needle get the same treatment, so ordering is preserved.
    """
    import re as _re
    return _re.sub(r"\s+", "", str(text or "")).casefold()


def theme_grounding_text(theme: ThemeInput) -> str:
    """The submitted text a theme_quote may be drawn from — nothing else counts."""
    parts = [
        theme.theme_overview, theme.goal, theme.why_problem,
        " ".join(theme.assumptions or []), getattr(theme, "concern", "") or "",
    ]
    return _norm_quote_space(" ".join(p for p in parts if p))


def verify_grounding(material: Dict[str, Any], theme_text_norm: str) -> List[str]:
    """Deterministically verify a candidate's quote-then-claim block.

    Returns a list of failure reasons (empty = grounded). Rules:
    - prose fields (relationship / serendipity_rationale) REQUIRE both quotes;
    - theme_quote must occur verbatim (whitespace/case-normalised) in the submitted
      theme text; source_quote must occur in the candidate's OWN title+abstract;
    - quotes below _QUOTE_MIN_CHARS cannot anchor anything.
    """
    has_prose = bool(material.get("relationship") or material.get("serendipity_rationale"))
    if not has_prose:
        return []
    failures: List[str] = []
    theme_quote = _norm_quote_space(material.get("theme_quote") or "")
    source_quote = _norm_quote_space(material.get("source_quote") or "")
    if len(theme_quote) < _QUOTE_MIN_CHARS:
        failures.append("theme_quote 欠落または短すぎ（10字以上の逐語抜粋が必要）")
    elif not theme_text_norm:
        # F-19 theme-side twin: nothing was submitted to match against.
        failures.append(
            f"{_UNVERIFIABLE_MARK}: 提出テーマ本文が空のため theme_quote を照合できません"
            "（引用の誤りではなく theme 欄の欠落が原因です）"
        )
    elif theme_quote not in theme_text_norm:
        failures.append("theme_quote が提出テーマ本文に存在しない（逐語一致が必要）")
    source_missing = _empty_fields(material, ("title", "abstract"))
    source_text = _norm_quote_space(
        f"{material.get('title') or ''} {material.get('abstract') or ''}"
    )
    if len(source_quote) < _QUOTE_MIN_CHARS:
        failures.append("source_quote 欠落または短すぎ（10字以上の逐語抜粋が必要）")
    elif not source_text:
        # F-19: the haystack itself is absent. Distinguish 照合不能 from 不一致 and name
        # the cause in the same sentence — the caller must not be sent to audit its quotes.
        failures.append(
            f"{_UNVERIFIABLE_MARK}: 候補の {'/'.join(source_missing) or 'title/abstract'} が"
            "送られていないため source_quote を照合できません"
            f"（引用の誤りではなく材料欄の欠落が原因です。{_ECHO_REMEDY}）"
        )
    elif source_quote not in source_text:
        msg = "source_quote が候補の title/abstract に存在しない（逐語一致が必要）"
        if source_missing:
            # Partial echo: title present, abstract absent. A correct abstract quote still
            # fails here, so say so rather than letting it read as fabrication.
            msg += (
                f" ※ ただし {'/'.join(source_missing)} が送られていません"
                f"——{'/'.join(source_missing)} からの引用であればこれが原因です（{_ECHO_REMEDY}）"
            )
        failures.append(msg)
    return failures


# Material fields the agent is contractually expected to echo back (F-09). They are not
# hard-required (the join key + scores are), but when they are missing the rendered output
# silently degrades to blank headings / "abstract欠損" / "年: 0" — which reads as a low-quality
# hit instead of a caller mistake. finalize surfaces these as explicit warnings.
ECHO_RECOMMENDED = ("title", "abstract", "year", "venue", "cited_by_count")


def echo_completeness_warnings(materials: Sequence[Dict[str, Any]]) -> List[str]:
    """One warning line per candidate whose echoed material is missing recommended fields."""
    warnings: List[str] = []
    for i, material in enumerate(materials):
        missing = [
            k for k in ECHO_RECOMMENDED
            if material.get(k) is None or (k in ("title", "venue") and not str(material.get(k) or "").strip())
        ]
        if missing:
            wid = str(material.get("id") or f"#{i}")
            line = (
                f"⚠ 候補 {wid}: 材料欄が欠けたまま送信されています（{', '.join(missing)}）"
                "— 該当欄は空のまま描画されます。contra が返した候補材料を全欄 echo してください。"
            )
            # F-19: this warning used to read as a cosmetic/rendering problem, so callers
            # ignored it and then read the grounding failure as "my quote was wrong".
            # title/abstract are also the ONLY haystack source_quote is matched against.
            if any(k in ("title", "abstract") for k in missing):
                line += (
                    " ★ この欠落は接地検証も不能にします（source_quote は送られた"
                    " title/abstract に対してのみ照合されるため、正しい引用でも失敗します）。"
                )
            warnings.append(line)
    return warnings


def normalize_agent_scores(
    materials: Sequence[Dict[str, Any]],
) -> "tuple[Dict[str, Work], Dict[str, dict], Dict[str, Dict[str, Any]]]":
    """Validate + split agent-scored candidates into (works, score rows, raw-by-id).

    Raises ValueError if a candidate is missing a required field.
    """
    works: Dict[str, Work] = {}
    scores: Dict[str, dict] = {}
    by_id: Dict[str, Dict[str, Any]] = {}
    for i, material in enumerate(materials):
        for key in AGENT_SCORE_REQUIRED:
            if material.get(key) is None:
                raise ValueError(f"delegated candidate #{i} missing required field '{key}'")
        wid = str(material["id"])
        works[wid] = work_from_material(material)
        scores[wid] = score_row_from_material(material)
        by_id[wid] = material
    return works, scores, by_id


def finalize_delegated_document(
    materials: Sequence[Dict[str, Any]],
    theme: ThemeInput,
    *,
    theme_profile: Optional[ThemeProfile] = None,
    count: int = 1,
    config: Optional[GenerationConfig] = None,
    emit_fallback: bool = True,
    grounded_only: bool = True,
    section_title: str = "Track B: 接続点フィーチャー（委譲採点 → post-gate）",
    diag: Optional[dict] = None,
    **gate_kwargs: Any,
) -> OutputDocument:
    """Stage (c): run agent-scored candidates through the deterministic post-gate.

    The agent supplies purpose_sim / mechanism_dist / (optional) structural_depth etc.;
    ``apply_post_gates`` re-applies the hard floors (anomaly / near-cap / serendipity /
    hollow / percentile / output-floor / fallback / M3) with NO LLM. Any agent-supplied
    4-part prose is honored; missing parts fall back to the deterministic structured fill.

    A1 grounding contract (``grounded_only``, default True): agent-supplied relational
    prose must carry a verbatim ``theme_quote`` (from the submitted theme text) and
    ``source_quote`` (from the candidate's own title/abstract). Code verifies the quotes;
    on failure ALL agent prose for that candidate is dropped (structured fill takes over),
    scores are untouched, and the failure is recorded in ``diag["grounding_failures"]``.
    """
    if grounded_only:
        theme_text = theme_grounding_text(theme)
        checked: List[Dict[str, Any]] = []
        failures_by_id: List[Dict[str, Any]] = []
        for material in materials:
            reasons = verify_grounding(material, theme_text)
            if reasons:
                material = dict(material)
                for field in ("relationship", "summary", "caution", "serendipity_rationale"):
                    material.pop(field, None)
                failures_by_id.append({"id": str(material.get("id") or "?"), "reasons": reasons})
            checked.append(material)
        materials = checked
        if diag is not None and failures_by_id:
            diag["grounding_failures"] = failures_by_id
    works, scores, by_id = normalize_agent_scores(materials)
    entries = apply_post_gates(
        scores, works,
        theme_profile=theme_profile, count=count, emit_fallback=emit_fallback,
        diag=diag, **gate_kwargs,
    )
    # Seed any agent-supplied prose, then deterministically fill the rest (no LLM).
    seeded: List[OutputEntry] = []
    for entry in entries:
        material = by_id.get(entry.work.id, {})
        seeded.append(dc_replace(
            entry,
            relationship=str(material.get("relationship") or "") or entry.relationship,
            abstract_summary=str(material.get("summary") or "") or entry.abstract_summary,
            caution=str(material.get("caution") or "") or entry.caution,
        ))
    filled = fill_track_entries(seeded, config or GenerationConfig(), theme=theme, mode="structured")
    section = OutputSection(title=section_title, track="B", entries=filled)
    return OutputDocument(theme=theme, sections=[section])


# --- Stage (d): key-free Track A (byrepo) assembly --------------------------
#
# Track A delegation is simpler than Track B: byrepo's selection is the 4-Pillar
# Reliability Score, computed deterministically in code (no LLM). There is no
# agent-supplied number for contra to re-gate -- the only LLM step is the 4-part
# prose. So the key-free path collects + scores (deterministic) and fills the
# prose with the structured mode; the agent refines the prose afterward in its
# own context. (Track B, by contrast, needs delegate_finalize because the agent
# supplies purpose_sim/mechanism_dist that the post-gate must re-check.)

_TRACK_A_LABEL = "実装アンカー"


def _reliability_level(score: int) -> str:
    """Quality band of the Reliability score. NOT the 関係度 label (F-17) — kept for callers
    that want to name the quality band explicitly."""
    if score >= 70:
        return "高"
    if score >= 40:
        return "中"
    return "低"


def build_track_a_entries(works: Sequence[Work], *, count: int = 3) -> List[OutputEntry]:
    """Deterministic Track A entries: reliability x relevance ranking (F-03), no LLM."""
    from src.pipeline.track_a import (   # local import avoids a cycle
        anchor_rank_key, anchor_relevance, relevance_level,
    )
    chosen = sorted(works, key=anchor_rank_key, reverse=True)[: max(count, 0)]
    return [
        OutputEntry(
            work=work,
            relationship="",
            abstract_summary="",
            caution="",
            track="A",
            label=_TRACK_A_LABEL,
            # F-17 (2026-09-01): 関係度 is the theme-relevance band. It used to be
            # _reliability_level(reliability_score) — a quality band with no theme in it —
            # so the one on-topic anchor read 「中」 and two off-topic ones read 「高」.
            # Reliability still renders on its own line under its own name.
            relationship_level=relevance_level(anchor_relevance(work)),
        )
        for work in chosen
    ]


def assemble_keyless_track_a_document(
    theme: ThemeInput,
    works: Sequence[Work],
    *,
    count: int = 3,
    config: Optional[GenerationConfig] = None,
    section_title: str = "Track A: Practical Anchors（キー無し・構造整形）",
) -> OutputDocument:
    """Full key-free Track A assembly: deterministic reliability ranking → structured fill."""
    entries = build_track_a_entries(works, count=count)
    filled = fill_track_entries(entries, config or GenerationConfig(), theme=theme, mode="structured")
    section = OutputSection(title=section_title, track="A", entries=filled)
    return OutputDocument(theme=theme, sections=[section])


__all__ = [
    "select_bridge_candidates_raw",
    "build_bridge_entries",
    "assemble_keyless_bridge_document",
    "AGENT_SCORE_REQUIRED",
    "work_from_material",
    "material_from_work",
    "score_row_from_material",
    "normalize_agent_scores",
    "finalize_delegated_document",
    "build_track_a_entries",
    "assemble_keyless_track_a_document",
]
