---
name: byrepo
description: contra の Track A Git practical anchors を収集・評価・出力するための named flow。
---

# Byrepo

この文書は contra における **Track A Git practical anchors** の運用定義とする。
会話では `byrepo で回して` または `Track A は byrepo で` の形で呼び出す。

## Purpose

- 研究テーマに近い **実装・制約・失敗パターン** を収集源から拾う
- Track B の遠い発想に対して、今すぐ触れる現実の足場を与える
- 論文アンカーではなく、**実務アンカー** を作る

## Sources

実務アンカーの収集源は差し替え可能で、既定では次の 3 つを併用する（`src/pipeline/track_a.py` が統合）。

- `github` — GitHub repository（実装・ツール・フレームワーク）
- `huggingface` — Hugging Face Hub の **model / dataset**（学習済みモデル・データセット）
- `kaggle` — Kaggle の **dataset / notebook（kernel）**（実世界データ・実行可能な EDA/ベースライン・失敗パターン）

各収集源は同一の `Work` に正規化され、`source_meta["reliability_score"]`（0-100）で統合ランキングする。片方の収集源が落ちても他方のアンカーは返す（障害分離）。`sources` で対象を絞れる（例: `["huggingface"]`）。

Kaggle は公開データの読み取りでも API 資格情報（環境変数 `KAGGLE_USERNAME` / `KAGGLE_KEY`、または `~/.kaggle/kaggle.json`）が必須。**資格情報が未設定なら Kaggle 収集は静かにスキップ**し（エラーにせず 0 件）、他収集源のアンカーはそのまま返す。

## Invocation

次のような明示依頼を受けたらこの flow を優先する。

- `byrepo`
- `byrepo で回して`
- `Track A は byrepo で`
- `Git practical anchors を出して`
- `Git版の Track A で進めて`
- `実装アンカーを集めて`

## Inputs

- `ThemeInput`
- `keywords.include`
- `keywords.exclude`
- 必要なら `track_a_count`
- 必要なら `sources`（既定 `["github", "huggingface", "kaggle"]`）

## Workflow

1. `keywords.include` を主軸に各収集源の検索クエリを組む
2. 収集源から候補を収集する
   - GitHub: Search API で repository を集め、README / issue を読む
   - Hugging Face: Hub API で model / dataset を集め、card(README) を読む
   - Kaggle: API で dataset / notebook(kernel) を集める（資格情報が無ければスキップ）
3. 収集源ごとの Reliability Score を算出する（GitHub=4 Pillar / HF=adoption・activity・license・theme-fit / Kaggle=adoption[votes・downloads・medal・usability]・activity・license/language・theme-fit）
4. `Work` に正規化し、`source_meta["reliability_score"]` で統合ランキングして Track A の既存分類・生成・出力へ流す

## Output Expectations

- Track A section に practical anchors を出力する
- 最低限、次を含める
  - 名称（GitHub=repository 名 / HF=model・dataset id / Kaggle=dataset・notebook の ref）
  - 採用度シグナル（GitHub=stars / HF=downloads・likes / Kaggle=votes・downloads・medal）
  - license
  - GitHub のときは issue signal
  - Reliability Score

## Non Goals

- GitHub 全文検索の最適化
- 自動 clone / 自動実行
- 厳密なコード品質監査
- Discussions / PR 全量分析
