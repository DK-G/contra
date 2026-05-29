# 作業タスクリスト

`roadmap.md`からブレークダウンした、具体的な作業タスクを管理します。

---

## 作業中 (In Progress)

*   なし

---

## 未着手 (To Do)

### Step 2: データモデル更新（`src/core/`）
*   `models.py` に `track`（A/B）・`label`（関係軸 or 接続点）フィールドを追加
*   `OutputSection` をTrack A/B対応の構造に更新
*   履歴管理用の `ThemeHistory` データクラスを追加（theme_hash, used_ids, generated_at）

### Step 3: 収集ロジック更新（`src/pipeline/collect.py` 他）
*   Track B 用別ドメインクエリのLLM生成プロンプト設計・実装
*   Track B 専用の収集フロー実装（別クエリでOpenAlexを叩く）
*   履歴除外ロジック実装：収集候補から既使用IDをフィルタリング
*   履歴の読み込み・書き込みユーティリティ実装（`data/history/{theme_hash}.json`）

### Step 4: 分類ロジック実装（`src/pipeline/classify.py`）
*   Track A 選出：キーワードスコアリング → 上位10本
*   Track A ラベル付与：LLMがテーマから関係軸候補リストを生成し、各論文に割り当て
*   Track B 選出：LLMが別ドメイン収集結果から「1点だけ接続」論文を識別・ラベル化
*   `classify_stub` を上記本実装に置き換え

### Step 5: 生成ロジック更新（`src/pipeline/generate.py`）
*   Track A 用：関係軸ラベル付きの関係性文生成（`--gen-mode llm` 対応）
*   Track B 用：接続点ラベル `【接続点: 〇〇だけ関係ある】` 付きの関係性文生成

### Step 5: 出力整形更新（`src/pipeline/export.py`）
*   レポートヘッダー（テーマ概要・仮説サマリー）の出力を追加
*   Track A セクション（関係度順10本）・Track B セクション（接続点ラベル付き10本）の構成に変更

### Step 6: CLI本体更新（`src/cli/main.py`）
*   `_build_document()` を Track A/B 20本構造に書き換え（旧100/200/200構造を廃止）
*   `_write_gemini_materials()` の出力フォーマットをTrack A/B対応に更新
*   実行後に採用論文IDを履歴ファイルへ追記する処理を追加

### Step 7: サンプル生成・品質評価
*   新構造で複数テーマのレポートを生成
*   Track A「関係軸ラベルが的確か」・Track B「接続点が意外で納得感があるか」を評価軸にレビュー
*   同テーマを2回実行し、重複論文が除外されていることを確認

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
