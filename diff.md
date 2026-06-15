# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   A-RS1: byrepo Reliability Score の Pillar 2 (LMA) が「完成した安定ライブラリ」を最も強く罰する問題（DECISION_LOG 2026-06-12 懸念1）を、改善方針候補1「完成判定の床」で緩和する。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/pipeline/git_collect.py`, `src/core/models.py`, `tests/test_git_collect.py`, `DECISION_LOG.md`, `roadmap.md`, `task.md`, `diff.md`, `Changelog.md`
*   `_lma_score` を「鮮度（freshness）」算出と「完成判定の床」適用の2段構成へ分離。`_is_completed_stable(repo)` を新設。
*   issue サンプルの open/closed 件数を `GitRepository` に構造化保持（`issue_open_count` / `issue_closed_count`）し、`source_meta` へ露出。

---

## 3. 確認方法 (必須)

*   `python3 -m pytest tests/ -q` → 95 passed
*   床の発火/非発火: `tests/test_git_collect.py::test_lma_floor_*`（強採用→15 / 中採用→12 / 未採用・issue履歴なし→1 / 未解決滞留→1 / 新鮮→25）

---

## 4. 既知の課題・リスク (必須)

*   改善方針候補2「候補プール内相対正規化」と A-RS2（Pillar 1 配点移行）は未着手。
*   床判定の close 率は issue サンプル（既定 per_page）に基づくヒューリスティックであり、母集団全件の正確な close 率ではない。

---

## 5. 変更内容の詳細 (任意)

*   `_is_completed_stable`: 採用シグナル（`stars >= 50` または `forks >= 10`）と、過去 issue 活動＋高クローズ率（`closed > 0` かつ `closed >= open`）の**両方**を要求し、「完成」と「誰も使っていない」を区別する（Pillar 3「ゼロIssueの罠」と同型）。
*   床値は基本 12点、強採用（`stars >= 200`）で 15点。`max(freshness, floor)` のため新鮮な repo のスコアは下げない。撤廃（鮮度ゼロ化）はせず互換性腐敗の実害を考慮して満点復帰もさせない。

---
