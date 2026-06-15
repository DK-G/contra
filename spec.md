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
| 実装収集API | GitHub API | v3（REST） | Track A Git アンカーの収集に使用 |
| LLM（4部構成生成） | OpenAI Responses API | gpt-4o-mini デフォルト | Responses APIを使用（Chat Completionsではない） |
| LLM後処理 | GeminiCLI | 外部ツール | `gemini_materials.jsonl` を読み込んで仕上げ |
| 外部ライブラリ | なし（stdlib のみ） | - | `urllib.request` で HTTP 通信。pip不要 |
| ビルド/デプロイ | なし | - | Phase 1はローカルCLI実行のみ |

### 2.1 将来的な追加技術要素（2026-06-09 導入決定）
* **MCP (Model Context Protocol)**: Microsoftのサンプル等を参照し、エージェント環境（Claude Code等）とのツール統合を行う。
* **Gensim/NumPy等 (GloVeコンセプト)**: 分散表現を用いた概念アライメント距離計算用。
* **agentmemory (または独自のローカル持続メモリ)**: 探索履歴や失敗した接続の永続メモリ管理。


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
    parser.py         # APIレスポンス → Work への正規化（source_meta に OA/arXiv ヒントを付与）
  /fulltext           # OA全文 provider 層（差し替え可能・入力補強レイヤー。スコア核には触れない）
    base.py           # FullText / FulltextProvider Protocol / ProviderChain / needs_fulltext / effective_abstract
    cache.py          # 論文ID単位のローカルキャッシュ（hit/miss 両方記録・再取得しない）
    http.py           # 非arXiv provider 共通の polite HTTP フェッチャ（レート制御・retry）
    textutil.py       # 共通テキスト整形（collapse_ws / extract_excerpt / prose_ratio）
    arxiv.py          # ① arXiv provider（キー不要・e-print LaTeX 展開→ノイズ除去）
    europepmc.py      # ② Europe PMC provider（キー不要・JATS XML 全文）
    ia_scholar.py     # ② IA Scholar provider（キー不要・fatcat 経由の被アーカイブ全文）
    core.py           # ② CORE provider（CORE_API_KEY を env から・未設定なら無効）
    oa_pdf.py         # ③ oa_url PDF フォールバック（stdlib only・best-effort・prose品質ゲート）
  /pipeline
    collect.py        # Collector: テーマ→クエリ生成→ページング収集
    filter.py         # abstractあり優先フィルタ・件数制限
    classify.py          # Track B 選別（select_track_b: SOLVENT purpose_sim × mechanism_dist）/ Track A 分類
    generate.py          # 4部構成生成（fill_track_entries: llm/structured/simple モード）
    export.py            # OutputDocument → Markdownファイル書き出し
    concept_distance.py  # Wu-Palmer 近似 L0/L1 Jaccard 階層距離・近傍ドメイン判定
    history.py           # テーマ別採用論文履歴（ハッシュ→JSON）
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
  ↓ validate_and_normalize()          # ThemeInput に変換・バリデーション
  ↓ collect (collect.py)              # Track B: 別ドメイン概念 × テーマ核心語でOpenAlex収集
  ↓ build_theme_profile()             # 近傍論文から L0/L1 Jaccard ドメインプロファイル構築
  ↓ collect_citation_candidates()     # citation 2-hop: 近傍論文の引用ネットワークから遠ドメイン候補を追加
  ↓ select_track_b (classify.py)      # purpose_sim × mechanism_dist (SOLVENT) で選別
                                       #   → Anomaly (purpose_sim < 0.20) 強制棄却
                                       #   → hollow judge (R2) で structural_depth 確認
                                       #   → percentile-gate + output-floor で品質絞り込み
  ↓ [M3 飽和判定] output-floor 超え0件 → _write_saturation_report() で飽和ノート出力・終了
  ↓ generate (generate.py)            # 4部構成生成（概要/関連性/役に立つ可能性の仮説/注意点）
  ↓ export_markdown()                 # 出力Markdownを書き出し
  ↓ _write_gemini_materials()         # gemini_materials.jsonl を書き出し
                                       ↓ GeminiCLI（外部）で後処理
```

3段階（収集／選別／提示）の各段に効くセレンディピティ知見の対応は [`plan.md`](plan.md) §6 と [`docs/research/serendipity_conditions.md`](docs/research/serendipity_conditions.md) §7 を参照。

**生成モード切り替え（--gen-mode）**
- `simple`: キーワード一致スコア、abstract切り詰め（テスト用）
- `structured`: テーマとの構造的関係・前提チェックをルールベースで生成
- `llm` / `plan_b`: OpenAI Responses API で4部構成生成（`--llm-max-items` 件まで）

-----

## 4. 制約・禁止事項 ★最重要

- **編集禁止のファイル / ディレクトリ**: `output/` 配下の生成済みファイル（上書き不可）、`data/` 配下のサンプル入力JSON
- **追加禁止の依存・ライブラリ**: 外部ライブラリ（pip install）は原則追加しない。必要な場合は必ず確認する。stdlibのみで実装する方針。
- **セキュリティ上の禁則**: `OPENAI_API_KEY` をコードやファイルに直書きしない（環境変数から読む）。APIキー・メールアドレスをoutputやgitにコミットしない。
- **勝手にやってほしくないこと**:
  - `src/core/models.py` のデータクラス構造の変更（下流への影響が大きい）
  - `select_track_b` のスコア設計（purpose_sim × mechanism_dist、ゲート閾値）を仕様確認なく変更する
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

- ~~**選別の乗算スコアが未実装**~~ → **実装済み** (Step 9): `select_track_b` で `serendipity = purpose_sim × mechanism_dist` (SOLVENT 方式)。Anomaly（`purpose_sim < 0.20`）強制棄却・hollow gate（Structural Depth judge）・percentile gate 実装済み。
- ~~**生成が3行構成のまま**~~ → **実装済み** (Step 9): `fill_track_entries` で4部構成（概要/関連性/役に立つ可能性の仮説/注意点）を LLM 生成。数値捏造ガード付き。
- ~~**本数が固定（10/10）のまま**~~ → **実装済み** (Step 9): 質ゲート方式（percentile-gate + `--output-floor`）。`--track-b-count` は上限キャップ。MVP は `--single` で Track B 最良1本。
- **OpenAI Responses API を使用**: Chat Completions APIではない。`/v1/responses` エンドポイント。`extract_output_text()` でレスポンスを取り出す。
- **`llm_max_items` のデフォルトが20**: LLMモードでも先頭20件しかLLM生成されない。残りは `structured` にフォールバックする。
- **`--mailto` がないとOpenAlexの速度制限が厳しい**: politepool対象外になるので本番実行時は指定推奨。

-----

## 7. 決定ログ

- `2026-06-15` **OA全文 provider 層の導入（abstract 薄 → mechanism 判定弱の補強）**:
  - byserendipity / bybridge の候補で「abstract が薄く mechanism 判定が弱い」課題を、OA論文の全文取得で補強する**差し替え可能な provider 層** `src/fulltext/` を新設。解決順は **① arXiv（キー不要・e-print LaTeX が最低ノイズ）→ ② Europe PMC（キー不要・JATS XML）/ IA Scholar（キー不要・fatcat 経由）/ CORE（`CORE_API_KEY`）→ ③ OpenAlex `oa_url` PDF（汎用フォールバック・stdlib only の best-effort）**。Unpaywall は OpenAlex `oa_url` に内包されるため独立 provider にしない。
  - **位置づけは「収集/判定の入力材料」レイヤー**。`select_track_b` のスコア設計（`purpose_sim × mechanism_dist`、ゲート 0.20/0.50/0.35 等）には一切触れない。全文は `effective_abstract(work)` 経由で PM スコアラ入力の abstract に**連結**するだけ（`--fulltext` 無指定なら従来とバイト単位で同一）。
  - **無駄打ち防止**: `--fulltext`（既定 off）の opt-in。`needs_fulltext`（OA かつ abstract が `--fulltext-max-abstract` 字未満）に合致する Track B 候補だけ取得。取得結果は論文ID単位で `data/fulltext/`（git追跡外）に**キャッシュ（hit/miss 両方）**し再実行で再取得しない。失敗時は `None` で abstract のみへ素直にフォールバック。
  - **制約遵守**: 外部ライブラリ追加なし（urllib / gzip / tarfile / zlib / xml.etree のみ）。APIキーは env から（arXiv 不要、CORE は `CORE_API_KEY`）。`src/core/models.py` は変更せず、OA/arXiv ヒントと取得全文は既存の `Work.source_meta`（柔軟 dict）に格納。
  - **多ファイル e-print 対応**: arXiv は本文を `\input` で別 `.tex` に分割するため、main の body と各フラグメントを結合してから LaTeX 除去（main の `\end{document}` でフラグメントを取りこぼさない）。
  - **PDF フォールバックは best-effort**: stdlib のみでは CID/Type0 フォントのグリフ再マップ不可。`prose_ratio` 品質ゲートで崩れたテキストは採用せず `None`（=最後尾 provider なので abstract のみに戻る）。
  - **検証**: ユニットテストはネットワークを injected fetcher で全モック（`tests/test_fulltext.py` / `tests/test_fulltext_providers.py`）。実ネットワーク疎通は `scripts/arxiv_fulltext_probe.py`（arXiv 単体＋`--doi/--oa-url` でフルチェーン）で別途確認する。
  - **後続候補**: IA Scholar provider の追加、実機サンプル生成での全文補強あり/なし品質比較。

- `2026-06-09` **byrepo パイプラインの信頼性スコアリングの改善（4 Pillars実装）および次世代機能の導入決定**:
  - Track A（Gitリポジトリ）の信頼性評価ロジックを、単純なスター数や更新日付から「マルチディメンショナルな100点満点スコア（4つのPillars）」にアップグレード。
  - クエリ構築における、スペースを含む除外フレーズのマイナス記号指定（例：`"-metaphor generation"`）が GitHub API で検索結果を 0 件にしてしまうバグを修正。GitHub が公式にサポートする `NOT` 構文（例：`NOT "metaphor generation"`）を使用するように修正。さらに `poetry` ツール除外の競合問題も解消。
  - レベルアップのインプット JSON `data/samples/theme_contra_level_up.json` を使った byrepo 探索に成功し、3つの有用なリポジトリ（MCP, GloVe, agentmemory）を発見。ライセンス調査（MIT, Apache-2.0）の結果、いずれも安全であることを確認し、Contra の将来のアーキテクチャ要素（MCPサーバー化、GloVeコンセプトの分散表現アライメント、agentmemoryの持続メモリ）として導入することを決定。

- `2026-02-xx` OpenAI Responses APIを採用（Chat Completionsではない）。既存実装に合わせる。

- `2026-02-xx` Plan A/B 並立を廃止。Plan B（LLM生成）＋ GeminiCLI後処理の二段階に一本化。`plan_a` CLIオプションは `structured` のエイリアスとして残存するが実質廃止。
- `2026-05-28` 500本収集→20本レポート形式（Track A/B）に方針変更。Track A：関係グラデーション10本（関係軸ラベル付き）、Track B：接続点フィーチャー10本（接続点タイプ別ラベル付き）。却下した案：500本のまま品質を上げる→ユーザーが消費できる量を超えていた。
- `2026-05-29` Track B の収集方式を修正: Track Aと同じ候補プールから残りを選ぶ方式を廃止。Track Bは別ドメイン・別クエリで独立収集することで「意外性」を担保する。接続点タイプの固定リストも廃止しLLMが自由発見する方式に変更。
- `2026-05-29` テーマ別履歴保存を追加: 採用論文20本のIDをテーマハッシュキーで管理。Phase 1はローカルJSONファイル（`data/history/{theme_hash}.json`）、Phase 2以降はDB移行。収集候補から既使用IDを除外することで同一論文の再利用を防ぐ。
- `2026-05-30` **Step 8 距離スコア較正（テーマ非依存化）**: ★重要な設計原則の確立。
  - **原則: near/far はテーマごとに変わる相対量であり、特定ドメイン語をグローバル定数でハードコードしてはならない**（contra は多岐にわたるテーマを対象とするため）。「教育」はゲームテーマには近接だが、エネルギーテーマには遠方になりうる。near の基準は常に「テーマ自身の field・keywords」から実行時に導く。
  - `_score_b_chunk`（選別）: surface_overlap をテーマの field・keywords を基準にLLMが較正する方式へ書き換え。「テーマと同じ現象/課題を別の応用分野で扱う論文は隣接（0.3-0.5）で、near 0 にしない」と明示。structure_match には Gentner の literal-vs-analogy 区別を追加し、隣接ゆえの見かけの構造一致は surface 側へ寄せるよう指示。乗算 `structure×(1-surface)` は surface が正しく測れれば近接を自動降格する（NotebookLM の Nooteboom 最適認知距離・Goldilocks で裏付け済み）。
  - `generate_track_b_queries`（収集）: グローバル定数 `_EXCLUDED_TRACK_B_DOMAINS`（education/gamification 固定）を撤廃。「テーマと同じ現象/課題を扱う隣接分野は obvious connection を生むので除外」という判断基準＋テーマの field・keywords を渡し、LLM がテーマごとに近接ドメインを避ける方式へ。
  - `_llm_generate_track_b_text`（提示）: ユーザープロンプトを「論文先頭・テーマ後置」に再構成し、hypothesis に Abstract 固有の数値・発見の引用を必須化、テーマの不安点の言い換えを禁止。
  - **却下した案**: (1) ゲームテーマ由来の隣接ドメイン語リスト（`_ADJACENT_DOMAIN_TERMS`）に surface バンプ +0.25 を加える応急処置→他テーマで誤作動するため Step 8 内で破棄。(2) surface_overlap を数値閾値でハードカット→LLMスコアのバラツキに脆弱。いずれも特定テーマへの依存を残すため、テーマ相対のプロンプト較正に一本化した。
  - 検証: casual_puzzle（0.7×0.6=0.42）/ energy（0.5×0.6=0.3）の2テーマで距離が中距離帯に収まり、旧来の0.9過大評価が再現しないことを確認。
  - `_score_work`（Track A プリランキング）: `_DOMAIN_PENALTY_TERMS`（multiplayer/esport 等ゲームサブジャンル語の固定減点）を撤廃。オフトピック判定は `theme.keywords.exclude` に一元化し、exclude に weight 2（`_EXCLUDE_WEIGHT`）を適用してユーザー宣言を強い降格信号とした。Track A は既定 0・`--single` で常に省略のため影響小。
  - 残課題（Step 9）: energy で選出論文がやや近接寄り（距離0.5）。質ゲート水準・候補プールの遠さ確保を要調整。

- `2026-05-30` **方針を再定義（contrarian 中核化）**: プロジェクトの核を「思考の狭窄に抗い、遠いが構造的に接続する論文を対置して視座を広げる」ことに据え直し。NotebookLM Deep Research（66ソース）でセレンディピティ発生条件を調査し [`docs/research/serendipity_conditions.md`](docs/research/serendipity_conditions.md) に一次資料化。主要決定:
  - **MVP を「20本レポート」から「Track B の良質な1本」へ**。本数は質ゲートの閾値超え数（出力であって入力でない）。却下案: 本数先行→近接/Anomaly混入で質が崩れた（2026-05-29の実行で実証）。
  - **Track B を中核、Track A はアンカー（任意）**に再配置。旧 A:10/B:10 対等を廃止。
  - **選別を距離スコア × 構造スコアの乗算**に。Gentnerの Analogy を狙い Anomaly を強制棄却、近接（マイオピア）も棄却。
  - **出力を4部構成に復活**（概要/関連性/役に立つ可能性の仮説/注意点）。旧3行構成では中核の「役に立つ可能性の仮説」が脱落していた。
  - 想定ユーザーを「作者自身が第一」と正直化。Web化・課金は plan.md §12「将来構想（任意）」へ分離。
- `2026-05-30` **Step 9 複数本モードの品質再設計（SOLVENT Purpose-Mechanism 再構築）**:
  - **選別スコア設計変更**: `structure × (1-surface)` → `purpose_sim × mechanism_dist` に変更（SOLVENT framework。Precision@1% 0.67→0.92 の最大レバレッジ）。`_score_b_chunk_pm` でstructure abduction（LLMに P/M を先抽出→比較）を実装し、表層バイアスを除去。
  - **analogy-poor 検出**: `_extract_theme_schema` でテーマの Purpose/Mechanism を LLM 抽出し、understanding-oriented（「なぜ X が起きるか」）または暗黙物理特性依存テーマを `is_analogy_poor=True` と判定し 0件返却。system-building/experiment テーマは analogy-rich（wind/social 両テーマが実験測定テーマとして正しく analogy-rich 判定→量子情報拡散等の真の遠類推を発見）。
  - **客観距離（要素B）**: `concept_distance.py` を Wu-Palmer 近似の **L0/L1 Jaccard 階層距離**に刷新（`ThemeProfile` dataclass。完全名一致cosineを廃棄）。`near_domain_signal` が L0/L1 Jaccard > 0.30 の論文で `mechanism_dist` を 0.5 にキャップし、同分野の false-serendipity を抑制。
  - **質ゲート（要素D）**: 固定 0.25 → **テーマ別 percentile-top30%**（絶対下限 = `--serendipity-gate` CLI 引数、デフォルト 0.20）に変更。0件時は `_FALLBACK_FLOOR=0.10` で単一 best fallback。
  - **多様性再ランキング**: count > 1 のとき concept Jaccard を redundancy 信号とする **MMR** (λ=0.7) を適用。
  - **`_PURPOSE_SIM_MIN` 一時引き上げ**: 0.25 → 0.40（検証で 0.25–0.39 が抽象カテゴリ一致のみで構造類推なし）。→ **後に R3 で 0.20 に緩和**（ディスクリートレベル化＋R2 judge gate と二重ゲートになっていたため）。
  - **検証結果（4テーマ）**: energy=Digital Twin / Climate Risk 選出（power-grid 近接なし ✓）、casual_puzzle=5件（複数本 ✓）、social=量子情報拡散（異常拡散・スクランブリング） serendipity=0.56（purpose_sim=0.7 × mechanism_dist=0.8）で真の遠類推 ✓、wind=海洋循環(AMOC)・気候経済（4件）。
  - **却下した案**: (1) Step9 試行の objective concept band filter（_SHARED_MIN/MAX）→ complete-name cosine は false-far を生む根本問題があるため，L0/L1 Jaccard 階層距離に置換。(2) min(concept_distance, llm_distance) 結合→ 2信号の min は false-near/false-far を両方残す、cap 方式に変更。

- `2026-05-31` **R2: 候補レベル hollow ゲート追加**: `_judge_b_candidates` で候補ごとに Structural Depth（Gentner）と `has_causal_pm` を別パスで評価。`structural_depth < 0.30` の純粋 hollow（表層カテゴリ一致のみ）を棄却。`has_causal_pm=False`（観察的・理解志向）は棄却せず「構造対応ゆるめ・思考のタネ」キャビアを表示（ユーザー調整 2026-05-30: 遠くても genuine な類推をカットしないよう recall 重視）。

- `2026-05-31` **R3: purpose_sim を離散レベルへ**: `purpose_level`（none/partial/strong）を導入し 0.10/0.45/0.70 の錨付き離散スケールにマップ（`_PURPOSE_LEVELS`）。free 0-1 float から変更しラター間ノイズ（run をまたいだ 0.7↔0.0 反転）を除去。`_PURPOSE_SIM_MIN` を 0.40 → **0.20** に緩和（R2 judge gate と二重ゲートになっていたため）。**現行値: `_PURPOSE_SIM_MIN=0.20`**。

- `2026-05-31` **R5: self-consistency 投票（`--score-votes`）**: PM スコアリングと hollow judge を K 回実行し、数値フィールドを中央値・`has_causal_pm` を多数決で集約。スコアのノイズが output-floor を跨いで候補が in/out を繰り返す問題を抑制。デフォルト K=1（シングルパス・コスト不変）。K=3 で安定性向上（約3倍のLLMコスト）。採点タスクに `temperature=0.0` を適用。

- `2026-05-31` **M3: テーマ飽和検知**: `output_floor` 超えが0件かつ `--allow-weak-fallback` 未指定の場合、弱い fallback を出力せず「飽和ノート」（`_write_saturation_report`）を書いて終了。採用なし=履歴不更新。誤った弱接続で水増しレポートを出さない設計。`diag` dict でステータスを呼び出し元に通知。

- `2026-06-11` **第3方式 bybridge を構想確定**: ユーザーが2テーマ（研究テーマ＋つなげたいテーマ）を指定し、両者を構造的に媒介する「橋」論文を第3ドメイン含め探す指向型モード。正本は [`docs/bybridge_concept.md`](docs/bybridge_concept.md)。主要決定:
  - 「またがる」の定義は **(b) 構造的な橋**（A・B 双方に構造類推が成り立つ論文。第3ドメイン可）。却下案: (a) 文字どおりの交差（A∩B）→ 確立済み学際分野を引き当て意外性が低く、両側クエリは多義語罠を悪化させる。
  - **Track B の転置**と整理: Track B = `purpose_sim × mechanism_dist`（目的同じ・メカニズム遠い）に対し、bybridge = **mechanism_sim（両テーマへの構造一致）× domain_dist**。`select_track_b` は流用不可、bridge score（min ゲート＋積ランキング＋両側 surface ペナルティ）を新設する。
  - 実装前に**偽橋率プローブ**（共有構造の仮説生成プロンプト＋ゴールドテスト2ペア: 群れ↔流体→Toner–Tu、株価↔弾道→カルマン系）で較正する。answer-known 検証ができるのは bybridge 固有の利点。
  - 着手は Phase 1（Track B 品質確立）Done 後。roadmap.md Phase 1.5 に Step B-0〜B-5 を定義。

- `2026-05-29` ~~Track A/B の初期詳細仕様を確定（Step 1完了）~~ → **以下の項目は後続の決定（2026-05-29〜05-31）で大幅に更新済み。参照のみ**:
  - 関係度表現: 5段階ラベル（高/中高/中/中低/低）を採用（現在も有効）。
  - ~~Track AとTrack Bは同じ候補プールを共有~~ → **廃止**（2026-05-29の別エントリで独立収集方式に変更）。
  - ~~Track B 補充ルール: ランダム補充~~ → **廃止**（Step 9 で SOLVENT 選別・quality gate に変更）。
  - ~~classify実装方針: Track B はLLMが「1点だけ関係ある」論文を識別~~ → **廃止**（Step 9 で purpose_sim × mechanism_dist に変更）。

-----

## 8. 未解決 / TODO（仕様レベル）

以下は実装済みとなり解決した:

- ~~選別スコアの設計確定~~ → 実装済み（Step 9: `select_track_b`、SOLVENT purpose_sim × mechanism_dist）
- ~~Track B 用クエリ設計（別ドメイン偏り抑制）~~ → 実装済み（Step 9 Phase 2: 構造的側面クロス方式、`generate_track_b_queries`）
- ~~4部構成の生成プロンプト設計~~ → 実装済み（Step 9: `_llm_generate_track_b_text`、変数対応背骨＋数値捏造ガード）
- ~~GeminiCLI入力フォーマット更新~~ → 実装済み（`_write_gemini_materials` が Track A/B 4部構成対応）
- ~~履歴ファイルのスキーマ定義~~ → 実装済み（`ThemeHistory` dataclass、id/title/doi 三重dedup）

**現在未解決:**

- **Phase 1「Done」判断**: 複数テーマで「遠いが構造一致」の1本が安定して出力でき、Anomaly・近接が混入しないことを品質評価（サンプル生成フェーズ）
- **テスト補強**: LLMモックを使った `fill_track_entries` の統合テスト
- **bybridge（第3方式）の偽橋率プローブ**: Phase 1 Done 後に着手。仮説生成プロンプト＋ゴールドテスト2ペアで較正してから本実装（[`docs/bybridge_concept.md`](docs/bybridge_concept.md) §8、roadmap.md Phase 1.5 B-0）


## 検証ツール (Validation Tools)

- **ユニットテスト（`tests/`）**: 選別スコア / 収集 / 飽和検知 / purpose_level / MAX-MIN 多様化 / 数値捏造ガード / export レンダリング / input_schema / history / OA全文 provider 層（`test_fulltext.py` / `test_fulltext_providers.py`・ネットワークはモック）（`python -m pytest tests/`）
- **プローブスクリプト（`scripts/`）**: `depletion_probe.py` / `r1_model_probe.py` / `r2_judge_compare.py` / `r5_score_stability.py`（各チューニングラウンドの検証用）/ `arxiv_fulltext_probe.py`（OA全文 provider の実ネットワーク疎通確認・要 outbound）
