# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   A-RS1/A-RS2 で導入した Pillar スコア（時間系・他人系）を Track A 出力で読み手が解釈できるよう、score 内訳表示を改善する。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/core/output_spec.py`, `tests/test_export_render.py`, `task.md`, `diff.md`, `Changelog.md`
*   Reliability Score 行に total `/100` と各 Pillar の max（Impl/Doc /30・LMA /25・Comm /20・Sec /25）を表示。
*   スコアリングモードタグ（`[rich: time+people]` / `[README-only]`）を追加。Verified Maturity（/12）・Third-Party Signal（/6）も max 付き表示に統一。

---

## 3. 確認方法 (必須)

*   `python3 -m pytest tests/ -q` → 111 passed
*   `tests/test_export_render.py::test_render_track_a_github_entry_with_rich_breakdown`（rich 内訳の max・モードタグ）

---

## 4. 既知の課題・リスク (必須)

*   discussion 観測は GitHub Discussions に REST 一覧エンドポイントが無く GraphQL 専用（dependents 同様）のため保留。
*   roadmap #10（複数テーマでの人間品質評価）は実 LLM API 認証情報＋人間判断が必要で、本セッション（無認証・自律）では未実施。

---

## 5. 変更内容の詳細 (任意)

*   スコアリングモードタグは `has_rich_signals` で分岐。rich モードは Pillar 1 の README 配点を時間・他人系へ移譲しているため、2 つの repo のスコアは**同一モード内でのみ比較可能**であることを明示する意図。
*   sub-score（Impl/Doc・LMA・Comm・Sec）が source_meta に無い旧データでは従来どおり total のみ＋モードタグを表示（後方互換）。

---
