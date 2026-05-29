# spec.md

> このファイルはAI向けの開発仕様書。READMEとは別物。  
> 新しいセッション開始時はこのファイルを最初に読み込ませること。

-----

## 1. コンセプト

- **概要**: 研究テーマを入力すると、OpenAlexから論文を収集・**選別**し、「一見無関係だが構造的に接続しうる遠い論文」を4部構成のMarkdownで提示するCLIツール（**contra = contrarian**）。
- **設計思想 / 譲れない核**: 「要約」ではなく「テーマとの関係性の再構成」。中核は **Track B（遠い接続）**。狙うのは「分野は遠いが関係構造が一致する」論文（Gentnerの Analogy）であり、無意味接続（Anomaly）と近接（マイオピア）は両方棄却する。理論的基盤は [`docs/research/serendipity_conditions.md`](docs/research/serendipity_conditions.md)、全体仕様は [`plan.md`](plan.md)。
- **ターゲットユーザー**: 第一に**作者自身**（発想拡張ツール）。将来的に大学院生・若手研究者。
- **現在のフェーズ**: Phase 1 CLI実装中。**MVP = Track B のセレンディピティ・ユニット「1本」を出力すること**。本数は質ゲートの閾値超え数（固定本数ではない）。旧500本構造・旧20本固定構造からの刷新が主タスク。

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
  ↓ collect (collect.py)             # 別ドメイン概念 × テーマ核心語 でOpenAlex収集／撤回論文除外
  ↓ select  (classify.py)            # 距離スコア(意外性) × 構造スコア(有用性) を乗算、両端棄却。Anomaly強制棄却
  ↓ generate (generate.py)           # 4部構成生成（概要/関連性/役に立つ可能性の仮説/注意点）
  ↓ export_markdown()                # 出力Markdownを書き出し（質ゲート通過分）
  ↓ _write_gemini_materials()        # gemini_materials.jsonl を書き出し
                                      ↓ GeminiCLI（外部）で後処理
```

3段階（収集／選別／提示）の各段に効くセレンディピティ知見の対応は [`plan.md`](plan.md) §6 と [`docs/research/serendipity_conditions.md`](docs/research/serendipity_conditions.md) §7 を参照。

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
  - 選別の乗算スコア設計（距離スコア × 構造スコア）の重み・閾値の変更
  - Track B の選出ロジック、質ゲートの閾値（出力本数を左右する）
  - OpenAlex クエリ生成ルール（別ドメイン概念 × テーマ核心語の掛け合わせ方）の変更
  - 4部構成フォーマット・出力Markdownのセクション構成変更

-----

## 5. 命名・コーディング規約

- **命名規則**: snake_case（Python標準）。クラスはPascalCase。
- **フォーマッタ / Linter**: 未設定。インデント4スペース。
- **コメント方針**: モジュール冒頭に1行docstring。関数コメントは原則なし。非自明な箇所のみインラインコメント。
- **言語**: コード内コメント・変数名は英語。UIメッセージ・出力Markdownは日本語。

-----

## 6. 既知の落とし穴

- **選別の乗算スコアが未実装**: 現状の `classify.py` はキーワードスコア＋ドメインペナルティ止まり。距離スコア(意外性) × 構造スコア(有用性) の乗算と、Anomaly（属性も関係も無一致）の強制棄却・質ゲートは未実装。
- **生成が3行構成のまま**: `generate.py` は関係性/要約/注意点の3行。4部構成（概要/関連性/**役に立つ可能性の仮説**/注意点）への移行が必要。「役に立つ可能性の仮説」が中核フィールド。
- **本数が固定（10/10）のまま**: `main.py` は Track A/B 各10本固定。質ゲート閾値超え数を出力する方式への移行が必要。MVP は Track B 最上位1本。
- **OpenAI Responses API を使用**: Chat Completions APIではない。`/v1/responses` エンドポイント。`extract_output_text()` でレスポンスを取り出す。
- **`llm_max_items` のデフォルトが20**: LLMモードでも先頭20件しかLLM生成されない。残りは `structured` にフォールバックする。
- **`--mailto` がないとOpenAlexの速度制限が厳しい**: politepool対象外になるので本番実行時は指定推奨。

-----

## 7. 決定ログ

- `2026-02-xx` OpenAI Responses APIを採用（Chat Completionsではない）。既存実装に合わせる。
- `2026-02-xx` Plan A/B 並立を廃止。Plan B（LLM生成）＋ GeminiCLI後処理の二段階に一本化。`plan_a` CLIオプションは `structured` のエイリアスとして残存するが実質廃止。
- `2026-05-28` 500本収集→20本レポート形式（Track A/B）に方針変更。Track A：関係グラデーション10本（関係軸ラベル付き）、Track B：接続点フィーチャー10本（接続点タイプ別ラベル付き）。却下した案：500本のまま品質を上げる→ユーザーが消費できる量を超えていた。
- `2026-05-29` Track B の収集方式を修正: Track Aと同じ候補プールから残りを選ぶ方式を廃止。Track Bは別ドメイン・別クエリで独立収集することで「意外性」を担保する。接続点タイプの固定リストも廃止しLLMが自由発見する方式に変更。
- `2026-05-29` テーマ別履歴保存を追加: 採用論文20本のIDをテーマハッシュキーで管理。Phase 1はローカルJSONファイル（`data/history/{theme_hash}.json`）、Phase 2以降はDB移行。収集候補から既使用IDを除外することで同一論文の再利用を防ぐ。
- `2026-05-30` **方針を再定義（contrarian 中核化）**: プロジェクトの核を「思考の狭窄に抗い、遠いが構造的に接続する論文を対置して視座を広げる」ことに据え直し。NotebookLM Deep Research（66ソース）でセレンディピティ発生条件を調査し [`docs/research/serendipity_conditions.md`](docs/research/serendipity_conditions.md) に一次資料化。主要決定:
  - **MVP を「20本レポート」から「Track B の良質な1本」へ**。本数は質ゲートの閾値超え数（出力であって入力でない）。却下案: 本数先行→近接/Anomaly混入で質が崩れた（2026-05-29の実行で実証）。
  - **Track B を中核、Track A はアンカー（任意）**に再配置。旧 A:10/B:10 対等を廃止。
  - **選別を距離スコア × 構造スコアの乗算**に。Gentnerの Analogy を狙い Anomaly を強制棄却、近接（マイオピア）も棄却。
  - **出力を4部構成に復活**（概要/関連性/役に立つ可能性の仮説/注意点）。旧3行構成では中核の「役に立つ可能性の仮説」が脱落していた。
  - 想定ユーザーを「作者自身が第一」と正直化。Web化・課金は plan.md §12「将来構想（任意）」へ分離。
- `2026-05-29` Track A/B の詳細仕様を確定（Step 1完了）※一部は2026-05-30の再定義で更新:
  - 関係度表現: 5段階ラベル（高/中高/中/中低/低）を採用。数値は却下（LLMによる偽精度を避ける）。
  - 関係軸ラベル: LLMがテーマから広めの候補リストを生成し、各論文に最適なラベルを割り当てる方式を採用。固定語彙は却下（テーマごとに最適化され、複数回利用で多角的な視座が蓄積される設計）。
  - Track AとTrack Bは同じ候補プールを共有する。Track Aが上位10本を選出後、残りからTrack Bが「1点だけ関係ある」論文をLLMが発見する。
  - Track B 補充ルール: 単一接続点のある論文が足りなければランダムで補充。接続点タイプの固定リストは設けない（LLMが発見した接続点をラベル化する）。
  - classify実装方針: Track A はキーワードスコアリングで候補を絞り込み、LLMが関係軸ラベルを割り当て。Track B はLLMが残り候補から「1点だけ関係ある」論文を識別。ハイブリッド方式を採用。

-----

## 8. 未解決 / TODO（仕様レベル）

- 選別スコアの設計確定: 距離スコア（意味的距離の測り方）・構造スコア（関係構造の一致をLLMにどう判定させるか）・乗算後の質ゲート閾値
- Track B 用クエリ「別ドメイン概念 × テーマ核心語」の掛け合わせプロンプト設計（教育・gamification偏りの抑制を含む）
- 4部構成の生成プロンプト設計（特に「役に立つ可能性の仮説」を慧眼の肩代わりとして書かせる指示）
- GeminiCLI入力フォーマットを4部構成に合わせて更新
- 履歴ファイルのスキーマ定義（`data/history/{theme_hash}.json` の構造）
- Phase 1 の「Done」判断基準: 複数テーマで「遠いが構造一致」の1本が安定して出力でき、Anomaly・近接が混入しないこと
