# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   roadmap #10（Phase 1 Done 判断）を前進させるため、Track B 品質評価を**再現可能な手順＋記入式ルーブリック**として整備する。実 LLM 生成を伴う評価実行を「人間/Codex が API キー在席環境で埋めるだけ」の状態にする。

---

## 2. 変更概要 (必須)

*   変更ファイル: `docs/quality_eval.md`（全面刷新）, `task.md`, `diff.md`, `Changelog.md`
*   `docs/quality_eval.md` を旧「20本レポート（100/200/200 比率・無関係4章）」前提から、現行 contrarian 方針（MVP = Track B の良質な1本・4部構成）へ刷新。
*   Done 定義（spec.md §8）・評価対象5テーマ・再現コマンド・1本ごとの観点・テーマ横断ルーブリック表・Done 成立条件を定義。

---

## 3. 確認方法 (必須)

*   `docs/quality_eval.md` のレビュー（旧版のセクションバランス観点が廃止され、4部構成・Phase 1 Done ゲートに整合しているか）。
*   コード変更なし: `python3 -m pytest tests/ -q` → 111 passed（回帰なし）。

---

## 4. 既知の課題・リスク (必須)

*   評価実行そのものは**実 LLM API 認証情報＋人間の品質判断**が必要で、無認証/自律セッションでは実施不可。本変更はテンプレート整備まで。
*   roadmap #10 の Done 判定・Pillar 配点全体の再較正は、上記評価の結果を待って実施。

---

## 5. 変更内容の詳細 (任意)

*   旧版の still-valid 観点（関係性・要約・注意点・再現性）は現行4部（RELATIONSHIP/SUMMARY/HYPOTHESIS/CAUTION/再現性）へ引き継ぎ、廃止したのは 100/200/200 比率の「セクションバランス」のみ。
*   再現コマンドは `--single --llm-model claude-haiku-4-5 --score-votes 3`（DECISION_LOG 2026-06-02 のモデル方針・R5 投票を反映）。飽和は `--allow-weak-fallback` を付けず M3 飽和ノートで確認。

---
