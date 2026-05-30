# 作業タスクリスト

`roadmap.md`からブレークダウンした、具体的な作業タスクを管理します。

---

## 作業中 (In Progress)

### Step 7: サンプル生成・品質評価
*   複数テーマで実行し、「遠いが構造一致」の1本が出るか評価
*   Anomaly（無意味接続）・近接（マイオピア）が混入しないことを確認
*   「役に立つ可能性の仮説」が論文固有で汎用文になっていないか確認
*   進捗: casual_puzzle テーマで `--single` のE2E成功（IDC theory「興味のループ」をスコア0.63で選出、4部構成出力を確認）

---

## 未着手 (To Do)

> 2026-05-30 のMVP E2E成功後に判明した較正・検証タスク。詳細は [`plan.md`](plan.md) §6。

### Step 9 (B): 複数本モードの挙動検証
*   `--track-b-count 10` 等で質ゲート通過数を確認し、「20本程度」のボリュームが質を保てるか検証
*   閾値 `--serendipity-gate` の妥当な水準を複数テーマで探る
*   通過数が少なすぎ／多すぎる場合のゲート・チャンク上限（`_SCORE_MAX_CANDIDATES`）の調整

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
*   `spec.md`（AI向け開発仕様書）を新規作成

### 2026-05-30 方針再定義（contrarian 中核化）
*   セレンディピティ発生条件をNotebookLM Deep Research（66ソース）で調査・一次資料化（`docs/research/serendipity_conditions.md`）
*   MVPを「20本レポート」から「**Track B の良質な1本**」へ再定義（本数は質ゲートの出力）
*   Track Bを中核・Track Aをアンカーに再配置、選別を距離×構造の乗算に、出力を4部構成に復活
*   `plan.md`・`spec.md`・`roadmap.md`・`task.md` を新方針に全面更新
*   実装済み: 撤回論文フィルタ、Track B複数ドメインクエリ、assumptionsクエリ、ドメインペナルティ（旧20本構造上での先行修正）

### Step 8 (A): 距離スコアの較正（2026-05-30 完了）
*   `_score_b_chunk` プロンプトに較正アンカーを追加し、隣接行動ドメイン（教育・gamification）が0.3-0.5にマッピングされるよう修正（旧来の距離0.9超えを解消）
*   `select_track_b` に `_ADJACENT_DOMAIN_TERMS` × `_ADJACENT_SURFACE_BUMP(+0.25)` のペナルティを追加し、収集段階で漏れた隣接論文を選別段階でも除減
*   `_llm_generate_track_b_text` のユーザープロンプトを「論文先頭・テーマ後置」に再構成し、Abstract固有の数値・発見引用を必須化（テーマの不安点の言い換え禁止を明示）
*   `--single` にて casual_puzzle / energy の2テーマで改善を確認（距離0.6-0.7、energy論文で論文固有数値の引用を確認）

### 2026-05-30 MVP実装（Step 2〜6 完了・E2E成功）
*   Step 2: `collect.py` の Track Bクエリを「別ドメイン概念 × テーマ核心語」の掛け合わせ式に（`generate_track_b_queries`, `_theme_anchor`）
*   Step 3: `classify.py` に `select_track_b`（距離×構造の乗算、Anomaly棄却 `_STRUCTURE_MIN`、近接棄却 `_SURFACE_MAX`、質ゲート `_SERENDIPITY_GATE`）。スコアリングはチャンク分割でAPIタイムアウト回避
*   Step 4: `generate.py` を4部構成に（`_llm_generate_track_a/b_text` が4要素タプル、`usefulness_hypothesis` 追加）
*   Step 5: `main.py` に `--single`/`--track-b-count`/`--track-a-count`/`--serendipity-gate`。Track Aは任意アンカー化
*   Step 6: `output_spec.py` の `_render_4part_body` でSUMMARY/RELATIONSHIP/HYPOTHESIS/CAUTIONを出力。`gemini_materials.jsonl` も4部構成＋スコア対応
*   `models.py` の `OutputEntry` に距離/構造/セレンディピティスコアと `usefulness_hypothesis` を追加（非破壊）
