# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   A-RS1 改善方針候補2「候補プール内相対正規化」を実装し、成熟ドメインで候補プール全体が stale でも、最も手入れされた repo が Pillar 2 (LMA) で浮上するようにする。これで A-RS1（候補1 完成判定の床＋候補2）を完了とする。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/pipeline/git_collect.py`, `tests/test_git_collect.py`, `DECISION_LOG.md`, `roadmap.md`, `task.md`, `diff.md`, `Changelog.md`
*   `_apply_pool_relative_lma(repos)` を新設し、`collect_track_a_git_repos` の後段（sort 前）で適用。
*   `GitCollectConfig.pool_relative_lma`（既定 True）で切替可能。

---

## 3. 確認方法 (必須)

*   `python3 -m pytest tests/ -q` → 99 passed
*   `tests/test_git_collect.py::test_pool_relative_lma_*`（stale ドメインで最新が浮上 / 新鮮 repo 不変 / 小プール no-op / 同点等クレジット）

---

## 4. 既知の課題・リスク (必須)

*   A-RS2（Pillar 1 配点を時間・他人系シグナルへ移行、GITHUB_TOKEN 事実上必須化とセット）は未着手。
*   相対順位は recency の magnitude を無視するヒューリスティック。順位天井 12点（完成判定の床 15点より低位）＋ `max` 意味論のため、被害（新鮮 repo の不当降格や順位だけでの逆転）は限定的。

---

## 5. 変更内容の詳細 (任意)

*   `_apply_pool_relative_lma`: 各 repo の push 鮮度（`pushed_at or updated_at`）を pool 内でランク付けし、`base(2)〜ceiling(12)` の相対スコアを `percentile` 線形で付与。`relative > 現 lma` のときのみ lma を上書きし、4 Pillars から `reliability_score` を再計算。
*   同日 push は同クレジット（`more_stale = days より厳密に大きい件数`）。プールサイズ 3 未満は no-op。追加 API 呼び出しなし。

---
