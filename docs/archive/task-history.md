# task 履歴アーカイブ — contra

> task.md の「完了 (Done)」節から移設した完了記録（2026-07-20 relocate・削除ではなく移動。詳細な判断経緯は DECISION_LOG.md に別途あり）。

## 完了 (Done)

### 2026-06-23 横断重複回避（履歴 dedup）を MCP/委譲経路へ配線
*   「同じレポートを繰り返さない」履歴 dedup（history.py）は **CLI 専用**で MCP/委譲経路に未配線だった（再実行で同じ論文が再出＝ユーザー指摘で発覚）。`mcp_server` に `compute_theme_hash(theme_overview)` キーで配線。
*   ヘルパ `_history_exclusions`（file history∪agent供給 used_ids/titles/dois・`no_history`で無効）／`_history_adopt`（post-gate通過分の id/正規化title/DOI を save_history）。収集時に除外（`_byserendipity_raw`/自己完結byserendipity/bybridge）、採用時に記録（自己完結＋`delegate_finalize`）。委譲は収集と finalize が別呼び出しでも同一ハッシュで自動整合。3ツールに `no_history`＋任意 `used_*` パラメータ追加。
*   検証: `tests/test_mcp_history.py` 5ケース＋実機2-run統合実証（キー無し）=RUN1 収集→3件採用→RUN2 がその3件を除外して残りを返す。全 **266 green**。残: OpenAlex client retry（semantic 5xx吸収）は別途。

### 2026-06-23 Track B をキー無し委譲ループへ（API を Claude Opus エージェントで代替・追加課金ゼロ）
*   「ガンガン回す」向けに、contra 自身は LLM を呼ばず（OpenAlex＋決定論ゲートのみ）、標的化抽象・採点・執筆を呼び出し側 Claude エージェントが代行する委譲ループへ。メータ Anthropic 切替案より「メータ API を使わない委譲」を選択（ユーザー決定）。
*   byserendipity の Phase 3 semantic 収集を key-free 化（穴埋め）: `serendipity_query.spec_from_payload`（agent facet→SerendipitySpec）＋`collect.collect_track_b_from_spec`（spec から semantic 収集・語彙 fallback 無し）＋`delegate.material_from_work`（work_from_material の逆）＋`mcp_server` の `byserendipity_discover --raw_only`（structure/facets を受け materials を返す）。bybridge は `bybridge_collect --raw_only`→`delegate_finalize` で既にキー無し成立のため無改修。
*   **★`search.semantic` 実機脆弱性対処**: 同エンドポイントが断続 5xx → facet 1本の失敗が収集全体を中断していたのを、`_collect_track_b_semantic` の facet 単位 try/except でスキップ継続に。
*   スキル＝委譲の置き場所: `docs/agent_rules/{byserendipity,bybridge}.md` を委譲キー無しループへ全面改稿＋`~/.claude/skills/{byserendipity,bybridge}/SKILL.md` を委譲既定へ更新。
*   実機検証: OPENAI/ANTHROPIC キー未設定で E2E 一周（手書き facet→実 OpenAlex semantic→materials→手書き採点→post-gate）。materials facet 5xx でも 2/3 facet で 58 異分野候補・anomaly 3件棄却・2件描画＝**キー無し完走/課金ゼロ実証**。`tests/test_delegation_keyfree.py` 6ケース・全 **261 green**。

### 2026-06-23 Track A 近傍シード収集に PRF（擬似適合フィードバック）導入
*   Phase 2 で「bybridge は異分野目的ゆえ PRF はホーム引き戻しで逆効果」と不採用にした PRF を、**ホーム語彙拡張が recall に効く Track A 近傍シード収集（`collect_and_filter`）へ再配置**（bybridge シード＋ドメインプロファイルの供給元）。
*   `_salient_terms`（純関数・LLM不使用）= 上位シードを relevance set とみなし seed 文書頻度で salient 語を抽出（stopword/定型句＋既出クエリ語＋単発語を除去・PRF の「corpus 頻出語を落として top-k」を静的 stopword＋in-set DF へ適応）。`collect_and_filter` に `use_prf=True`＝**初期検索が薄いとき（5≤収集数<max_count）だけ発火**し、ヘッドキーワード＋salient のペアで field-scoped 拡張（`fallback=False` で generic-search drift を回避）。広いテーマは base で満ちるのでコスト増ゼロ。
*   実機 A/B: ニッチテーマ（最適間隔の復習・home=psychology）で 148→300件、追加は spacing-effect/memory/retention のホーム論文が大勢（少数の多義 drift は downstream 篩い＋本番 max_count=20 で薄テーマ数件に限定ゆえ許容）＝net-positive。`tests/test_prf.py` 7ケース・全 **255 green**。byserendipity/bybridge は逆にホームから離れるため PRF 非採用（住み分け）。

### 2026-06-23 検索クエリ精度 Phase 3（byserendipity: 標的化抽象＋HyDE semantic＋実行前検証）
*   **★実機検証**: OpenAlex `search.semantic` は**実在する埋め込み/ANN エンドポイント**（戦略 doc の「要実機確認」に回答）。上位50件固定・ページング不可・`type:article` と合成可・`primary_topic.field.id:!` 否定と非合成（400）→ ホーム除外はクライアント側。
*   新規 `src/pipeline/serendipity_query.py`: `generate_serendipity_facets`（標的化抽象＝機能語＋構造制約保持で再記述、最大3遠 facet、各 HyDE 仮想アブスト・temp=1.0）／`build_semantic_query`（相補的結合＝構造アンカー＋仮想アブスト）／`validate_semantic_results`・`home_field_fraction`・`exclude_home_field`（非空＋ホーム収束の実行前検証）。
*   `src/pipeline/query.py`: `route="semantic"` を `search.semantic` へ配線（合成安全な type/year のみ・per-page 50 クランプ・field 除外は非出力）。`src/pipeline/collect.py`: `collect_track_b` を semantic 主経路化（`_collect_track_b_semantic`）＋全 facet 落選で語彙ベースラインへ quality-gate fallback（`_collect_track_b_lexical`）。後方互換シグネチャ＝MCP/CLI 無改修で恩恵。
*   選別段（classify.py の purpose_sim × mechanism_dist）・スコア設計値（0.20/0.50/0.35）は不変（spec.md §7 禁則）。round-trip は単一根拠文書が無いため「非空＋ホーム収束」へ適応（concept 類似は選別段に委ね非重複）。
*   実機 A/B: semantic は語彙と同等のホーム収束（0.02/0.03）・分野多様性（17/18）で、候補が**構造的に的中**（最適シーディング/マイクロインフルエンサー/生態系の到来順効果/ワクチン早期採用）＝語彙のキーワード散乱より net-positive。`tests/test_serendipity_query.py` 14ケース＋`test_query.py` semantic 2ケース更新・全 **248 green**。PRF は Track A 収集へ（別 PR）。

### 2026-06-23 検索クエリ精度 Phase 2（bybridge: co-citation＋betweenness）
*   新規 `src/pipeline/bridges.py`（全純関数・API 追加コスト 0）: `shared_bridge_count`（co-citation 強度）／`bridge_field_diversity`＋`annotate_bridge_signals`（各 bridge を引用する候補の primary_topic Field 多様性＝betweenness 代理を source_meta に刻む）／`bridge_rank_key`（betweenness→共有数→被引用）。mcp/delegate の重複 `shared_bridge_count` を一本化。
*   ホームドメイン除外を L0 concepts → `dominant_field_ids`（primary_topic.field 除外、無ければ concepts フォールバック）へ移行。`collect_citation_candidates` が収集時に候補を注記。delegate/mcp を betweenness 優先ランク＋「異分野 N」表示へ更新。
*   PRF は bybridge の異分野目的と衝突のため不採用（Track A 収集へ再配置）。
*   実データ検証: seeds home=CS+Materials を除外し Biochem/Medicine 候補、betweenness=5（共有 ML 基礎文献で 5 分野連結）が上位。`tests/test_bridges.py` 6ケース＋citation field 除外テスト・全 **233 green**。

### 2026-06-23 検索クエリ精度 Phase 1（基盤レイヤ・bynote 145af5df 由来）
*   bynote（NotebookLM Deep Research 77ソース＋Consensus/alphaXiv 実測）で「収集クエリそのものの精度」の戦略を確定。`docs/research/search_query_precision_strategy.md` ＋ DECISION_LOG 3エントリ。
*   新規 `src/pipeline/query.py`: `StructuredQuery`（フィールド限定 `title_and_abstract.search` 主体描画＋recall 安全な generic-search fallback＋`sanitize_filter_value`）。`collect.py` を汎用 `search=` から filter 主体へ配線し、`collect_citation_candidates` を共有 `StructuredQuery` ビルダへ統合（フィルタ構築を全経路で単一化・挙動保存）。
*   Topic ID 解決インフラ: parser `primary_topic.field`→`source_meta`、`OPENALEX_FIELDS`/`resolve_field_ids`（静的・単語境界）/`dominant_field_ids`（データ駆動ホーム）、`StructuredQuery.exclude_field_ids`/`max_referenced_works`。**field-REQUIRE は実測 net-negative（GNN×創薬で 2,377→1,695・異分野クロス掲載を削る）ゆえデフォルト不採用**、消費先＝ホームドメイン除外（Phase 2/3）。
*   実データ検証: filter で候補 **68,288→2,377（約28倍タイト）**・上位的中保持、parser 25/25 に field_id・`dominant_field_ids`=17。`tests/test_query.py` 20ケース・全 **227 green**。

### 2026-06-17 MCP 出力のプロンプトインジェクション緩和（untrusted-data エンベロープ）
*   `src/mcp_server.py`: `_wrap_external` / `_external_data_result` を追加。外部由来テキスト（repo README / abstract / description）を返す全ツール結果を `<untrusted_external_data>` で囲い「データであり指示ではない」と明示。埋め込みタグは無害化し早期 close による脱出を防止。
*   対象: byserendipity・byrepo（structured/LLM）・bybridge（structured/raw/LLM）・delegate_finalize。bynote（ユーザ自身のメモ解析）と診断文は対象外。
*   背景監査: contra 本体は読み取り専用（exec 系ゼロ・API 固定・鍵は env のみ）と確認。残るリスクは取得テキスト→エージェントの注入経路に集約されるため出力層で緩和。
*   位置づけ: 「緩和」であって「保証」ではない（エージェント側のツール権最小化・最小権限トークン・本体固定/再監査との多層防御）。`tests/test_mcp_injection.py` に5ケース追加（全 213 件 green）。


### 2026-06-15 ローカル化 段階(d): byrepo/Track A 委譲（委譲シリーズ a-d 完了）
*   `src/pipeline/delegate.py`: `build_track_a_entries`（4-Pillar 信頼性スコア降順の決定論ランク）＋ `assemble_keyless_track_a_document`（→ structured 整形 → OutputDocument）。LLM 不使用。
*   MCP `byrepo_search` に `structured` フラグ追加（信頼性順＋構造整形済み Track A Markdown をキー無しで返す）。
*   設計要点: Track A は選別が決定論（信頼性スコア）のため再ゲート不要＝Track B（delegate_finalize）より単純。
*   `tests/test_delegate.py` に2ケース追加（全 191 件 green）。DECISION_LOG に段階(d)＋シリーズ総括を記録。

### 2026-06-15 ローカル化 段階(c): エージェント採点 JSON スキーマ＋委譲経路
*   `src/pipeline/delegate.py`: エージェント採点候補の JSON 契約（`AGENT_SCORE_REQUIRED`）＋ `work_from_material`/`score_row_from_material`/`normalize_agent_scores`/`finalize_delegated_document`。
*   finalize は採点済み候補を `apply_post_gates`（LLM 不使用で全ゲート再適用）に流し、エージェント提供プローズを優先しつつ欠落は structured 補完 → OutputDocument。
*   MCP ツール `delegate_finalize` を追加（theme＋agent-scored candidates → post-gate 通過分の Markdown＋診断）。
*   `tests/test_delegate.py` に4ケース追加（全 189 件 green）。DECISION_LOG に段階(c)を記録。

### 2026-06-15 ローカル化 段階(b): 数値ゲートの post-gate 純関数化
*   `select_track_b` の決定論ゲートを LLM 採点/judge から分離。`_serendipity_scored`（anomaly＋near-cap＋serendipity）/ `_hollow_filter`（hollow 棄却・fail-open）/ `_quality_gate_and_build`（percentile→output_floor→fallback/M3→MMR→構築）を共有純関数化。
*   `apply_post_gates` を新設＝エージェント採点（purpose_sim/mechanism_dist/structural_depth/has_causal_pm 等）に対し LLM 不使用で全ゲートを再適用する委譲用 post-gate。
*   `select_track_b` も同じ純関数を呼ぶよう refactor（ゲート実装を一本化、挙動不変）。スコア設計値は不変。
*   `tests/test_post_gates.py` に6ケース追加（全 185 件 green）。DECISION_LOG に段階(b)を記録。

### 2026-06-15 ローカル化 段階(a): bybridge キー無し structured 一周
*   新モジュール `src/pipeline/delegate.py`（純関数）: 決定論選別（near_domain でマイオピア pre-filter ＋共有 bridge 数で順位付け）→ `fill_track_entries(mode="structured")` で 4部構成を充足 → OutputDocument。LLM/API キー不使用で一周完結。
*   distance_score は L0/L1 Jaccard から決定論算出。structure/serendipity は LLM 判定待ちで 0.0（委譲先エージェントが補充）。
*   MCP `bybridge` に `structured` フラグ追加（`raw_only=true, structured=true` でキー無し 4部 Markdown）。既存経路は非破壊。
*   `tests/test_delegate.py` に4ケース追加（全 179 件 green）。DECISION_LOG に委譲方式の採用＋段階(a)を記録。

### 2026-06-15 Phase 1 Done 評価ルーブリックの整備（docs/quality_eval.md 刷新）
*   旧「20本レポート（100/200/200 比率・無関係4章）」前提の観点リストを、現行 contrarian 方針（MVP = Track B の良質な1本・4部構成）へ全面刷新。
*   Done 定義（spec.md §8）・評価対象5テーマ・再現コマンド（`--single --llm-model claude-haiku-4-5 --score-votes 3`）・1本ごとの観点（RELATIONSHIP/SUMMARY/HYPOTHESIS/CAUTION/再現性）・記入式テーマ横断ルーブリック表・Done 成立条件を定義。
*   実 LLM 生成が必要なため「人間/Codex が API キー在席で実行して埋めるテンプレート」として機能。コード変更なし（テスト 111 件 green 維持）。

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
*   構成点検レポート作成（`docs/archive/structure_inspection_2026-06-01.md`）。
*   **A（ドキュメント同期）**: README.md 全面改稿（contrarian CLI・Track B 中核・実装済み機能）。spec.md: ディレクトリ図・生成モード・§6 落とし穴（実装済みに訂正）・§7 決定ログ（R2/R3/R5/M3）・§8 未解決リスト を現状に同期。
*   **B（デッドコード削除）**: 旧 surface×structure スコアリング・classify_stub・generate_entries（3行生成）・build_minimal_document・domain_distance 等を削除。未使用 import を除去。
*   **C（ドキュメント重複解消）**: docs/ 直下の重複 3 ファイルを削除（正本は docs/specs/ に統一）。
*   **D（テスト補強）**: 数値捏造ガード・export レンダリング・input_schema・history の単体テストを追加。合計 71 件 green。

### 2026-05-30 Git公開準備
*   生成済み `output/` を Git 管理対象から外し、今後の実行結果が公開差分に混ざらないよう `.gitignore` に追加。

### インフラ（再利用可能・変更不要）
*   入力仕様の最小セットを確定（`docs/archive/input_min_spec.md`）
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
