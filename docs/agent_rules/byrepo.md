---
name: byrepo
description: contra の Track A Git practical anchors を収集・評価・出力するための named flow。
---

# Byrepo

この文書は contra における **Track A practical anchors** の運用定義とする。
会話では `byrepo で回して` または `Track A は byrepo で` の形で呼び出す。

## Purpose

- 研究テーマに近い **実装・制約・失敗パターン** を repository / model / dataset / research artifact から拾う
- Track B の遠い発想に対して、今すぐ触れる現実の足場を与える
- 論文アンカーではなく、**実務アンカー** を作る

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

## Workflow

1. `keywords.include` を主軸に source type 別検索クエリを組む
2. GitHub Search API と GitLab Projects API で repository 候補を収集する
3. Hugging Face から model / dataset / Space 候補を収集する
4. Zenodo / DataCite から DOI 付きの dataset / software / research artifact 候補を収集する
5. README / card / metadata / issue を取得して、用途・導入手順・制約の匂いを読む
6. source type 別 Reliability Score を算出する
7. DOI / URL / 正規化 title で重複排除し、`Work` に正規化して Track A の既存分類・生成・出力へ流す

## Output Expectations

- Track A section に practical anchors を出力する
- 最低限、次を含める
  - anchor 名
  - source type（GitHub / GitLab / Hugging Face / Zenodo / DataCite）
  - stars / downloads / likes など source type に応じた採用シグナル
  - license
  - issue signal または card / metadata completeness
  - Reliability Score

## Non Goals

- GitHub 全文検索の最適化
- 自動 clone / 自動実行
- 厳密なコード品質監査
- Discussions / PR 全量分析
- Hugging Face model / dataset の自動ダウンロード
- Zenodo / DataCite 添付ファイルの全文解析
