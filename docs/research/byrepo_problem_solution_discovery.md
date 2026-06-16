# byrepo 問題解決リポジトリ発見戦略

作成日: 2026-06-16

> bynote 調査（NotebookLM ノート `Contra byrepo OSS Discovery Strategy` / `00f94e59-0b57-47a4-b52b-872bf6f82496`）。
> 追加ノート: `2026-06-16 byrepo problem-solution repository discovery strategy` / `86d8abad-e2e7-4bb9-a9fb-74ebf7f89d24`。

## 1. 今回のテーマ

`byrepo` の精度向上対象を、「キーワードが一致する repository を探す」から「ユーザーの問題解決に資する repository / model / dataset / research artifact を探す」へ寄せる。

既存実装では GitHub / GitLab / Hugging Face / Zenodo / DataCite を Track A practical anchors として収集できるようになった。次のボトルネックは source 追加ではなく、`ThemeInput` から **問題、解決機構、実装証拠、運用制約** を分解し、検索と rerank に使うことである。

## 2. 調査から得た中核方針

### 2.1 検索は「問題文 -> 証拠クエリ群」に展開する

単一キーワード検索では、テーマ語を含むだけの古い実験コード、awesome list、fork、未完成プロジェクトが混ざる。GitHub 公式検索は `in:readme`、`in:topics`、`stars`、`forks`、`pushed`、`language`、`topic`、`license`、`archived:false` などで repository メタデータを絞れるため、検索段階から「実装証拠」を要求できる。

`byrepo` では `ThemeInput` を以下の facet へ分けて、source type ごとに複数クエリを生成するのがよい。

| Facet | 目的 | クエリ語例 |
|---|---|---|
| Problem symptom | 何を解決したいか | `domain shift`, `fault recovery`, `class imbalance` |
| Solution capability | 何ができる artifact が必要か | `evaluation`, `benchmark`, `pipeline`, `inference`, `simulation` |
| Implementation evidence | 動く証拠 | `demo`, `example`, `quickstart`, `notebook`, `cli` |
| Artifact type | source ごとの対象 | `model`, `dataset`, `space`, `software`, `reproducibility package` |
| Ecosystem anchor | 技術環境との一致 | `filename:package.json`, `pyproject.toml`, `transformers`, `pytorch` |
| Evaluation evidence | 問題解決の検証 | `benchmark`, `metrics`, `leaderboard`, `baseline`, `ablation` |
| Constraint evidence | 制約が読めるか | `caveat`, `limitation`, `known issues`, `requirements` |

### 2.2 Discovery と rerank を分離する

検索 API の rank は「問題解決性」ではなく、プラットフォーム固有の人気・文字列一致・更新情報に強く依存する。したがって、`byrepo` は次の2段に分ける。

1. **Recall stage**: source type ごとのクエリ束で広く候補を集める。
2. **Precision stage**: `Problem-Solution Fit` と `Reliability Score` を分けて rerank する。

`Reliability Score` は「使ってよいか」を測る。新しく必要なのは「この問題に効くか」を測る `Problem-Solution Fit` である。

### 2.3 README / card / metadata は What/How だけでは弱い

README 研究では、多くの repository は What や How を書く一方、目的、比較優位、状態、制約を説明する Why / When は相対的に希少で、成熟度の強いシグナルになる。Hugging Face や Zenodo/DataCite でも同じで、単に概要があるだけでなく、用途、評価、制約、ライセンス、関連論文が揃っているかを見るべきである。

`byrepo` では completeness を以下に分ける。

- **Orientation**: 何をする artifact か。
- **Operationalization**: どう動かすか。
- **Problem claim**: どの問題を解くと主張しているか。
- **Evidence**: benchmark / metric / paper / issue / example があるか。
- **Boundary**: どの条件では崩れるか。

### 2.4 保守性は last push 単体では測らない

LMA 研究は、commit、fork、issue、PR、最大無コミット日数、最大貢献者集中など複数特徴で maintenance activity を推定している。OpenSSF も、活動、リリース、maintainer diversity、security policy、license、authenticity、dependency impact を評価対象にする。

現状の `pushed:>2025-01-01` は有効な足切りだが、最終順位では以下を組み合わせる。

- recent push / release
- issue close signal
- PR merge signal
- fork-to-star ratio
- maintainer diversity
- archived / deprecated / finished status
- license clarity
- security policy / CI / tests

## 3. byrepo に追加すべき評価モデル

### 3.1 Problem-Solution Fit Score

Reliability とは別に 0-100 点で持つ。

| 軸 | 配点 | 判定 |
|---|---:|---|
| Problem Match | 25 | ユーザーの問題症状や評価対象が README/card/metadata に明示される |
| Solution Mechanism | 25 | 具体的な解決機構、手法、パイプライン、モデル、データが説明される |
| Execution Evidence | 20 | demo/example/notebook/CLI/model widget/dataset files がある |
| Evaluation Evidence | 20 | benchmark, metrics, baseline, paper, issue usage がある |
| Constraint Visibility | 10 | limitation, caveat, requirements, known issue が読める |

最終 rank は単純加算ではなく、まず `Problem-Solution Fit` で足切りし、その後 `Reliability Score` で並べるのがよい。高信頼だが問題に効かない artifact を上位に出す失敗を避けるため。

### 3.2 Selection Rationale を必ず出す

Track A に出す各候補は、次の4つを `source_meta` へ保持する。

- `matched_problem`: 入力問題のどの部分に対応したか
- `solution_mechanism`: 何を使って解決しようとしているか
- `usable_artifact`: 何が触れるか（repo / model / dataset / demo / package）
- `visible_constraint`: どの制約・失敗パターンが見えるか

これは LLM 生成の品質にも効く。現状の Track A 生成は source body に依存するため、候補選定時点で rationale を構造化しておくと、4部構成が「それっぽい紹介」から「なぜ今これを見るべきか」に寄る。

## 4. Source type 別の検索戦略

### GitHub / GitLab

- repository search: problem terms + capability terms + `in:readme` / `topic` / `language` / `pushed` / `archived:false`
- code/file evidence: `filename:pyproject.toml`, `filename:package.json`, `path:examples`, `path:notebooks`, `Dockerfile`, `requirements.txt`
- issue evidence: problem symptom terms in issues, recent closed issues, setup failure reports
- negative filter: awesome list, course, toy, tutorial-only, archived, no license, no README

### Hugging Face

- models: task tag + domain tag + problem terms; downloads は補助で、card completeness と license を重視
- datasets: domain + evaluation / benchmark / split / metric terms
- Spaces: demo evidence として使うが、standalone solution としては過信しない
- negative filter: gated-only, no license, no card, model card が空、派生元不明

### Zenodo / DataCite

- dataset / software / replication package / benchmark を優先
- DOI、related identifiers、GitHub link、paper link を重視
- DataCite は同一 DOI の重複が出やすいため、unified collector の DOI dedup を必須にする
- negative filter: paper-only record, files absent, license absent, description が短すぎる

## 5. 推奨実装ステップ

1. `ThemeInput` から `ProblemSearchPlan` を生成する。
   - `problem_terms`
   - `capability_terms`
   - `artifact_terms`
   - `evidence_terms`
   - `constraint_terms`
   - `ecosystem_terms`
2. source type ごとに query bundle を作る。
3. 収集候補へ `problem_solution_fit_score` を付ける。
4. `reliability_score` と分離して足切り・rerank する。
5. `source_meta` に `matched_problem`, `solution_mechanism`, `usable_artifact`, `visible_constraint` を保存する。
6. Track A 出力に `Why selected` を1行追加する。

## 6. 採用判断

採用すべき方針は、**検索対象追加ではなく、問題文からの evidence-seeking query expansion と Problem-Solution Fit rerank を追加すること**。

理由:

- 既に GitHub / GitLab / Hugging Face / Zenodo / DataCite の検索面は広がった。
- 次の品質差は「どこを探すか」より「何を解決証拠とみなすか」で決まる。
- Reliability Score だけでは、信頼できるが問題解決に資さない候補を上位に出す。
- `Problem-Solution Fit` は Track A の目的である「今すぐ触れる現実の足場」に直結する。

## 7. 参照資料

- NotebookLM: `Contra byrepo OSS Discovery Strategy` (`00f94e59-0b57-47a4-b52b-872bf6f82496`)
- GitHub Docs: Searching for repositories — https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories
- GitHub Docs: Code Search syntax — https://docs.github.com/en/search-github/github-code-search/understanding-github-code-search-syntax
- OpenSSF: Concise Guide for Evaluating Open Source Software — https://best.openssf.org/Concise-Guide-for-Evaluating-Open-Source-Software
- Prana et al. 2018/2019: Categorizing the Content of GitHub README Files — https://arxiv.org/abs/1802.06997
- Coelho et al. 2018: Identifying Unmaintained Projects in GitHub — https://arxiv.org/abs/1809.04041
- Coelho et al. 2020: Is this GitHub Project Maintained? — https://arxiv.org/abs/2003.04755
