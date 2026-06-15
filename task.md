# 作業タスクリスト

`roadmap.md`からブレークダウンした、具体的な作業タスクを管理します。

---

## 作業中 (In Progress)

- [/] Track A Git実用アンカー設計
    - [x] 研究テーマに直接関連する OSS / GitHub repository を検索・収集する条件を定義する
    - [x] Track A を「近接論文アンカー」だけでなく「直接使える実装・制約・失敗パターンのアンカー」として再定義する
    - [x] Git 由来情報の信頼性評価（stars / activity / license / issue quality / last commit / README completeness）を設計する
    - [x] Track B の遠類推と混同しない表示区分・出力フォーマットを設計する
    - [x] 設計結果を `plan.md` 変更案または `docs/specs/` の設計メモにまとめる（`docs/specs/track_a_git_anchor_design.md`）
- [/] Phase 1 Done 判断: Track B 品質評価
    - [ ] 複数テーマでサンプル生成し、「遠いが構造一致」の1本が安定して出るか確認する
    - [ ] Anomaly（無意味接続）と近接（マイオピア）が混入していないか確認する
    - [ ] 「役に立つ可能性の仮説」が論文固有の発見に基づいているか確認する
    - [ ] 飽和ノート発生時に弱い候補で水増しされないことを確認する
    - [ ] 品質評価結果を `docs/quality_eval.md` または `memo.md` に追記する

---

## 未着手 (To Do)

- [x] A-RS1: byrepo Pillar 2 (LMA) 改善
    - [x] 完成判定の床（採用シグナル＋過去 issue 活動＋高クローズ率の条件付きで 12〜15点床止め）を実装する
    - [x] 候補プール内相対正規化（プールをドメインサンプルとみなし相対順位で LMA を付与）を実装する
- [x] A-RS2: byrepo Pillar 1 配点移行（README 成熟度 → 時間・他人系シグナル）。GITHUB_TOKEN 事実上必須化とセット
    - [x] 先手: CI 実行履歴＋リリース刻みを verified maturity（最大12点）として導入し、リッチシグナル取得時のみ README 系をスケールして移譲する
    - [x] 「他人」系シグナル（外部コントリビュータ数 / owner 以外の起票者）を third_party（最大6点）として導入する（dependents は REST 非提供のため対象外）
- [/] Track A Git practical anchors に discussion 観測や score 内訳表示の改善を追加する
    - [x] score 内訳表示の改善: total `/100`・各 Pillar の max（/30 /25 /20 /25）・スコアリングモード（rich: time+people / README-only）を Track A Markdown に表示
    - [ ] discussion 観測: GitHub Discussions は REST に一覧エンドポイントが無く GraphQL 専用（dependents 同様）。GraphQL 経路の導入が必要なため保留
- [x] LLMモックを使った `fill_track_entries` の統合テストを追加する
- [x] `roadmap.md` の Phase 1 現況を、Step 9 / R2 / R3 / R5 / M3 実装済みの状態に同期する
- [ ] Web化・課金は現時点では実装しない。必要になったら Phase 2 として再評価する

---

## 完了 (Done)

### 2026-06-15 Track A score 内訳表示の改善
*   Track A Markdown の Reliability Score 行に total `/100` と各 Pillar の max（Impl/Doc /30・LMA /25・Comm /20・Sec /25）を表示。
*   スコアリングモードタグ（`[rich: time+people]` / `[README-only]`）を追加し、スコアが同一モード内でのみ比較可能であることを読み手に明示（A-RS2 の配点移行に対応）。
*   Verified Maturity（/12）・Third-Party Signal（/6）も max 付き表示に統一。`tests/test_export_render.py` に rich 内訳ケースを追加（全 111 件 green）。
*   discussion 観測は GitHub Discussions が GraphQL 専用（REST 一覧なし）のため保留。

### 2026-06-15 A-RS2 続編: Pillar 1 に「他人」系シグナルを追加（A-RS2 完了）
*   `_third_party_score`（最大6点）= 外部コントリビュータ数（owner 除く、`/contributors`、最大3）＋非 owner issue 起票者数（issues サンプル再利用・追加 REST ゼロ、最大3）。
*   Pillar 1 rich モード配点を再配分: README 系 0.4 倍（completeness 8 / code 4）＋時間系 verified maturity 12 ＋他人系 third_party 6 = 30。非 rich は従来どおり。
*   owner 判定のため `owner_login` を保持。`_fetch_issue_signal` を 5-tuple 化（非 owner 起票者を計上）。dependents は GitHub REST 非提供のため対象外。
*   `source_meta`＋Track A Markdown（Third-Party Signal 行）に露出。`tests/test_git_collect.py` に3ケース追加（全 110 件 green）。

### 2026-06-15 A-RS2: Pillar 1 配点移行の先手（CI実行履歴＋リリース刻み）を実装
*   `_verified_maturity_score`（最大12点）= リリース刻み（`_release_cadence_score` 最大6）＋CI健全性（`_ci_health_score` 直近 runs の実行＋成功率 最大6）。設定ファイル存在でなく「回って通っている」事実を採点。
*   Pillar 1（最大30据え置き）をリッチシグナル取得時のみ README 系 0.6 倍へスケールし、空いた12点を verified maturity に移譲。非取得時は従来スコア（無認証回帰なし）。
*   取得は `/releases` と `/actions/runs`（repo あたり約2 REST 増）。`include_rich_signals=None` はトークン在席時のみ自動有効化、CLI `--git-rich-signals/--no-git-rich-signals` で上書き、失敗は graceful degrade。
*   `source_meta`＋Track A Markdown（Verified Maturity 行）に露出。`tests/test_git_collect.py` に8ケース追加（全 107 件 green）。

### 2026-06-15 A-RS1: Pillar 2 (LMA) 候補プール内相対正規化を実装（A-RS1 完了）
*   `_apply_pool_relative_lma` を追加。候補プールをドメインサンプルとみなし、push 鮮度のプール内相対順位で LMA を補正（成熟ドメインで全 repo が stale でも最も手入れされた repo が浮上）。
*   `max` 意味論で新鮮 repo は不変。順位天井 12点（完成判定の床 15点より低位）、同点は等クレジット、プール 3 未満は no-op、`GitCollectConfig.pool_relative_lma` で切替可、追加 API コストゼロ。
*   補正時は4 Pillars から `reliability_score` を再計算。`tests/test_git_collect.py` に4ケース追加（全 99 件 green）。

### 2026-06-15 A-RS1: Pillar 2 (LMA) 完成判定の床を実装
*   `_lma_score` を freshness 算出と完成判定の床に分離。stale でも「採用シグナル（stars>=50 / forks>=10）＋過去 issue 活動＋高クローズ率（closed>=open）」を満たす完成した安定ライブラリは LMA を 12点（強採用は 15点）で床止め。
*   `_is_completed_stable` を追加し「完成」と「誰も使っていない」を区別（Pillar 3「ゼロIssueの罠」と同型）。`max(freshness, floor)` で新鮮 repo のスコアは不変。
*   issue サンプルの open/closed 件数を `GitRepository.issue_open_count` / `issue_closed_count` に構造化保持し、`source_meta` へ露出。
*   `tests/test_git_collect.py` に床の発火/非発火5ケースを追加（全 95 件 green）。
*   DECISION_LOG 2026-06-15 / roadmap A-RS1 を更新。候補2（プール内相対正規化）と A-RS2 は未着手。

### 2026-06-09 named flow 追加（byrepo / byserendipity）
*   Track A Git practical anchors 用の named flow `byrepo` を `docs/agent_rules/byrepo.md` に追加。
*   Track B 構造類推用の named flow `byserendipity` を `docs/agent_rules/byserendipity.md` に追加。
*   `AGENT_COORDINATION.md` の Standard Named Flows に両者を登録し、`bynote` 系と同様に呼び出し名で扱えるよう整理。

### 2026-06-09 Track A Reliability Score と issue 観測の追加
*   GitHub issues を少数サンプル取得し、open / closed 件数、本文有無、label の有無を issue signal として評価する処理を追加。
*   Theme Fit / Activity / Adoption / License / README / Issue / Research Linkage からなる暫定 Reliability Score を実装。
*   repository 正規化時に score と issue signal を `Work.source_meta` へ保持し、Track A Markdown に表示するよう更新。
*   `tests/test_git_collect.py` と `tests/test_export_render.py` を更新し、score 算出と出力反映を検証。

### 2026-06-09 Track A Git collector の Track A パイプライン接続
*   GitHub repository を `Work` へ正規化する変換を追加し、既存の Track A 分類・生成・履歴パイプラインへ接続。
*   CLI の Track A 収集元を OpenAlex 近接論文から Git practical anchors へ切り替え。
*   Track A の生成プロンプトを repository 前提でも破綻しないよう調整。
*   Track A Markdown 表示を GitHub repository 向けに分岐し、`stars` / `GitHub` / 更新年を表示。
*   `tests/test_git_collect.py` と `tests/test_export_render.py` で接続後の変換・表示を検証。

### 2026-06-09 Track A Git実用アンカー collector の最小実装
*   GitHub REST API を叩く最小クライアント `src/github/client.py` を追加。
*   `src/pipeline/git_collect.py` に Track A 向け Git 検索クエリ生成、repository 検索、README base64 デコードを実装。
*   `src/core/models.py` に GitHub repository メタデータを保持する `GitRepository` データクラスを追加。
*   `tests/test_git_collect.py` でクエリ生成、README デコード、search + readme 取得フローをモック検証。
*   まだ Track A の既存分類・Markdown 出力パイプラインには未接続。

### 2026-06-09 Track A Git実用アンカー設計メモ
*   Track A を「近接論文アンカー」から「実装・制約・失敗パターンを示す Git 実用アンカー」へ再定義する設計メモを追加。
*   OSS / GitHub repository の収集条件、除外条件、Repository Reliability Score の暫定評価軸を整理。
*   Track B の遠類推と混同しない表示区分として、Track A を `Practical Anchors` 系の補助セクションで扱う方針を明文化。
*   実装に落とす際の最小単位を「検索 / メタデータ取得 / README要約 / 軽い issue 観測 / Markdown レンダリング」として整理。

### 2026-06-07 fill_track_entries 統合テストと roadmap 同期
*   `tests/test_fill_track_entries.py` を追加し、`fill_track_entries` が Track A / Track B の LLM 生成境界をモック経由で呼び分け、結果を `OutputEntry` に反映することを検証。
*   LLM 生成が `None` を返した場合に、既存の構造化 fallback（relationship / summary / hypothesis / caution）へ落ちることを検証。
*   `roadmap.md` の Phase 1 現況を 2026-06-07 時点へ更新し、Step 9 / R2 / R3 / R5 / M3 を実装済みとして同期。
*   確認: Codex 同梱 Python で新規テストの direct runner と `compileall` が成功。PATH に `python` / `py` と pytest が無いため `python -m pytest tests/ -q` は未実行。

### 2026-06-03 タスク整理
*   `spec.md` §8 の現在未解決に合わせ、作業中を「Phase 1 Done 判断: Track B 品質評価」に更新。
*   次の未着手として LLMモック統合テストと roadmap 現況同期を明示。
*   Web化・課金は `plan.md` §12 の将来構想扱いのため、現時点の実装対象外として維持。
*   Git を検索元にした Track A 実用アンカーは予定タスクとして作業中へ追加。まずは設計から進める。

### Step 9 (B): 複数本モードの品質再設計（2026-05-30 完了）
*   Track B 選別を SOLVENT の Purpose-Mechanism スキーマで再構築。`_score_b_chunk_pm` で structure abduction（P/M先抽出→比較）を実装。
*   serendipity = purpose_sim × mechanism_dist（乗算）に変更。テーマ別 analogy-poor 検出（`_extract_theme_schema`）を追加。
*   `concept_distance.py` を Wu-Palmer 近似の L0/L1 Jaccard 階層距離に刷新（`ThemeProfile`）。near_domain_signal で同分野論文の mechanism_dist を 0.5 にキャップし false-serendipity を抑制。
*   質ゲートを固定 0.25 → テーマ別 percentile-top30%（絶対下限 0.20）に変更。MMR 多様性再ランキング・0件 fallback を実装。
*   `_PURPOSE_SIM_MIN` 0.25 → 0.40 に引き上げ（抽象カテゴリ一致の排除）→ **後に R3 で 0.20 に緩和**（ディスクリートレベル化＋R2 judge gate と二重ゲートになっていたため）。現行値: 0.20。
*   検証（4テーマ）: energy=Digital Twin 選出（power-grid 近接なし ✓）、casual=5件（複数本 ✓）、social=量子情報拡散 serendipity=0.56（最高品質の遠類推 ✓）、wind=海洋循環・気候経済（4件）。
*   wind/social は analogy-poor でなく approach_type:experiment の測定テーマゆえ正しく analogy-rich と判定（前セッションの analogy-poor 予測は旧スコアリングのバグによる誤診と確認）。

### Step 9 Phase 2 各ラウンド（R1〜R5・M3・citation 2-hop、2026-05-31 完了）
*   **R1（具体的発見の引用強化）**: `_score_b_chunk_pm` に `paper_finding`（方向＋数値/効果量）フィールドを追加。`serendipity_rationale` に発見を埋め込む形式を必須化。数値捏造ガード（`_unsupported_numbers`）を `_llm_generate_track_b_text` に実装（Abstract に存在しない数値を hypothesis に書かせない）。R2 judge に `proposed_mapping` として findings を渡し答合わせ可能に。
*   **R2（hollow gate）**: `_judge_b_candidates` で候補ごとに Structural Depth（Gentner）・applicability・has_causal_pm を別パスで評価。`structural_depth < 0.30` の純粋 hollow を棄却。`has_causal_pm=False`（観察的・理解志向）は棄却せず「構造対応ゆるめ・思考のタネ」キャビアを表示（recall 重視のユーザー調整）。
*   **R3（purpose_sim 離散レベル化）**: `purpose_level`（none/partial/strong → 0.10/0.45/0.70）を導入し `_PURPOSE_LEVELS` に錨付き離散スケールをマップ。run をまたいだ 0.7↔0.0 反転ノイズを除去。`_PURPOSE_SIM_MIN` 0.40 → 0.20 に緩和（R2 gate と二重ゲートになっていたため）。
*   **R5（自己一貫性投票）**: `--score-votes K` で PM スコアリングと hollow judge を K 回実行し、数値フィールドを中央値・has_causal_pm を多数決で集約。スコアが output-floor を跨いで in/out を繰り返す問題を抑制。`temperature=0.0` を採点タスクに適用。デフォルト K=1（コスト不変）。
*   **M3（テーマ飽和検知）**: `output_floor` 超えが 0 件かつ `--allow-weak-fallback` 未指定の場合、弱い fallback を出力せず「飽和ノート」（`_write_saturation_report`）を書いて終了。履歴不更新。`diag` dict でステータスを呼び出し元に通知。テスト追加（`test_m3_saturation.py`）。
*   **citation 2-hop 収集**: `collect_citation_candidates` を実装。near-field 論文の共有引用文献（bridges）を経由して別ドメイン候補を収集。seeds の L0 概念 ID でホームドメインを除外。Track B プールに統合済みの重複を id/title/DOI 三重 dedup で排除。
*   **MAX-MIN 多様化**: `_maxmin_diversify` で concept Jaccard 最遠選抜（Farthest-point greedy）を実装。scoring cap 超えの候補を LIST 先頭切り捨てでなく概念空間最遠点でサブサンプル（citation 2-hop の遠候補がリスト末尾で切られる問題を解消）。テスト追加（`test_maxmin_diversify.py` / `test_collect_citation.py` / `test_purpose_level.py` / `test_score_voting.py`）。

### 2026-06-01 全ブランチ統合・構成整備
*   全ブランチ（claude/contra-step9-gate-tuning・claude/implementation-status-701DK）を main にマージし origin へ push。
*   構成点検レポート作成（`docs/structure_inspection_2026-06-01.md`）。
*   **A（ドキュメント同期）**: README.md 全面改稿（contrarian CLI・Track B 中核・実装済み機能）。spec.md: ディレクトリ図・生成モード・§6 落とし穴（実装済みに訂正）・§7 決定ログ（R2/R3/R5/M3）・§8 未解決リスト を現状に同期。
*   **B（デッドコード削除）**: 旧 surface×structure スコアリング・classify_stub・generate_entries（3行生成）・build_minimal_document・domain_distance 等を削除。未使用 import を除去。
*   **C（ドキュメント重複解消）**: docs/ 直下の重複 3 ファイルを削除（正本は docs/specs/ に統一）。
*   **D（テスト補強）**: 数値捏造ガード・export レンダリング・input_schema・history の単体テストを追加。合計 71 件 green。

### 2026-05-30 Git公開準備
*   生成済み `output/` を Git 管理対象から外し、今後の実行結果が公開差分に混ざらないよう `.gitignore` に追加。

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
*   `spec.md`（AI向け開発仕様書）を新規作成

### 2026-05-30 方針再定義（contrarian 中核化）
*   セレンディピティ発生条件をNotebookLM Deep Research（66ソース）で調査・一次資料化（`docs/research/serendipity_conditions.md`）
*   MVPを「20本レポート」から「**Track B の良質な1本**」へ再定義（本数は質ゲートの出力）
*   Track Bを中核・Track Aをアンカーに再配置、選別を距離×構造の乗算に、出力を4部構成に復活
*   `plan.md`・`spec.md`・`roadmap.md`・`task.md` を新方針に全面更新
*   実装済み: 撤回論文フィルタ、Track B複数ドメインクエリ、assumptionsクエリ、ドメインペナルティ（旧20本構造上での先行修正）

### Step 8 (A): 距離スコアの較正（2026-05-30 完了・テーマ非依存化）
*   **near/far はテーマ相対量**という原則を確立。特定ドメイン語のハードコードリスト（ゲームテーマ由来）を全廃し、テーマ自身の field・keywords を near の基準点として LLM に渡す方式へ統一。多岐にわたるテーマで誤作動しない設計に。
*   `_score_b_chunk` プロンプトを書き換え: surface_overlap をテーマの field・keywords 基準で較正（「テーマと同じ現象/課題を別の応用分野で扱う論文は隣接=0.3-0.5、near 0 にしない」）。structure_match に Gentner の literal-vs-analogy 区別を追加（隣接ゆえの見かけの構造一致は surface 側へ寄せる）。
*   `collect.py generate_track_b_queries`: グローバル定数 `_EXCLUDED_TRACK_B_DOMAINS`（education/gamification 固定）を撤廃。「テーマと同じ現象/課題を扱う隣接分野は除外」という判断基準＋テーマの field・keywords を LLM に渡す方式へ（テーマごとに near が変わる問題を解消）。
*   `_llm_generate_track_b_text` のユーザープロンプトを「論文先頭・テーマ後置」に再構成し、Abstract固有の数値・発見引用を必須化（テーマの不安点の言い換え禁止を明示）。
*   検証: `--single` で casual_puzzle（距離0.7×構造0.6=0.42）と energy（距離0.5×構造0.6=0.3）の2テーマ実行。旧来の距離0.9過大評価は再現せず中距離帯に収まることを確認。hypothesis は論文固有のメカニズムを起点にしている。
*   `classify.py _DOMAIN_PENALTY_TERMS`（Track A・ゲームサブジャンル語固定）も撤廃。何をオフトピックとするかは `theme.keywords.exclude`（ユーザー宣言）に依拠し、exclude は単一 include より強い降格信号として weight 2 を適用（`_EXCLUDE_WEIGHT`）。Track A は `--single` で常に省略・既定でも 0 のため影響範囲は小だが、テーマ依存の解消として整理。
*   補足（Step 9 へ）: energy 試行で選出論文がやや近接寄り（距離0.5）。質ゲート水準と候補プールの遠さ確保は Step 9 で調整。

### 2026-05-30 MVP実装（Step 2〜6 完了・E2E成功）
*   Step 2: `collect.py` の Track Bクエリを「別ドメイン概念 × テーマ核心語」の掛け合わせ式に（`generate_track_b_queries`, `_theme_anchor`）
*   Step 3: `classify.py` に `select_track_b`（距離×構造の乗算、Anomaly棄却 `_STRUCTURE_MIN`、近接棄却 `_SURFACE_MAX`、質ゲート `_SERENDIPITY_GATE`）。スコアリングはチャンク分割でAPIタイムアウト回避
*   Step 4: `generate.py` を4部構成に（`_llm_generate_track_a/b_text` が4要素タプル、`usefulness_hypothesis` 追加）
*   Step 5: `main.py` に `--single`/`--track-b-count`/`--track-a-count`/`--serendipity-gate`。Track Aは任意アンカー化
*   Step 6: `output_spec.py` の `_render_4part_body` でSUMMARY/RELATIONSHIP/HYPOTHESIS/CAUTIONを出力。`gemini_materials.jsonl` も4部構成＋スコア対応
*   `models.py` の `OutputEntry` に距離/構造/セレンディピティスコアと `usefulness_hypothesis` を追加（非破壊）
