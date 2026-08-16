# Contra

研究テーマを入力すると、OpenAlexから論文を収集・選別し、「一見無関係だが構造的に接続しうる遠い論文」を4部構成のMarkdownで提示するツール。CLI と MCP サーバーの両方から利用できる。

**contra = contrarian**。思考の狭窄（マイオピア）に抗い、テーマに遠いが関係構造が一致する論文を対置することで、視座を広げる。

## 特徴

- **Track B 中核**: ドメインは遠いが Purpose/Mechanism 構造が一致する論文（Gentner の Analogy）を選出
- **Track A Git practical anchors**: GitHub repository から実装・制約・失敗パターンを収集し、4本柱 Reliability Score で評価
- **質ゲート方式**: 本数は固定でなく、質スコア閾値を超えた候補だけを出力（`serendipity = purpose_sim × mechanism_dist`）
- **citation 2-hop (bridge) 収集**: 近傍シードの共有引用文献を経由してホームドメイン外の交差論文を収集
- **OA全文補強（provider層・opt-in）**: abstract が薄い OA 候補について、差し替え可能な provider chain（arXiv→Europe PMC→IA Scholar→CORE→oa_url PDF）で全文要点を取得し mechanism 判定の入力を強化（スコア式・閾値は不変）
- **Anomaly/マイオピア棄却**: 無意味接続・近接を両方弾く
- **4部構成出力**: 概要 / テーマとの関連性 / 役に立つ可能性の仮説（中核）/ 注意点
- **テーマ別履歴管理**: 採用論文IDを記録し、次回実行時の重複を回避
- **テーマ飽和検知（M3）**: 良候補がゼロのとき弱い論文で水増しせず「飽和ノート」を出力

## by シリーズ（named flows / MCP ツール）

各フローの運用定義は [`docs/agent_rules/`](docs/agent_rules/) が正本。MCP サーバー経由で AI エージェントから直接呼び出せる。

| フロー | MCP ツール | 内容 |
|---|---|---|
| `byserendipity` | `byserendipity_discover` | Track B: LLM クエリで遠ドメイン論文を収集し、構造類推で選別 |
| `byrepo` | `byrepo_search` | Track A: GitHub repository + Hugging Face Hub の model/dataset を収集し Reliability Score で評価 |
| `bybridge` | `bybridge_collect` | citation 2-hop: 共有引用文献(bridge)経由でホームドメイン外の交差論文を収集（`raw_only=true` なら LLM キー不要） |
| `bynote` | `bynote_link_concepts` | メモを Purpose/Mechanism に分解し、類推ドメインと Serendipity Bridge の問いを提示 |

## 必要環境

- Python 3.10+
- 環境変数 `OPENAI_API_KEY` または `ANTHROPIC_API_KEY`（選別・生成に使用。`--llm-model` / `llm_model` でプロバイダごとゼロコード切替）
- OpenAlex API（APIキー不要）
- `GITHUB_TOKEN`（任意。byrepo の GitHub Search レート制限が 10→30 req/min に緩和）
- `CORE_API_KEY`（任意。`--fulltext` 使用時に CORE provider を有効化。未設定なら CORE はスキップ）

## 使い方

### CLI

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
| `--track-a-pool-size` | Track A 収集源ごとの探索プール件数（`--track-a-count` とは独立。0=自動で `max(count*2, 10)`） | 0（自動） |
| `--gen-mode` | 生成モード（llm / structured / simple） | llm |
| `--llm-model` | 選別・生成に使うモデル（OpenAI / Claude 切替） | gpt-4o-mini |
| `--no-history` | 履歴除外をスキップ | off |
| `--score-votes` | 自己一貫性投票数（1=単発、3=安定重視） | 1 |
| `--serendipity-gate` | Track B 絶対下限スコア | 0.25 |
| `--output-floor` | 出力品質フロア（これ未満は飽和扱い） | 0.35 |
| `--fulltext` | OA全文補強を有効化（OA かつ abstract が短い Track B 候補のみ取得） | off |
| `--fulltext-cache-dir` | 全文キャッシュ（論文ID単位・git追跡外。hit/miss とも記録し再取得しない） | data/fulltext |
| `--fulltext-max-abstract` | この文字数未満の abstract を持つ OA 候補だけ全文取得（無駄打ち防止） | 280 |
| `--mcp` | stdio MCP サーバーとして起動 | off |

### MCP サーバー

`--mcp` で stdio MCP サーバーとして起動し、上記4ツールを公開する。起動ラッパーは [`scripts/run_mcp.cmd`](scripts/run_mcp.cmd)（repo ルートへ cd してから起動する）。

Claude Code への登録例（user スコープ＝全プロジェクトから利用可）:

```bash
claude mcp add --scope user contra -- cmd /c D:\dev\repos\contra\scripts\run_mcp.cmd
```

入力バリデーションに注意: `theme_overview` は 200–1200 字、`assumptions` は 2–5 項目、`scope_time_range` は `last_10_years` / `no_limit`。

## ディレクトリ構成

```
src/
  core/          データモデル・入力バリデーション・出力Markdown仕様
  openalex/      OpenAlex HTTPクライアント・レスポンスパーサー
  github/        GitHub Search クライアント（Track A / byrepo）
  fulltext/      OA全文 provider 層（arXiv / Europe PMC / IA Scholar / CORE / oa_url PDF・chain・キャッシュ）
  pipeline/      収集 / 選別 / 生成 / エクスポート / 履歴 / 距離計算
  cli/           CLI エントリポイント (main.py)
  mcp_server.py  by シリーズ stdio MCP サーバー
data/
  samples/       テーマ入力サンプル JSON
  history/       テーマ別採用論文履歴（実行後に生成、git 追跡対象外）
  fulltext/      OA全文キャッシュ（`--fulltext` 実行後に生成、git 追跡対象外）
output/          生成結果（実行後に生成、git 追跡対象外）
scripts/         検証・プローブスクリプト・MCP起動ラッパー
docs/
  agent_rules/   by シリーズ named flow の運用定義（正本）
tests/           ユニットテスト
```

## 仕様書

- [`plan.md`](plan.md) — マスター仕様書（目的・設計原則・パイプライン設計・出力仕様）
- [`spec.md`](spec.md) — AI向け開発仕様書（技術スタック・決定ログ・禁則事項）
- [`roadmap.md`](roadmap.md) — 開発ロードマップ・残作業

## 開発状況

Phase 2 完了・MCP 化済み（`main` ブランチ）。

主要実装済み:
- Track B 選別: SOLVENT Purpose-Mechanism 構造類推スコアリング（`select_track_b`）
- Track A: GitHub + Hugging Face Hub 収集・統合ランキング（byrepo）
- citation 2-hop 収集（bybridge）・MAX-MIN 多様化
- hollow gate（Structural Depth judge）・percentile gate・output floor
- 4部構成生成・数値捏造ガード
- テーマ飽和検知（M3）・自己一貫性投票（R5）
- stdio MCP サーバー（by シリーズ4ツール）
- OpenAI / Anthropic 両プロバイダ対応（`--llm-model` で切替）
- OA全文 provider 層（arXiv→Europe PMC→IA Scholar→CORE→oa_url PDF の chain・論文ID単位キャッシュ・`--fulltext` で opt-in。mechanism 判定の入力補強でスコア核は不変）
