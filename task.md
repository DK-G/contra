# 作業タスクリスト

`roadmap.md`からブレークダウンした、具体的な作業タスクを管理します。

---

## 作業中 (In Progress)

（なし）

---

## 未着手 (To Do)

（なし）

---

## 完了 (Done)

### Step 9 (B): 複数本モードの品質再設計（2026-05-30 完了）
*   Track B 選別を SOLVENT の Purpose-Mechanism スキーマで再構築。`_score_b_chunk_pm` で structure abduction（P/M先抽出→比較）を実装。
*   serendipity = purpose_sim × mechanism_dist（乗算）に変更。テーマ別 analogy-poor 検出（`_extract_theme_schema`）を追加。
*   `concept_distance.py` を Wu-Palmer 近似の L0/L1 Jaccard 階層距離に刷新（`ThemeProfile`）。near_domain_signal で同分野論文の mechanism_dist を 0.5 にキャップし false-serendipity を抑制。
*   質ゲートを固定 0.25 → テーマ別 percentile-top30%（絶対下限 0.20）に変更。MMR 多様性再ランキング・0件 fallback を実装。
*   `_PURPOSE_SIM_MIN` 0.25 → 0.40 に引き上げ（抽象カテゴリ一致の排除）。
*   検証（4テーマ）: energy=Digital Twin 選出（power-grid 近接なし ✓）、casual=5件（複数本 ✓）、social=量子情報拡散 serendipity=0.56（最高品質の遠類推 ✓）、wind=海洋循環・気候経済（4件）。
*   wind/social は analogy-poor でなく approach_type:experiment の測定テーマゆえ正しく analogy-rich と判定（前セッションの analogy-poor 予測は旧スコアリングのバグによる誤診と確認）。

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
