---
name: byrepo
description: contra の Track A Git practical anchors を収集・評価・出力するための named flow。
---

# Byrepo

この文書は contra における **Track A Git practical anchors** の運用定義とする。
会話では `byrepo で回して` または `Track A は byrepo で` の形で呼び出す。

## Purpose

- 研究テーマに近い **実装・制約・失敗パターン** を GitHub repository から拾う
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

1. `keywords.include` を主軸に GitHub repository 検索クエリを組む
2. GitHub Search API で repository 候補を収集する
3. README を取得して、用途・導入手順・制約の匂いを読む
4. issue を少数サンプル取得して、詰まりどころ・運用ノイズを観測する
5. Reliability Score を算出する
6. `GitRepository -> Work` に正規化して Track A の既存分類・生成・出力へ流す

## Output Expectations

- Track A section に practical anchors を出力する
- 最低限、次を含める
  - repository 名
  - stars
  - license
  - issue signal
  - Reliability Score

## Non Goals

- GitHub 全文検索の最適化
- 自動 clone / 自動実行
- 厳密なコード品質監査
- Discussions / PR 全量分析
