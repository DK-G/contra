# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   LLM 判定・生成を contra 自身の API キー（従量課金）から外し、呼び出し側エージェント（Max サブスク）の推論へ委譲する設計（`docs/research/mcp_subscription_delegation.md`）の**段階(a)**として、bybridge を**キー無しで一周**できるようにする。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/pipeline/delegate.py`（新規）, `src/mcp_server.py`, `tests/test_delegate.py`（新規）, `DECISION_LOG.md`, `task.md`, `diff.md`, `Changelog.md`
*   `delegate.py`（純関数）: 決定論選別（near_domain でマイオピア pre-filter ＋共有 citation-bridge 数で順位付け）→ `fill_track_entries(mode="structured")`（LLM 不使用）→ OutputDocument。
*   MCP `bybridge` に `structured`（bool, 既定 False）を追加。`raw_only=true, structured=true` でキー無し 4部 Markdown を返す。

---

## 3. 確認方法 (必須)

*   `python3 -m pytest tests/ -q` → 179 passed
*   `python3 -c "import src.mcp_server"` → OK
*   `tests/test_delegate.py`（順位付け / near-domain 棄却 / 決定論スコア / キー無しでの 4部充足）

---

## 4. 既知の課題・リスク (必須)

*   structure/serendipity スコアは LLM 判定待ちのため 0.0（委譲先エージェントが補充）。distance_score は L0/L1 Jaccard の決定論値。
*   段階(b)（数値ゲートの純関数化・post-gate）、(c)（エージェント採点 JSON スキーマ）、(d)（byrepo 委譲）は未着手。
*   用途スコープは作者自身（個人/研究）。製品バックエンドとして不特定多数に叩かせる形にはしない。

---

## 5. 変更内容の詳細 (任意)

*   `select_bridge_candidates_raw`: `near_domain_signal`（既存・L0/L1 Jaccard）で同一広域ドメインを棄却し、共有 bridge 数で降順。新たなスコア設計値は導入せず既存の閾値ロジックを再利用。
*   `assemble_keyless_bridge_document`: structured 整形が `responses_create` を一切経由しないことをコードで確認済み（`generate.py:fill_track_entries` の mode 分岐）。
*   既存の bybridge 経路（flat list / LLM 選別・生成）は非破壊。

---
