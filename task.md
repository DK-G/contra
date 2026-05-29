# 作業タスクリスト

`roadmap.md`からブレークダウンした、具体的な作業タスクを管理します。

---

## 作業中 (In Progress)

*   なし

---

## 未着手 (To Do)

### Step 1: 仕様確定（実装前に決める）
*   Track A の関係度表現を決定：5段階ラベル（高/中高/中/中低/低）vs 数値（1-10）
*   Track A の関係軸ラベルを決定：LLM自由生成 vs 固定語彙リストから選択
*   Track B の接続点タイプ8種を確定し、論文が見つからない場合の補充ルールを決める
*   `classify_stub` の本実装方針を決定：LLMベース vs キーワード+ルールベース

### Step 2: データモデル更新（`src/core/`）
*   `models.py` に `track`（A/B）・`label`（関係軸 or 接続点）フィールドを追加
*   `OutputSection` をTrack A/B対応の構造に更新

### Step 3: 分類ロジック実装（`src/pipeline/classify.py`）
*   Track A 選出：関係度スコアリング → 上位10本、スコアに応じた関係軸ラベルを付与
*   Track B 選出：接続点タイプ別に1本ずつ（合計10本）選出するロジック実装
*   `classify_stub` を上記本実装に置き換え

### Step 4: 生成ロジック更新（`src/pipeline/generate.py`）
*   Track A 用：関係軸ラベルを含む関係性文の生成（`--gen-mode llm` 対応）
*   Track B 用：接続点ラベル `【接続点: 〇〇だけ関係ある】` を含む関係性文の生成

### Step 5: 出力整形更新（`src/pipeline/export.py`）
*   レポートヘッダー（テーマ概要・仮説サマリー）の出力を追加
*   Track A セクション（関係度順10本）・Track B セクション（接続点ラベル付き10本）の構成に変更

### Step 6: CLI本体更新（`src/cli/main.py`）
*   `_build_document()` を Track A/B 20本構造に書き換え（旧100/200/200構造を廃止）
*   `_write_gemini_materials()` の出力フォーマットをTrack A/B対応に更新

### Step 7: サンプル生成・品質評価
*   新構造で複数テーマのレポートを生成
*   Track A「関係軸ラベルが的確か」・Track B「接続点が意外で納得感があるか」を評価軸にレビュー

### Step 8: GeminiCLI後処理フロー整備
*   GeminiCLIで3行（関係性/要約/注意点）を更新する後処理フロー設計
*   Track A/B形式の `gemini_materials.jsonl` を入力とした実行手順を整備

---

## 完了 (Done)

### インフラ（再利用可能・変更不要）
*   入力仕様の最小セットを確定（`docs/input_min_spec.md`）
*   入力→内部表現のスキーマ定義（`src/core/input_schema.py`, `src/core/models.py`）
*   OpenAlex APIクライアント実装（`src/openalex/client.py`, `parser.py`）
*   OpenAlex検索クエリ設計・拡張（include/exclude/field/goalの重み付け）
*   OpenAlexページング・リトライ・重複排除・フィールド欠損ポリシー確定
*   収集パイプライン実装（`src/pipeline/collect.py`, `filter.py`）
*   abstractあり優先のフィルタ実装
*   3行構成テンプレートの生成ルール定義・実装（simple/structured/llmモード）
*   CLIエントリポイント雛形作成（`src/cli/main.py`）
*   収集→分類→生成→出力のE2E接続・動作確認

### 方針・設計
*   Plan A/B並立を廃止し、Plan B（LLM）＋GeminiCLI後処理の方針に一本化
*   500本収集→20本レポート形式（Track A/B構成）に方針変更
*   `plan.md`, `roadmap.md` を新方針に更新
*   `spec.md`（AI向け開発仕様書）を新規作成
