# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 2026-06-16 byrepo Problem-Solution Fit 実装

## 1. 変更目的 (必須)

*   `byrepo` がキーワード一致や信頼性スコアだけでなく、「ユーザーの問題解決に資する候補」を優先できるようにする。
*   クエリ群の単位と、運用時に解釈の幅が出る判断を仕様書にまとめる。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/pipeline/problem_search.py`, `src/pipeline/git_collect.py`, `src/pipeline/artifact_collect.py`, `src/pipeline/practical_collect.py`, `src/core/models.py`, `src/core/output_spec.py`, `src/cli/main.py`, `src/mcp_server.py`, `tests/test_problem_search.py`, `tests/test_git_collect.py`, `tests/test_artifact_collect.py`, `docs/specs/byrepo_problem_solution_fit_spec.md`, `task.md`, `diff.md`, `Changelog.md`
*   `ThemeInput -> ProblemSearchPlan -> QuerySpec(source type × intent)` の検索計画層を追加した。
*   GitHub / GitLab / Hugging Face / Zenodo / DataCite collector を `use_problem_search=True` で複数 query bundle に対応させた。
*   `Problem-Solution Fit Score` と `matched_problem` / `solution_mechanism` / `usable_artifact` / `visible_constraint` を `source_meta` に保存し、Markdown / MCP 出力に表示するようにした。
*   unified collector の rank を `(problem_match_score, problem_solution_fit_score, reliability_score)` に変更した。
*   クエリ群の単位、source type 別の扱い、人気指標・awesome list・demo・DOI record など解釈が割れる点を仕様書へ明文化した。

---

## 3. 確認方法 (必須)

*   `C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall src tests`
*   対象モックテスト直接実行: `tests.test_git_collect` / `tests.test_artifact_collect` / `tests.test_problem_search` / `tests.test_export_render`
*   実API smoke test: 同じ BERT テーマで `use_problem_search=False` / `True` を比較し、問題一致候補が上位に来ることを確認。
*   `git diff --check`

---

## 4. 既知の課題・リスク (必須)

*   `ProblemSearchPlan` は現時点ではヒューリスティック抽出。LLM 支援の facet 抽出は未実装。
*   GitHub code search / issue search を使った file/path evidence と実運用 issue evidence は未実装。
*   実API smoke test では DataCite / Zenodo の汎用AI artifact が混ざるケースがまだあり、複数テーマで score weight の較正が必要。
*   `pytest` は同梱 Python に未導入のため未実行。

---

## 5. 変更内容の詳細 (任意)

*   クエリ群の単位は「リポジトリ」でも「1件のみ」でもなく、`ThemeInput` に紐づく `source type × intent` とした。
*   `Problem Match` が 0 の候補は fit score を最大15に抑え、rank の第一キーも `problem_match_score` にして、問題一致の弱い artifact が上位を占めるのを避ける。
*   `awesome` / tutorial / course / link list 系 repository は practical anchor ではなく discovery seed と見なし、fit score を抑える。
*   `use_problem_search=True` の source collector では `Problem Match` が 0 の候補を返さないようにし、GitHub の awesome/list 系や GitLab / DataCite の汎用候補を Track A から除外する。
*   `bert-text` / `digital-twin` のようなハイフン区切り表記を、空白区切りの問題語と同等に扱う。
*   同じ BERT テーマで GitHub / GitLab / Hugging Face / Zenodo / DataCite を source 別比較し、GitLab のノイズ除外、Hugging Face の表記揺れ対応、DataCite の問題一致ゼロ候補除外を確認した。
*   CLI の Track A 収集経路と MCP `byrepo_search` 経路で、新検索方式が `use_problem_search=True` として有効化されることを direct test で固定した。
*   `use_problem_search=True` では最初の query で上限に達しても打ち切らず、intent ごとに候補を集めてから rerank するよう変更した。
*   非 Git source の focused query は上位3つの `problem_terms` を使い、`problem_only` は上位2語の fallback として最後に回すよう変更した。
*   同一 BERT テーマの旧新比較で、新方式は `Meta-Tsallis-Entropy Minimization`（BERT / text classification / domain shift 全一致, `pm=25`）を1位にし、旧方式に残った `pm=0` 候補を除外することを確認した。

---

## 2026-06-16 byrepo 問題解決リポジトリ発見戦略調査

## 1. 変更目的 (必須)

*   `byrepo` の精度向上に向けて、キーワード一致ではなく「ユーザーの問題解決に資する repository / artifact」を見つけるための方法論を整理する。

---

## 2. 変更概要 (必須)

*   変更ファイル: `docs/research/byrepo_problem_solution_discovery.md`, `task.md`, `diff.md`, `Changelog.md`
*   NotebookLM ノート `Contra byrepo OSS Discovery Strategy` を使い、既存ソースと補助Web調査から `Problem-Solution Fit`、evidence-seeking query expansion、source type 別検索戦略を整理した。
*   NotebookLM に追加ノート `2026-06-16 byrepo problem-solution repository discovery strategy` を作成した。

---

## 3. 確認方法 (必須)

*   `Get-Content -Raw docs/research/byrepo_problem_solution_discovery.md`
*   NotebookLM note 作成結果: `86d8abad-e2e7-4bb9-a9fb-74ebf7f89d24`

---

## 4. 既知の課題・リスク (必須)

*   今回は調査・設計メモのみで、`Problem-Solution Fit` の実装は未着手。
*   NotebookLM の追加 Deep Research は開始できたが、即時 import では新規ソースが見つからなかったため、既存ノートソースと補助Web調査を根拠にした。

---

## 5. 変更内容の詳細 (任意)

*   次の実装候補として `ProblemSearchPlan` 生成、source type 別 query bundle、`problem_solution_fit_score`、`matched_problem` / `solution_mechanism` / `usable_artifact` / `visible_constraint` の `source_meta` 保存を提案した。

---

## 2026-06-16 Track A practical anchor sources 拡張

## 1. 変更目的 (必須)

*   `byrepo` の名称は維持したまま、検索対象を GitHub repository だけでなく GitLab / Hugging Face / Zenodo / DataCite へ拡張する。
*   Git repository と model / dataset / research artifact を同じ評価軸に押し込まず、source type 別の信頼性評価で Track A practical anchors に流す。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/core/models.py`, `src/gitlab/client.py`, `src/pipeline/git_collect.py`, `src/pipeline/artifact_collect.py`, `src/pipeline/practical_collect.py`, `src/core/output_spec.py`, `src/pipeline/generate.py`, `src/cli/main.py`, `src/mcp_server.py`, `tests/test_git_collect.py`, `tests/test_artifact_collect.py`, `README.md`, `plan.md`, `docs/agent_rules/byrepo.md`, `task.md`, `diff.md`, `Changelog.md`
*   GitLab Projects API client と GitLab repository 正規化を追加し、`GitCollectConfig(include_gitlab=True)` で GitHub と同じ repository anchor フローに合流できるようにした。
*   Hugging Face / Zenodo / DataCite の artifact collector を追加し、card / metadata completeness、license、activity、adoption、linkage、risk penalty で評価するようにした。
*   CLI / MCP の Track A 収集を unified practical collector に切り替え、DOI / URL / 正規化 title で重複排除するようにした。

---

## 3. 確認方法 (必須)

*   `C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall src tests`
*   対象モックテスト直接実行: `tests.test_git_collect` / `tests.test_artifact_collect`
*   既存出力レンダリング直接実行: `tests.test_export_render`
*   実API smoke test: GitHub / GitLab / Hugging Face / Zenodo / DataCite の各 collector を小件数で実行し、疎通と正規化を確認。
*   実API smoke test: unified practical collector を実行し、複数 source type の統合結果を確認。
*   `pytest` は同梱 Python に未導入のため未実行。

---

## 4. 既知の課題・リスク (必須)

*   実API smoke test は小件数のみ。レートリミット、検索品質、source type ごとのスコア較正は複数テーマで追加確認が必要。
*   DataCite 単体では同一 DOI の重複候補が返ることを確認済み。unified collector 側の DOI / URL / 正規化 title 重複排除で吸収する。
*   名称変更（`byrepo` -> `byanchor` 等）は今回の対象外。

---

## 5. 変更内容の詳細 (任意)

*   `GitRepository` に `provider` / `api_id` を追加し、`github_repository` / `gitlab_repository` を `Work.publication_type` で区別する。
*   `PracticalArtifact` を追加し、`hf_model` / `hf_dataset` / `hf_space` / `zenodo_record` / `datacite_doi` を `Work` に正規化する。
*   Track A Markdown では repository と artifact で表示する score 内訳を分けた。

---

## 1. 変更目的 (必須)

*   Track A と Track B の回し方を named flow として独立定義し、`bynote` のように呼び出し名で扱えるようにする。

---

## 2. 変更概要 (必須)

*   変更ファイル: `docs/agent_rules/byrepo.md`, `docs/agent_rules/byserendipity.md`, `AGENT_COORDINATION.md`, `task.md`, `diff.md`, `Changelog.md`
*   Track A 用 `byrepo` と Track B 用 `byserendipity` を追加し、named flow 一覧へ登録した。

---

## 3. 確認方法 (必須)

*   `Get-Content -Raw docs/agent_rules/byrepo.md`
*   `Get-Content -Raw docs/agent_rules/byserendipity.md`
*   `Get-Content -Raw AGENT_COORDINATION.md`

---

## 4. 既知の課題・リスク (必須)

*   現時点では named flow の定義追加であり、自動ディスパッチ機構そのものは実装していない。

---

## 5. 変更内容の詳細 (任意)

*   `byrepo` は Track A practical anchors、`byserendipity` は Track B contrarian flow の役割を明示的に分離している。

---
