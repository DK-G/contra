# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   A-RS2 続編: Pillar 1 の配点移行を完了する。先手（時間系=CI/リリース）に続き、生成で水増しできないもう一方のシグナル class「他人」（外部コントリビュータ / owner 以外の issue 起票者）を導入する。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/pipeline/git_collect.py`, `src/core/models.py`, `src/core/output_spec.py`, `tests/test_git_collect.py`, `DECISION_LOG.md`, `roadmap.md`, `task.md`, `diff.md`, `Changelog.md`
*   `_third_party_score`（最大6点）= 外部コントリビュータ数（`/contributors`、owner 除く、最大3）＋非 owner issue 起票者数（issues サンプル再利用・追加 REST ゼロ、最大3）を新設。
*   Pillar 1（最大30据え置き）の rich モードを README 系 0.4 倍（completeness 8 / code 4）＋verified maturity 12 ＋third_party 6 へ再配分。非 rich は従来どおり。
*   `owner_login` を保持し `_fetch_issue_signal` を 5-tuple 化（非 owner 起票者を計上）。

---

## 3. 確認方法 (必須)

*   `python3 -m pytest tests/ -q` → 110 passed
*   `tests/test_git_collect.py::test_third_party_score_tiers` / `test_collect_counts_external_people_signals`（owner 除外カウント＋露出）

---

## 4. 既知の課題・リスク (必須)

*   **dependents（下流利用）は GitHub に公式 REST API がない**（HTML の dependents graph のみ）ため対象外。将来 GraphQL/別経路を要検討。
*   外部コントリビュータ取得で repo あたり REST が更に1増（合計 約3増/repo）。トークン前提は不変（無認証は従来スコアにフォールバック）。
*   トークン在席時は README のみ強い repo が更に相対降格する（A-RS2 の狙い通り）。Pillar 配点全体の再較正は roadmap #10 の人間品質評価とあわせて実施予定。

---

## 5. 変更内容の詳細 (任意)

*   `_third_party_score`: 外部コントリビュータ（≥1/≥3/≥8 で各+1）＋非 owner 起票者（≥1/≥3/≥5 で各+1）、最大6。スキャフォールドで生成不能な「第三者の実関与」を採点。
*   `_fetch_contributor_signal`: `/contributors?anon=false` から owner 以外の login 数を数える。`_attach_rich_signals` に追加（graceful degrade）。
*   非 owner 起票者は先手で取得済みの issues ペイロードを再利用（`_fetch_issue_signal` 内で `user.login != owner_login` の distinct を計上）。

---
