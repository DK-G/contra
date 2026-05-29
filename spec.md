# spec.md

> このファイルはAI向けの開発仕様書。READMEとは別物。  
> 新しいセッション開始時はこのファイルを最初に読み込ませること。

-----

## 1. コンセプト

- **概要**: 研究テーマを入力すると、OpenAlexから論文を収集・分類し、20本レポート（Markdown）を生成するCLIツール。
- **設計思想 / 譲れない核**: 「要約」ではなく「テーマとの関係性の再構成」。Track A（関係グラデーション）とTrack B（接続点フィーチャー）の2軸で、テーマの輪郭と盲点を可視化する。
- **ターゲットユーザー**: 大学院生・若手研究者（テーマ探索・レビュー前段階）
- **現在のフェーズ**: Phase 1 CLI実装中。**ただし実装は旧500本構造のまま**。Track A/B 20本構造への刷新が次の主タスク。

-----

## 2. 技術スタック

| 領域 | 採用技術 | バージョン | 選定理由 |
|---|---|---|---|
| 言語 | Python | 3.10以上推奨 | 標準ライブラリのみで依存を最小化 |
| フレームワーク | なし（CLI） | - | MVPはCLIで十分。Web化はPhase 2 |
| 論文収集API | OpenAlex | v1（REST） | 無料・abstractあり・大規模。APIキー不要 |
| LLM（3行生成） | OpenAI Responses API | gpt-4o-mini デフォルト | Responses APIを使用（Chat Completionsではない） |
| LLM後処理 | GeminiCLI | 外部ツール | `gemini_materials.jsonl` を読み込んで仕上げ |
| 外部ライブラリ | なし（stdlib のみ） | - | `urllib.request` で HTTP 通信。pip不要 |
| ビルド/デプロイ | なし | - | Phase 1はローカルCLI実行のみ |

-----

## 3. アーキテクチャ

### ディレクトリ構成

```
/src
  /core
    input_schema.py   # 入力バリデーション・ThemeInput生成
    models.py         # 全データクラス定義（Work, OutputEntry, OutputDocument等）
    output_spec.py    # 出力Markdown仕様定数
  /openalex
    client.py         # OpenAlex HTTPクライアント（リトライ・ページング）
    parser.py         # APIレスポンス → Work への正規化
  /pipeline
    collect.py        # Collector: テーマ→クエリ生成→ページング収集
    filter.py         # abstractあり優先フィルタ・件数制限
    classify.py       # classify_stub: キーワードスコアで分類（現在スタブ）
    generate.py       # 3行生成（simple/structured/llm の3モード）
    export.py         # OutputDocument → Markdownファイル書き出し
  /cli
    main.py           # CLIエントリポイント（argparse）
  openai_client.py    # OpenAI Responses API薄いラッパー

/data                 # 入力JSONサンプル（theme.json等）
/output               # 生成結果（run_*/brainstorm_output.md, gemini_materials.jsonl）
/scripts              # 実行スクリプト（run_cli.ps1等）
/docs                 # 仕様メモ（input_min_spec.md, output_markdown_spec.md等）
```

### データの流れ

```
入力JSON (data/theme.json)
  ↓ validate_and_normalize()         # ThemeInput に変換・バリデーション
  ↓ collect_and_filter()             # OpenAlex APIからWork一覧を収集
  ↓ classify_stub()                  # キーワードスコアで分類（スタブ）
  ↓ generate_entries()               # 3行構成生成（simple/structured/llmモード）
  ↓ export_markdown()                # brainstorm_output.md を書き出し
  ↓ _write_gemini_materials()        # gemini_materials.jsonl を書き出し
                                      ↓ GeminiCLI（外部）で後処理
```

**生成モード切り替え（--gen-mode）**
- `simple`: キーワード一致スコア、abstract切り詰め（テスト用）
- `structured`: テーマとの構造的関係・前提チェックをルールベースで生成
- `llm` / `plan_b`: OpenAI Responses APIで3行生成（`--llm-max-items` 件まで）

-----

## 4. 制約・禁止事項 ★最重要

- **編集禁止のファイル / ディレクトリ**: `output/` 配下の生成済みファイル（上書き不可）、`data/` 配下のサンプル入力JSON
- **追加禁止の依存・ライブラリ**: 外部ライブラリ（pip install）は原則追加しない。必要な場合は必ず確認する。stdlibのみで実装する方針。
- **セキュリティ上の禁則**: `OPENAI_API_KEY` をコードやファイルに直書きしない（環境変数から読む）。APIキー・メールアドレスをoutputやgitにコミットしない。
- **勝手にやってほしくないこと**:
  - `src/core/models.py` のデータクラス構造の変更（下流への影響が大きい）
  - `classify_stub` をスタブから本実装に勝手に変更する（仕様確定前）
  - フォルダ構成の変更
  - `plan_a` モードの復活（廃止済み。`structured` モードに統合）
- **変更前に必ず確認すること**:
  - Track A/B の選出ロジック・比率（枚数・接続点タイプの種類）
  - OpenAlex クエリ生成ルールの変更
  - 出力Markdownのセクション構成変更

-----

## 5. 命名・コーディング規約

- **命名規則**: snake_case（Python標準）。クラスはPascalCase。
- **フォーマッタ / Linter**: 未設定。インデント4スペース。
- **コメント方針**: モジュール冒頭に1行docstring。関数コメントは原則なし。非自明な箇所のみインラインコメント。
- **言語**: コード内コメント・変数名は英語。UIメッセージ・出力Markdownは日本語。

-----

## 6. 既知の落とし穴

- **`classify_stub` はスタブ**: キーワードスコアによる単純分類で、Track B（接続点フィーチャー）の概念は未実装。semantic classificationも未実装。
- **CLI本体が旧500本構造のまま**: `main.py` の `_build_document` / `_write_gemini_materials` は `related(100)/broad(200)/unrelated(200)` の4章構造を前提としている。Track A/B 20本形式への移行が必要。
- **OpenAI Responses API を使用**: Chat Completions APIではない。`/v1/responses` エンドポイント。`extract_output_text()` でレスポンスを取り出す。
- **`llm_max_items` のデフォルトが20**: LLMモードでも先頭20件しかLLM生成されない。残りは `structured` にフォールバックする。
- **`--mailto` がないとOpenAlexの速度制限が厳しい**: politepool対象外になるので本番実行時は指定推奨。

-----

## 7. 決定ログ

- `2026-02-xx` OpenAI Responses APIを採用（Chat Completionsではない）。既存実装に合わせる。
- `2026-02-xx` Plan A/B 並立を廃止。Plan B（LLM生成）＋ GeminiCLI後処理の二段階に一本化。`plan_a` CLIオプションは `structured` のエイリアスとして残存するが実質廃止。
- `2026-05-28` 500本収集→20本レポート形式（Track A/B）に方針変更。Track A：関係グラデーション10本（関係軸ラベル付き）、Track B：接続点フィーチャー10本（接続点タイプ別ラベル付き）。却下した案：500本のまま品質を上げる→ユーザーが消費できる量を超えていた。
- `2026-05-29` Track A/B の詳細仕様を確定（Step 1完了）:
  - 関係度表現: 5段階ラベル（高/中高/中/中低/低）を採用。数値は却下（LLMによる偽精度を避ける）。
  - 関係軸ラベル: LLMがテーマから広めの候補リストを生成し、各論文に最適なラベルを割り当てる方式を採用。固定語彙は却下（テーマごとに最適化され、複数回利用で多角的な視座が蓄積される設計）。
  - Track AとTrack Bは同じ候補プールを共有する。Track Aが上位10本を選出後、残りからTrack Bが「1点だけ関係ある」論文をLLMが発見する。
  - Track B 補充ルール: 単一接続点のある論文が足りなければランダムで補充。接続点タイプの固定リストは設けない（LLMが発見した接続点をラベル化する）。
  - classify実装方針: Track A はキーワードスコアリングで候補を絞り込み、LLMが関係軸ラベルを割り当て。Track B はLLMが残り候補から「1点だけ関係ある」論文を識別。ハイブリッド方式を採用。

-----

## 8. 未解決 / TODO（仕様レベル）

- GeminiCLIへの入力フォーマットをTrack A/B構造に合わせた更新（現在は旧4章構造）
- Track A の関係軸候補リスト生成プロンプトの設計（何語程度生成させるか、テーマの何を見て生成するか）
- Phase 1 の「Done」判断基準：Track A/B 20本レポートで複数テーマ安定出力が条件
