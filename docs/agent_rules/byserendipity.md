---
name: byserendipity
description: contra の Track B を使って遠いが構造的に接続する論文を選別・生成する named flow。
---

# Byserendipity

この文書は contra における **Track B contrarian / serendipity flow** の運用定義とする。
会話では `byserendipity で回して` または `Track B は byserendipity で` の形で呼び出す。

## Purpose

- 一見無関係だが構造的に接続しうる遠い論文を見つける
- 近接や anomaly を避け、**遠いが効く発想** を抽出する
- contra の中核である Track B を独立フローとして明示する

## Invocation

次のような明示依頼を受けたらこの flow を優先する。

- `byserendipity`
- `byserendipity で回して`
- `Track B は byserendipity で`
- `遠い接続だけ見たい`
- `contrarian 側を回して`
- `構造類推の方で進めて`

## Inputs

- `ThemeInput`
- `goal`
- `assumptions`
- `concern`
- `track_b_count`
- `serendipity_gate`
- `output_floor`

## Workflow

1. テーマから abstract relational structure を推定する
2. LLM で distant-domain query 群を生成する
3. OpenAlex から Track B 候補を収集する
4. 必要に応じて citation 2-hop を加える
5. `purpose_sim × mechanism_dist` で選別する
6. hollow gate / output floor / saturation 判定を通す
7. 4部構成（概要 / 関連性 / 仮説 / 注意点）を生成する

## Output Expectations

- Track B section に次を含める
  - 接続点ラベル
  - serendipity score
  - distance / structure score
  - 4部構成

## Non Goals

- 近接論文の網羅
- 実装のしやすさ評価
- GitHub repository の実用性評価
