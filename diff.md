# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   委譲設計（`docs/research/mcp_subscription_delegation.md`）の**段階(d)**として、byrepo/Track A を**キー無しで一周**できるようにし、委譲シリーズ(a)〜(d)を完了する。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/pipeline/delegate.py`, `src/mcp_server.py`, `tests/test_delegate.py`, `DECISION_LOG.md`, `task.md`, `diff.md`, `Changelog.md`
*   `build_track_a_entries`（4-Pillar 信頼性スコア降順の決定論ランク・relationship_level を信頼性帯から付与）＋ `assemble_keyless_track_a_document`（→ `fill_track_entries(mode="structured")` → OutputDocument）。LLM 不使用。
*   MCP `byrepo_search` に `structured` フラグ追加（信頼性順＋構造整形済み Track A Markdown をキー無しで返す）。

---

## 3. 確認方法 (必須)

*   `python3 -m pytest tests/ -q` → 191 passed
*   `python3 -c "import src.mcp_server"` → OK
*   `tests/test_delegate.py`（信頼性順ランク / キー無しでの4部充足）

---

## 4. 既知の課題・リスク (必須)

*   設計要点: Track A は選別が決定論（信頼性スコア）のため**再ゲート不要**＝Track B（`delegate_finalize`）より単純。エージェントは後でプローズを磨くだけ。
*   実エージェントによる採点ループの実運用手順化（roadmap #10 の評価とセット）、agentmemory 周回メモリ統合は未着手。
*   スコア設計値は不変。

---

## 5. 変更内容の詳細 (任意)

*   byrepo は元々 collect/score が決定論（GitHub/OpenAlex 取得のみ、LLM なし）。`classify_track_a(use_llm=False)` と `mode="structured"` も決定論であることを確認済み。
*   `structured=true` の MCP `byrepo` は、信頼性スコアで sort・trim 後 `assemble_keyless_track_a_document` で組み立て、`render_markdown` で出力（Track A の Reliability/Verified Maturity/Third-Party 内訳表示はそのまま機能）。
*   委譲シリーズ総括: (a) bybridge キー無し structured → (b) post-gate 純関数化 → (c) `delegate_finalize` ＋ JSON スキーマ → (d) Track A キー無し組み立て。

---
