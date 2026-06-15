# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   A-RS2: byrepo Reliability Score の Pillar 1 が README 成熟度に偏重し、vibe coding 時代に水増し容易になっている問題（DECISION_LOG 2026-06-12 懸念2）を是正する。配点を、生成で水増しできない「時間」系シグナル（CI 実行履歴＋リリース刻み）へ段階移行する**先手**を実装する。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/pipeline/git_collect.py`, `src/core/models.py`, `src/core/output_spec.py`, `src/cli/main.py`, `tests/test_git_collect.py`, `DECISION_LOG.md`, `roadmap.md`, `task.md`, `diff.md`, `Changelog.md`
*   `_verified_maturity_score`（最大12点）= `_release_cadence_score`（最大6）＋`_ci_health_score`（最大6）を新設。
*   Pillar 1（最大30据え置き）をリッチシグナル取得時のみ README 系 0.6 倍へスケールし、空いた12点を verified maturity に移譲。
*   `_fetch_release_signal` / `_fetch_ci_signal` を追加し収集経路へ接続。`GitCollectConfig.include_rich_signals`（既定 None=トークン在席時のみ自動有効）。CLI `--git-rich-signals/--no-git-rich-signals`。

---

## 3. 確認方法 (必須)

*   `python3 -m pytest tests/ -q` → 107 passed
*   `tests/test_git_collect.py::test_rich_signals_migrate_weight_off_readme`（README 偏重の降格）/ `test_collect_with_rich_signals_exposes_verified_maturity`（収集経路での露出）

---

## 4. 既知の課題・リスク (必須)

*   「他人」系シグナル（外部コントリビュータ / owner 以外の起票者 / dependents）は A-RS2 続編として未着手。
*   リッチシグナルは repo ごと約2 REST 呼び出し増。無認証 60 req/h を踏むため**トークン前提**（既定はトークン在席時のみ自動有効、無認証は従来スコアにフォールバック＝回帰なし）。
*   トークン在席時は README のみで満点だった repo が相対的に降格する（A-RS2 の狙い通りの是正だが、出力順位が変わる behavior change）。

---

## 5. 変更内容の詳細 (任意)

*   `_release_cadence_score`: 公開リリース数による versioning discipline（1本=2 / 3本+=+2 / 6本+=+2、最大6）。鮮度は Pillar 2 の役割なので cadence は本数ベース。
*   `_ci_health_score`: 直近 Actions runs の実行（+3）＋成功率（≥0.8 で+3、≥0.5 で+1、最大6）。「workflow file がテキストに出る」Pillar 4 ヒューリスティックと異なり「回って通っている」事実を採点。
*   取得失敗は graceful degrade（各シグナル 0 点、`has_rich_signals` は立てる）。`source_meta` と Track A Markdown に `Verified Maturity` を露出。

---
