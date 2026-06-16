# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 2026-06-16 byrepo DOI threshold 複数テーマ較正

## 1. 変更目的 (必須)

*   DOI source の visible problem match threshold が厳しすぎる / 緩すぎる問題を、複数テーマの実API smoke で較正する。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/core/models.py`, `src/pipeline/artifact_collect.py`, `tests/test_artifact_collect.py`, `docs/specs/byrepo_problem_solution_fit_spec.md`, `task.md`, `diff.md`, `Changelog.md`
*   `title_description_problem_terms` / `title_description_problem_term_count` を追加し、DataCite では metadata subject ではなく title / description に見える問題語数で threshold を判定するようにした。
*   DataCite は multi-term theme で原則2語以上、paper-only record は最大3語まで要求する threshold にした。
*   Zenodo は files を持つ artifact が多いため、non-paper artifact は title / description / tags のどれかに1語以上見えれば残す source-specific threshold とした。

---

## 3. 確認方法 (必須)

*   `C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall src tests`
*   対象モックテスト直接実行: `tests.test_git_collect` / `tests.test_artifact_collect` / `tests.test_problem_search` / `tests.test_export_render`
*   実API smoke test: 医療画像 / エネルギー / ロボティクス / NLP の4テーマで Zenodo / DataCite を比較した。

---

## 4. 既知の課題・リスク (必須)

*   DataCite は厳しく絞られるため recall が下がる可能性がある。
*   Zenodo は recall 維持のため1語 visible match を許容しており、source-specific な追加較正余地が残る。

---

## 5. 変更内容の詳細 (任意)

*   実API smoke では DataCite の energy 系 broad `digital twin` 1語候補が除外され、NLP の `BERT / text classification / domain shift` 全一致候補は残ることを確認した。

---

## 2026-06-16 byrepo DOI field-level 問題一致改善

## 1. 変更目的 (必須)

*   Zenodo / DataCite の metadata subject だけで問題一致した広い候補を抑え、title / description / tags に問題語が見える候補を優先する。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/core/models.py`, `src/pipeline/artifact_collect.py`, `src/pipeline/practical_collect.py`, `src/mcp_server.py`, `tests/test_artifact_collect.py`, `docs/specs/byrepo_problem_solution_fit_spec.md`, `task.md`, `diff.md`, `Changelog.md`
*   `PracticalArtifact` に `field_problem_score` / `title_problem_score` / `description_problem_score` を追加した。
*   DOI source では title / description / tags の問題語一致を rank に入れ、metadata-only problem match を `use_problem_search=True` で除外するようにした。
*   unified collector と MCP `byrepo_search` の rank でも `field_problem_score` を見るようにした。

---

## 3. 確認方法 (必須)

*   `C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall src tests`
*   対象モックテスト直接実行: `tests.test_git_collect` / `tests.test_artifact_collect` / `tests.test_problem_search` / `tests.test_export_render`
*   実API smoke test: 同じ BERT テーマで DataCite を確認し、metadata-only の広い candidate が除外されることを確認。

---

## 4. 既知の課題・リスク (必須)

*   DataCite の候補が厳しく絞られるため、複数テーマで source type 別 threshold の較正が必要。

---

## 5. 変更内容の詳細 (任意)

*   field-level score は title を最重視、description を次点、tags を補助として計算する。

---

## 2026-06-16 byrepo DOI artifact 精密化

## 1. 変更目的 (必須)

*   Zenodo / DataCite の DOI record で paper-only record と実 artifact が混ざる問題を抑え、Track A practical anchor を「触れる成果物」寄りにする。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/core/models.py`, `src/pipeline/artifact_collect.py`, `src/pipeline/practical_collect.py`, `src/mcp_server.py`, `tests/test_artifact_collect.py`, `docs/specs/byrepo_problem_solution_fit_spec.md`, `task.md`, `diff.md`, `Changelog.md`
*   `PracticalArtifact` に `artifact_kind_score` / `artifact_kind_label` を追加した。
*   `resource_type`, files, related identifiers, code link, dataset/software/model 語から artifact kind を評価し、Dataset / Software / Model / files / code link を持つ record を優先するようにした。
*   Text / publication / preprint だけで files や related identifiers がないものを `paper_only` として risk penalty を加え、artifact / unified / MCP rank で後ろに回すようにした。

---

## 3. 確認方法 (必須)

*   `C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall src tests`
*   対象モックテスト直接実行: `tests.test_git_collect` / `tests.test_artifact_collect` / `tests.test_problem_search` / `tests.test_export_render`
*   実API smoke test: 同じ BERT テーマで DataCite を確認し、`paper_only` record が non-paper artifact より後ろに回ることを確認。

---

## 4. 既知の課題・リスク (必須)

*   DataCite では Dataset record でもテーマから広い候補が残るため、title / description の問題語重み付け改善は別タスクとして残す。
*   `artifact_kind_score` は触れる成果物かどうかの補助評価であり、問題一致そのものの代替ではない。

---

## 5. 変更内容の詳細 (任意)

*   実API確認では `Meta-Tsallis-Entropy...` などの paper-only record が `paper_only` と判定され、DataCite rank 上位から下がることを確認した。

---

## 2026-06-16 byrepo GitHub recall 改善

## 1. 変更目的 (必須)

*   `use_problem_search=True` の厳格な問題一致フィルタにより、GitHub repository が 0 件になりやすいケースを緩和する。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/pipeline/problem_search.py`, `src/pipeline/git_collect.py`, `src/core/models.py`, `tests/test_git_collect.py`, `tests/test_problem_search.py`, `docs/specs/byrepo_problem_solution_fit_spec.md`, `task.md`, `diff.md`, `Changelog.md`
*   GitHub repository search に `problem_specific_relaxed` / `problem_pair_relaxed` fallback query を追加し、strict query で候補が偏る場合でも問題語に沿った repository を拾えるようにした。
*   `GITHUB_TOKEN` がある場合のみ GitHub code search を補助的に使い、code search result の repository を詳細取得して通常の repository scoring / ranking に流すようにした。
*   code search で見つかった path を `GitRepository.code_search_paths` と `Work.source_meta["code_search_paths"]` に保存し、Problem-Solution Fit の text evidence に含めるようにした。

---

## 3. 確認方法 (必須)

*   `C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall src tests`
*   対象モックテスト直接実行: `tests.test_git_collect` / `tests.test_artifact_collect` / `tests.test_problem_search` / `tests.test_export_render`
*   GitHub code search 実API確認: 未認証では 401 になることを確認し、token なしでは code search をスキップする仕様にした。

---

## 4. 既知の課題・リスク (必須)

*   `GITHUB_TOKEN` ありの code search smoke test は未実行。
*   code search は現時点では repository recovery と path evidence までで、ファイル内容・snippet の直接抽出は未実装。
*   unauthenticated GitHub repository search は rate limit に到達しやすく、実APIでの旧新比較は rate limit 回復後または token ありで再確認が必要。

---

## 5. 変更内容の詳細 (任意)

*   GitHub code search API は未認証で 401 を返すため、未認証運用の主 recall 改善は repository relaxed fallback query とした。

---

## 2026-06-16 byrepo 残タスク整理

## 1. 変更目的 (必須)

*   これまでの会話で明示的に後回し・未実装となっている byrepo 改善項目を、次回以降に拾えるよう `task.md` に整理する。

---

## 2. 変更概要 (必須)

*   変更ファイル: `task.md`, `diff.md`, `Changelog.md`
*   byrepo 名称変更、LLM 支援 `ProblemSearchPlan`、GitHub code search、issue / discussion 検索、GitHub recall 改善、Zenodo / DataCite 精密化、複数テーマでの score 較正を To Do に追加した。

---

## 3. 確認方法 (必須)

*   `Get-Content -Path task.md`

---

## 4. 既知の課題・リスク (必須)

*   今回はタスク整理のみで、実装変更は行っていない。

---

## 5. 変更内容の詳細 (任意)

*   会話上の「手つかずになっている部分」を、Track A byrepo の残タスクとして粒度を揃えて追加した。

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
