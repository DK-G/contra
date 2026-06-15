# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   委譲設計（`docs/research/mcp_subscription_delegation.md`）の**段階(c)**として、3段フロー [1]contra 生候補 → [2]エージェント採点 → [3]contra post-gate の **[3] を MCP 経由で完結**させる。エージェント採点を受け取る JSON スキーマと委譲経路を定義する。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/pipeline/delegate.py`, `src/mcp_server.py`, `tests/test_delegate.py`, `DECISION_LOG.md`, `task.md`, `diff.md`, `Changelog.md`
*   候補素材＋エージェント採点の JSON 契約（`AGENT_SCORE_REQUIRED`）、`work_from_material` / `score_row_from_material` / `normalize_agent_scores` / `finalize_delegated_document` を追加。
*   MCP ツール `delegate_finalize`（theme＋agent-scored `candidates` → `apply_post_gates` → Track B Markdown＋診断）。LLM・API キー不使用。

---

## 3. 確認方法 (必須)

*   `python3 -m pytest tests/ -q` → 189 passed
*   `python3 -c "import src.mcp_server"` → OK
*   `tests/test_delegate.py`（Work 再構築 / 必須欠落で ValueError / 強候補通過＋プローズ尊重 / エージェント主張でも anomaly は棄却）

---

## 4. 既知の課題・リスク (必須)

*   段階(d)（byrepo/Track A 委譲）は未着手。
*   `finalize_delegated_document` は `theme_profile` 任意（seeds 無しでは near-domain cap が効かない）。実運用では bybridge/byserendipity の生候補取得時に得た profile を併せて渡すのが望ましい。
*   スコア設計値は不変（段階 b の床をそのまま適用）。実エージェントによる採点ループの実運用手順化は roadmap #10 の評価とあわせて。

---

## 5. 変更内容の詳細 (任意)

*   JSON 契約: 候補1件が「contra が配った素材（id/title/abstract/year/venue/doi/cited_by_count/concepts/concept_tags/referenced_works）」＋「エージェント採点（purpose_sim/mechanism_dist 必須、structural_depth/has_causal_pm 任意、connection_label/serendipity_rationale、任意の relationship/summary/caution）」。
*   `finalize_delegated_document` はエージェント提供プローズを優先し、欠落分のみ `fill_track_entries(mode="structured")` で決定論補完（LLM 不使用）。
*   Work を素材 JSON から再構築するため、エージェントは採点用に受け取った素材をそのまま投げ返せばよく、再収集も contra 側 LLM 採点も不要。

---
