# DECISION LOG

contra の重要な設計判断を記録する。新しいエントリを先頭に追記する。

---

## 2026-06-01 — Track B 生成3部の hollow 対策：転用読みの定石に基づく多段プロンプト化

**決定**: Track B の4部生成のうち②関連性・③仮説・④注意点を、「遠い論文を自テーマへ転用する読み」の確立手順（構造写像/LBD/bisociation/概念ブレンディング/知識ブローカリング/Reading-for-Relevance/情報採餌に共通の4ムーブ）に沿って**多段構造化**し、各部に**FORBIDリスト**を明記する。summary は実Abstract援用で充足済みのため変更しない。

**根拠**: bynote 調査（NotebookLM Deep Research 68ソース、ノート `85d1cd32`、一次資料 `docs/research/reading_for_transfer.md`）。A-1 品質評価で観測した hollow 症状（②カテゴリ言い換え/③"可能性がある"bloat/④定型caution）が、先行研究が明示的に禁止する失敗型と一致した。

**処方**:
1. 生成プロンプト: object-mapping → Shared Relational Structure 明示 → 変数付き candidate-inference 仮説 → 破断点 caution。各部に禁止例を明記。
2. judge ルーブリック（Structural Depth / Applicability / Constraint Adherence 各0-10）でカテゴリ一致を hollow 棄却（次段で校正）。
3. summary は不変。

**トレードオフ / 却下**: 質ゲートを厳しくすると飽和（0件）が増えるが、ユーザー方針「論文選定は重視しない・同一論文の再ピック禁止が効けば周回でカバー」と整合するため許容。プロンプトを勘で調整する案は却下し、定石調査を先行させた。

**可逆性**: プロンプト変更のみ。選別ロジック・データ構造は不変。

**関連**: A-1 評価でのロバストネス修正（commit `28bbecc`）・Abstract truncation 修正（commit `0264d04`）。
