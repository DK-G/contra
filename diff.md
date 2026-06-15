# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   委譲設計（`docs/research/mcp_subscription_delegation.md`）の**段階(b)**として、`select_track_b` の決定論ゲートを LLM 採点/judge から切り離し、純関数 `apply_post_gates`（コードの硬い床）として切り出す。エージェント採点に対しても同じ数値床を機械的に再適用できるようにする。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/pipeline/classify.py`, `tests/test_post_gates.py`（新規）, `DECISION_LOG.md`, `task.md`, `diff.md`, `Changelog.md`
*   共有純関数（LLM 不使用）: `_serendipity_scored`（anomaly＋near-domain cap＋serendipity）/ `_hollow_filter`（hollow 棄却・fail-open）/ `_quality_gate_and_build`（percentile→output_floor→fallback/M3→MMR→構築）。
*   `apply_post_gates(scores, id_to_work, ...)` を新設＝委譲用 post-gate。`select_track_b` も同じ純関数を呼ぶよう refactor（ゲート実装を一本化）。

---

## 3. 確認方法 (必須)

*   `python3 -m pytest tests/ -q` → 185 passed（refactor 後も M3 飽和 / score voting / purpose_level 等の Track B テストが全 green ＝挙動不変）
*   `tests/test_post_gates.py`（anomaly / hollow / near-domain cap / fallback vs 飽和 / 因果ゆるめ表示 / 強候補通過）

---

## 4. 既知の課題・リスク (必須)

*   段階(c)（エージェント採点を受け取る JSON スキーマ定義＋ MCP 委譲経路）、段階(d)（byrepo/Track A 委譲）は未着手。
*   スコア設計値（`_PURPOSE_SIM_MIN=0.20` / `_STRUCT_DEPTH_GATE=0.50` / `_OUTPUT_FLOOR=0.35` / `_FALLBACK_FLOOR=0.10` / `_NEAR_DOMAIN_MECH_CAP=0.5`）は不変。ゲートの所在をコード側へ集約しただけ（`spec.md` 禁則順守）。

---

## 5. 変更内容の詳細 (任意)

*   `apply_post_gates` の入力 score 行は `{purpose_sim, mechanism_dist, connection_label, serendipity_rationale}` 必須、`{structural_depth, has_causal_pm}` 任意（hollow judge 欠落時は fail-open）。
*   `select_track_b` の LLM 経路では従来どおり `_score_b_candidates_pm`（採点）と `_judge_b_candidates`（hollow judge）を呼び、結果を score 行へマージしてから同じ純関数群に渡す。両経路でゲート挙動が一致する。

---
