# Contra

研究テーマを入力すると、OpenAlexから論文を収集・選別し、「一見無関係だが構造的に接続しうる遠い論文」を4部構成のMarkdownで提示するCLIツール。

**contra = contrarian**。思考の狭窄（マイオピア）に抗い、テーマに遠いが関係構造が一致する論文を対置することで、視座を広げる。

## 特徴

- **Track B 中核**: ドメインは遠いが Purpose/Mechanism 構造が一致する論文（Gentner の Analogy）を選出
- **質ゲート方式**: 本数は固定でなく、質スコア閾値を超えた候補だけを出力（`serendipity = purpose_sim × mechanism_dist`）
- **Anomaly/マイオピア棄却**: 無意味接続・近接を両方弾く
- **4部構成出力**: 概要 / テーマとの関連性 / 役に立つ可能性の仮説（中核）/ 注意点
- **テーマ別履歴管理**: 採用論文IDを記録し、次回実行時の重複を回避
- **テーマ飽和検知（M3）**: 良候補がゼロのとき弱い論文で水増しせず「飽和ノート」を出力

## 必要環境

- Python 3.10+
- 環境変数 `OPENAI_API_KEY`（選別・生成に使用）
- OpenAlex API（APIキー不要）

## 使い方

```bash
python -m src.cli.main \
  --input data/samples/theme.json \
  --out output/my_run \
  --gen-mode llm
```

主要オプション:

| オプション | 説明 | デフォルト |
|---|---|---|
| `--input` | テーマ入力 JSON | 必須 |
| `--out` | 出力ディレクトリ | 必須 |
| `--single` | MVP モード: Track B 最良1本のみ | off |
| `--track-b-count` | Track B 最大本数（上限。質ゲートで減る） | 10 |
| `--track-a-count` | Track A アンカー本数（0=省略） | 0 |
| `--gen-mode` | 生成モード（llm / structured / simple） | llm |
| `--no-history` | 履歴除外をスキップ | off |
| `--score-votes` | 自己一貫性投票数（1=単発、3=安定重視） | 1 |
| `--serendipity-gate` | Track B 絶対下限スコア | 0.25 |
| `--output-floor` | 出力品質フロア（これ未満は飽和扱い） | 0.35 |

## ディレクトリ構成

```
src/
  core/          データモデル・入力バリデーション・出力Markdown仕様
  openalex/      OpenAlex HTTPクライアント・レスポンスパーサー
  pipeline/      収集 / 選別 / 生成 / エクスポート / 履歴 / 距離計算
  cli/           CLI エントリポイント (main.py)
data/
  samples/       テーマ入力サンプル JSON
  history/       テーマ別採用論文履歴（実行後に生成、git 追跡対象外）
output/          生成結果（実行後に生成、git 追跡対象外）
scripts/         検証・プローブスクリプト
docs/            仕様メモ・調査資料
tests/           ユニットテスト
```

## 仕様書

- [`plan.md`](plan.md) — マスター仕様書（目的・設計原則・パイプライン設計・出力仕様）
- [`spec.md`](spec.md) — AI向け開発仕様書（技術スタック・決定ログ・禁則事項）
- [`roadmap.md`](roadmap.md) — 開発ロードマップ・残作業

## 開発状況

Phase 1 CLI 実装中（`main` ブランチ）。

主要実装済み:
- Track B 選別: SOLVENT Purpose-Mechanism 構造類推スコアリング（`select_track_b`）
- citation 2-hop 収集・MAX-MIN 多様化
- hollow gate（Structural Depth judge）・percentile gate・output floor
- 4部構成生成・数値捏造ガード
- テーマ飽和検知（M3）・自己一貫性投票（R5）
