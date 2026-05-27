# 作業タスクリスト

`roadmap.md`からブレークダウンした、具体的な作業タスクを管理します。

---

## 作業中 (In Progress)

*   なし

---

## 未着手 (To Do)

*   GeminiCLIで関係性/要約/注意点を更新する後処理フロー設計
*   Plan B（LLM）出力→GeminiCLI後処理の実行手順を整備

---

## 完了 (Done)

*   入力仕様の最小セットを確定（`docs/input_min_spec.md`）
*   入力仕様のスキーマ草案を作成（`input_schema.md`）
*   入力→内部表現のスキーマ定義（`src/core/input_schema.py`, `src/core/models.py`）
*   OpenAlex収集の最小API設計メモを作成（`openalex_api_memo.md`）
*   OpenAlex APIの最小利用方針を整理（必須フィールド・取得順）
*   OpenAlex検索クエリ設計（入力→検索語の生成ルール）
*   OpenAlex検索クエリの拡張（include/exclude/field/goalの重み付け）
*   OpenAlexページング/レート制御の方針確定
*   OpenAlexリトライ/バックオフ方針の策定
*   OpenAlex重複排除ポリシー（ID/DOI重複の扱い）
*   OpenAlexレスポンスのフィールド欠損ポリシー定義
*   OpenAlex abstract復元失敗時の扱い
*   OpenAlex結果の停止条件（十分数/低関連/空ページ）
*   収集パイプライン雛形（検索→候補→フィルタ）を作成
*   abstractあり優先のフィルタ実装
*   取得数制御（合計500本）と過不足時の補充ルール設計
*   関連/広域/無関係の分類ルールを定義（判定軸と比率）
*   無関係論文セクションの4章割り当てロジック設計
*   3行構成テンプレートの生成ルール定義（関係性/要約/注意点）
*   1テーマ=1Markdownの出力整形（ファイル名規則含む）
*   収集→分類→生成→出力の接続作業（CLI通常フローに統合）
*   収集結果をMarkdown出力へ反映（collect→classify→generate→export）
*   OpenAlex収集ありのE2E実行確認（theme.json）
*   Plan A/Bの並立は廃止し、Plan BをベースにGeminiCLIで仕上げる方針に変更
*   出力Markdownのセクション構成を具体化（`output_markdown_spec.md`）
*   出力Markdownのセクション構成を確定（`src/core/output_spec.py`）
*   CLI実行手順を`memo.md`に追記
*   Phase 1 CLI雛形を作成（`scripts/`, `src/`, `docs/`）
*   サンプルテーマ3件の生成・レビュー（`data/samples/`, `output/sample_*`）
*   品質評価観点の整理（`docs/quality_eval.md`）
