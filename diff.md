# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   llm-evolve（ローカル LLM を改造して測る周回、2026-11-17 開始）が、byserendipity の facet を数学の小分野に向けて「数学の中で領域をまたぐ類推」を探す。どの候補がどの小分野から来たかを呼び手が見て、残す小分野を選べるようにする（F-90）。
*   ホーム除外は Field 単位のまま。Subfield での除外は F-37（2026-09-27）で「残る候補が変わる」として見送っているので、名指すだけにする。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/mcp_server.py`, `tests/test_subfield_ids_line.py`（新規）, `DECISION_LOG.md`, `Changelog.md`, `diff.md`
*   `_subfield_ids_line(works)`: 候補の id を `primary_topic_subfield_name`（括弧に Field）ごとにまとめた 1 行。`_field_ids_line`（F-65）と同じ形。
*   byserendipity の引数 `subfield_line`（boolean・既定 false）。raw 経路で true のとき診断に上の 1 行を足す。予算（`materials_max_chars`）の計算に入る。既定の出力は不変。

---

## 3. 確認方法 (必須)

*   `python -m pytest tests/ -q` → 743 passed（新規 3 件: まとめ方・opt-in のときだけ出て他は同じ・スキーマの既定値）
*   実 OpenAlex: 数学向け facet 3 つ（最適輸送・情報幾何・代数的位相）、`materials_lean`＋45,000。off 38,409 字／on 39,251 字（1 行 842 字）。候補 33 件、Mathematics 28 件が Applied Mathematics 17／Geometry and Topology 5／Mathematical Physics 5 に分かれて見えた。

---

## 4. 既知の課題・リスク (必須)

*   予算が厳しい呼び出しで true にすると、1 行の分だけ抄録の先頭が短くなる（F-65 の 1 行と同じ扱い）。既定 false なので既存の呼び手には影響しない。
*   bybridge・read_works には付けていない（依頼元が使うのは byserendipity raw だけ）。
*   動いている MCP サーバーは `repos/contra` の main を読むので、main へ merge するまで呼び手からは使えない。
