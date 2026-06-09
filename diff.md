# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   Track A と Track B の回し方を named flow として独立定義し、`bynote` のように呼び出し名で扱えるようにする。

---

## 2. 変更概要 (必須)

*   変更ファイル: `docs/agent_rules/byrepo.md`, `docs/agent_rules/byserendipity.md`, `AGENT_COORDINATION.md`, `task.md`, `diff.md`, `Changelog.md`
*   Track A 用 `byrepo` と Track B 用 `byserendipity` を追加し、named flow 一覧へ登録した。

---

## 3. 確認方法 (必須)

*   `Get-Content -Raw docs/agent_rules/byrepo.md`
*   `Get-Content -Raw docs/agent_rules/byserendipity.md`
*   `Get-Content -Raw AGENT_COORDINATION.md`

---

## 4. 既知の課題・リスク (必須)

*   現時点では named flow の定義追加であり、自動ディスパッチ機構そのものは実装していない。

---

## 5. 変更内容の詳細 (任意)

*   `byrepo` は Track A practical anchors、`byserendipity` は Track B contrarian flow の役割を明示的に分離している。

---
