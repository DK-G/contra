# 構成点検レポート — plan.md の目的に照らした全体構成の適合性

- **点検日**: 2026-06-01
- **対象**: `contra` リポジトリ（`main` ブランチ、全ブランチ統合後の状態）
- **基準**: [`plan.md`](../../plan.md)（マスター仕様書）に記された目的・設計原則
- **観点**: 「全体の構成（アーキテクチャ・ドキュメント・コード配置）が、plan.md の目的に対して適切か」
- **スコープ外**: セキュリティ監査・網羅的なバグ探索（必要なら別途 `/security-review` 等で実施）

---

## 0. 総評

**コアの実装はplan.mdの思想と高い精度で一致している。** 「遠いが構造的に接続する論文を対置する（contrarian）」という中核思想は、収集→選別→提示の3段パイプラインに正しく落ちている。Track B を主役にした SOLVENT 方式の選別、4部構成生成、質ゲート（本数＝出力）、マイオピア棄却、飽和検知まで、plan.md の §2〜§10 が実コードに対応する。テストも新パイプラインの中核を 30 件で網羅し、全て green。

**一方で、ドキュメント層が実装に追従できておらず、構成全体の「読み取りやすさ・信頼性」を損なっている。** 特に `README.md` と `spec.md` の一部は **2026-05-30 の方針再定義（contrarian 中核化）以前の旧フレーミング**のまま残り、実装と正面から矛盾する記述がある。加えて旧設計の**デッドコード**が各モジュールに残存している。

→ **コード＝適切、ドキュメント＝要同期、旧コード＝要整理**、が結論。重大なのは A 群（ドキュメント乖離）。

---

## 1. 目的との適合（良好な点）

plan.md の各要件が、実装の以下に対応していることを確認した。

| plan.md の要件 | 対応する実装 | 評価 |
|---|---|---|
| §6 3段パイプライン（収集→選別→提示） | [`main.py`](../src/cli/main.py) のオーケストレーション（collect→select→generate→export） | ✅ 一致 |
| §6.2 距離 × 構造の乗算・両端棄却・Anomaly強制棄却 | [`select_track_b()`](../src/pipeline/classify.py)（`serendipity = purpose_sim × mechanism_dist`、SOLVENT） | ✅ 一致 |
| §5.2 本数は「出力」（質ゲート方式） | percentile-gate + `output_floor` + count上限（[`classify.py`](../src/pipeline/classify.py) Step4） | ✅ 一致 |
| §7 4部構成（概要/関連性/役に立つ可能性の仮説/注意点） | [`output_spec._render_4part_body()`](../src/core/output_spec.py) / [`generate.fill_track_entries()`](../src/pipeline/generate.py) | ✅ 一致 |
| §3 最適認知距離・マイオピア棄却 | [`near_domain_signal()`](../src/pipeline/concept_distance.py) による `mechanism_dist` キャップ | ✅ 一致 |
| §6.1 別ドメイン概念 × 構造的側面・ドメイン多様化・撤回除外 | [`generate_track_b_queries()`](../src/pipeline/collect.py) / citation 2-hop / MAX-MIN 多様化 | ✅ 一致 |
| §10 テーマ別履歴管理（重複回避） | [`history.py`](../src/pipeline/history.py) + main.py の used_ids/titles/dois 除外 | ✅ 一致 |
| §1.3 MVP = Track B 1本 | `--single` フラグ（main.py） | ✅ 一致 |
| 誤った弱接続での水増し抑止 | M3 飽和ノート（`_write_saturation_report`、`diag` テレメトリ） | ✅ 思想に忠実 |
| §11 技術構成（stdlib中心・依存最小） | 外部依存なし、`urllib` ベース、`compileall` OK | ✅ 一致 |

- **テスト**: 30件 green（PM採点の median 集約、judge 投票、MAX-MIN、M3飽和、citation 2-hop、purpose_level 解析）。新パイプラインの中核を押さえている。

---

## 2. 構成上の問題点

### A. ドキュメントと実装の重大な乖離 〔重要度: 高〕

#### A-1. `README.md` が旧「Webサービス」フレーミングのまま
- [`README.md`](../../README.md) のタイトルが「論文ブレインストーミング支援**Webサービス**」、本文も「ブレインストーミング工程を支援する**Webサービス**のドキュメントとデータを管理します」。
- これは plan.md §1.1 が**置き換えた当の旧定義**。現行の plan.md は「個人の思考ツール（CLI）」「contra = contrarian」「Track B 中核」「MVP=1本」「Web化は §12 将来構想」と明記している。README にこれらの核心が**一切登場しない**。
- さらに README が参照する `inspection-list.md`（L20）と `docs/AI_AGENT_WORKFLOW.md`（L23）は**いずれも存在しない**（参照切れ）。

#### A-2. `spec.md` の §3/§4/§6 が実装より前の状態を記述
- §3 アーキテクチャ: `classify.py` を「`classify_stub`: キーワードスコアで分類（**現在スタブ**）」、`generate.py` を「**3行生成**」と記述。実際は `select_track_b`（SOLVENT 本実装）・4部生成済み。
- §3 ディレクトリ図に [`concept_distance.py`](../src/pipeline/concept_distance.py) と [`history.py`](../src/pipeline/history.py) が**欠落**。
- §6「既知の落とし穴」が「**選別の乗算スコアが未実装**」「**生成が3行構成のまま**」「**本数が固定(10/10)のまま**」と明記。**いずれも実装済み**で、同じ spec.md の §7 決定ログ（Step 9）と**自己矛盾**している。
- §4「`classify_stub` をスタブから本実装に勝手に変更するな」という禁則も、現状（本実装が別関数 `select_track_b` に存在し stub は孤立）と噛み合わない。

#### A-3. 決定ログの数値が最新チューニングより前で停止
- §7 決定ログは「`_PURPOSE_SIM_MIN` を 0.25 → **0.40** に引き上げ」と記載。実コードは **0.20**（[`classify.py`](../src/pipeline/classify.py) の `_PURPOSE_SIM_MIN`、R5 でディスクリート化＋緩和）。
- 決定ログが R2/R3/R5（percentile gate・purpose のレベル離散化・self-consistency 投票・hollow judge）**以前で止まっている**。コード側のインラインコメントには R2〜R5 の経緯が厚く残っているため、spec への反映漏れ。

> **影響**: spec.md は「新セッション開始時に最初に読み込ませる AI 向け仕様書」と自称している（spec.md 冒頭）。その文書が「未実装」と書いている機能が実は実装済み、という乖離は、AI エージェント／新規参加者を**確実に誤誘導する**。最優先で同期すべき。

---

### B. 旧設計のデッドコード残存 〔重要度: 中〕

新パイプライン（`select_track_b` 系）への移行後、旧実装が削除されず残っている。`compileall` は通り害はないが、構成の見通しを悪くし、A の混乱を助長する。

| 残骸 | 場所 | 状態 |
|---|---|---|
| `_score_b_chunk` / `_score_b_candidates`（旧 surface×structure 採点） | [`classify.py`](../src/pipeline/classify.py) | 呼び出し元なし（現行は `_score_b_candidates_pm`） |
| `classify_stub` / `ClassifiedWorks`（旧500本分類） | [`classify.py`](../src/pipeline/classify.py) | main.py で **import のみ・未使用** |
| `generate_entries` + 3行生成系（`_llm_generate`/`_relationship`/`_summarize`/`_structured_*`） | [`generate.py`](../src/pipeline/generate.py) | main.py で **import のみ・未使用**（現行は `fill_track_entries`） |
| `build_minimal_document` / `_mock_entry` + legacy render 分岐（旧7セクション500本） | [`output_spec.py`](../src/core/output_spec.py) | 呼び出し元なし |
| `domain_distance`（export 済みだが未使用。利用は `near_domain_signal` のみ） | [`concept_distance.py`](../src/pipeline/concept_distance.py) | 未使用 |

- 派生: [`main.py`](../src/cli/main.py) の import 行に未使用シンボル（`classify_stub`, `generate_entries`）。
- 注意: `classify_track_b`（classify.py）は `--gen-mode` が `llm` 以外のときの非LLMフォールバックとして `select_track_b` 内から到達するため、**デッドではない**（残す）。

---

### C. ドキュメントの重複・配置の混在 〔重要度: 中〜小〕

- **重複**: `docs/input_schema.md` と `docs/specs/input_schema.md` が**完全一致**。`output_markdown_spec.md` / `openalex_api_memo.md` は `docs/` と `docs/specs/` で**内容が異なり**、どちらが正本か不明。
- **ルート直下の運用足場の混在**: `AGENT_COORDINATION.md` / `Gemini.md` / `TOOL_CONFIG_GUIDE.md` / `agent.md` / `diff.md` / `memo.md` / `review.md` / `Changelog.md` ＋ `Template/` が、プロジェクト本体（`plan/spec/roadmap/task` + `src/`）と同階層に並ぶ。エージェント運用フレームの足場と成果物が同列で、新規読者には本体の所在が分かりにくい。

> 本レポートを `docs/` 配下に置いたのも、ルートをこれ以上混雑させない判断による。

---

### D. テストカバレッジの空白 〔重要度: 中〕

新パイプラインの中核（選別・収集）は厚いが、**出力品質に直結する経路にテストがない**。

- **未カバー**: 4部生成（`generate.fill_track_entries`）、特に**数値捏造ガード**（`_unsupported_numbers` … Abstract に無い数値を hypothesis に書かせない仕組み。plan.md §7「汎用文禁止」「忠実な概要」の要）、export レンダリング（`output_spec.render_markdown`）、入力バリデーション（`input_schema`）、履歴の読み書き（`history`）。
- 統合テスト（モックLLMでの select→generate→export 一気通し）なし。LLM 依存ゆえ難しいが、捏造ガードは純粋関数なので単体テスト可能。

---

### E. 軽微 〔重要度: 低〕

- spec.md §2/§3 の「LLM（3行生成）」「3行生成」表記（4部構成へ）。
- `plan.md` 自体は最新で良好。基準文書として妥当に機能している（点検の拠り所として問題なし）。

---

## 3. 推奨アクション（優先度順）

1. **[最優先・対外] `README.md` を全面改稿**
   contrarian 中核 / CLI 個人ツール / MVP=1本 / Track B 主役 を反映。存在しないファイル参照（`inspection-list.md`, `docs/AI_AGENT_WORKFLOW.md`）を除去または作成。

2. **[高] `spec.md` を実装状態に同期**
   §6 の「未実装」3項目（乗算スコア／4部構成／可変本数）を「実装済み（Step 9）」へ。§3 ディレクトリ図に `concept_distance.py`・`history.py` を追加し、`classify.py`／`generate.py` の説明を現行（`select_track_b`／4部生成）へ更新。§4 の `classify_stub` 禁則を見直し。決定ログに R2/R3/R5 と現行閾値（`_PURPOSE_SIM_MIN=0.20` 等）を追記。

3. **[中] デッドコードを削除 or `legacy/` へ隔離**
   §2-B の表の各シンボル。最低でも `main.py` の未使用 import（`classify_stub`, `generate_entries`）を除去。`classify_track_b` は残す。

4. **[中] `docs/` の重複解消**
   `docs/` と `docs/specs/` を一本化（正本を決め、もう一方は削除かリンク化）。

5. **[中] テスト補強**
   数値捏造ガード（`_unsupported_numbers`）、export レンダリング、`input_schema`、`history` に単体テストを追加。

---

## 付録: 点検方法

- plan.md / spec.md / roadmap.md / README.md を精読し、`src/` 全モジュール（`cli/main.py`, `core/*`, `openalex/*`, `pipeline/*`）と `tests/` を読解。
- `git ls-files` で生成物（`output/`, `data/history/`）が **追跡対象外**（.gitignore 済み・コミット汚染なし）であることを確認。
- `python -m compileall src` で全ソースのコンパイル成功を確認。
- `python -m pytest` で 30件 green を確認。
- デッドコードは grep による呼び出し元の全数確認で判定。
