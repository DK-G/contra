# byrepo Problem-Solution Fit 仕様

作成日: 2026-06-16

## 1. 目的

`byrepo` は Track A practical anchors として、ユーザーの研究・開発テーマに対して「今すぐ触れる現実の足場」を出す。

本仕様は、検索対象が GitHub / GitLab / Hugging Face / Zenodo / DataCite へ広がった後に、キーワード一致だけでなく **問題解決に資する候補** を上位に出すための検索計画、クエリ単位、スコア、運用判断を定義する。

## 2. クエリ群の単位

クエリ群は **1つの入力テーマ (`ThemeInput`) に対する `ProblemSearchPlan` 配下で、`source type × intent` 単位** にまとめる。

採用しない単位:

- **リポジトリ単位**: 検索前には対象リポジトリが存在しないため、単位として早すぎる。
- **問題単位だけ**: 同じ問題でも、repository / model / dataset / DOI record では検索語と評価証拠が異なる。
- **1件のみ**: recall が足りず、検索 API の rank 偏りをそのまま受ける。

採用する単位:

```text
ThemeInput
  -> ProblemSearchPlan
      -> QuerySpec(source_type="github_repository", intent="problem_capability", query=...)
      -> QuerySpec(source_type="github_repository", intent="implementation_evidence", query=...)
      -> QuerySpec(source_type="hf_model", intent="artifact_evidence", query=...)
      -> QuerySpec(source_type="zenodo_record", intent="evaluation_evidence", query=...)
```

この単位なら、同じテーマから「問題症状」「解決能力」「実行証拠」「評価証拠」を別々に拾い、source type ごとに API の癖へ合わせて翻訳できる。

## 3. ProblemSearchPlan

`ProblemSearchPlan` は `ThemeInput` から抽出する検索計画で、以下の facet を持つ。

| Facet | 意味 | 主な入力 |
|---|---|---|
| `problem_terms` | 解くべき問題や症状 | `keywords.include`, `why_problem`, `concern`, `scope.field` |
| `capability_terms` | 必要な機能・能力 | `goal`, `theme_overview` |
| `artifact_terms` | 探す成果物の種類 | `goal`, `approach_type` |
| `evidence_terms` | 動く・検証済みである証拠 | `goal`, `theme_overview` |
| `constraint_terms` | 制約や失敗条件 | `concern`, `keywords.exclude` |
| `ecosystem_terms` | 技術環境との一致 | `theme_overview`, `scope`, `keywords` |

現行実装はヒューリスティック抽出であり、LLM 生成は使わない。これは、外部 API 検索の前段で低コスト・再現可能に動かすためである。

## 4. QuerySpec

`QuerySpec` は次の3要素を持つ。

- `source_type`: `github_repository`, `gitlab_repository`, `hf_model`, `hf_dataset`, `hf_space`, `zenodo_record`, `datacite_doi` など
- `intent`: `problem_capability`, `implementation_evidence`, `artifact_evidence`, `evaluation_evidence`, `ecosystem_fit` など
- `query`: 実際に API へ渡す検索文字列

### 4.1 source type 別の扱い

GitHub:

- repository search を使うため、`in:readme`, `stars`, `pushed`, `archived:false` など repository search に合う qualifier を使う。
- `filename:` や `path:` は code search 向けなので、現行 collector では使わない。
- `awesome` 系リストは discovery seed としては有用だが、Track A practical anchor そのものではないため、Problem-Solution Fit に上限ペナルティをかける。

GitLab:

- Projects API の `search` は GitHub より qualifier が少ないため、plain query を使う。
- precision は検索後の README / issue / score 側で補う。

Hugging Face:

- model / dataset / Space を source type として分ける。
- downloads は補助指標であり、card completeness、license、task/domain tag を重視する。

Zenodo / DataCite:

- DOI 付き artifact を重視する。
- DataCite は同一 DOI の重複候補が返ることがあるため、unified collector で DOI / URL / 正規化 title dedup を必須とする。

## 5. Problem-Solution Fit Score

`Problem-Solution Fit` は「この候補がユーザー問題の解決に効くか」を見るスコアで、`Reliability Score` とは分離する。

| 軸 | 配点 | 解釈 |
|---|---:|---|
| Problem Match | 25 | 入力問題・症状・対象ドメインに一致する |
| Solution Mechanism | 25 | 解決機構、手法、パイプライン、モデル、データが読める |
| Execution Evidence | 20 | demo, example, quickstart, notebook, files など触れる証拠がある |
| Evaluation Evidence | 20 | benchmark, metric, baseline, paper, citation など検証の証拠がある |
| Constraint Visibility | 10 | limitation, caveat, requirements, known issue など制約が見える |

最終 rank は以下を優先する。

```text
(problem_match_score, problem_solution_fit_score, reliability_score)
```

つまり、まず入力問題にどれだけ直接一致するかを優先し、その中で問題解決性、最後に信頼性を見る。

ただし、`Problem Match` が 0 の候補は、どれだけ実行証拠や評価証拠を持っていても当該テーマへの直接解決性が確認できないため、fit score を最大15に抑える。
`use_problem_search=True` の source collector では、原則として `Problem Match` が 0 の候補は返さない。これは、問題一致ゼロ候補を「探索補助」ではなく Track A practical anchor として出してしまう失敗を避けるためである。

## 6. source_meta に保存する理由

候補の `Work.source_meta` には以下を保存する。

- `problem_solution_fit_score`
- `problem_match_score`
- `solution_mechanism_score`
- `execution_evidence_score`
- `evaluation_evidence_score`
- `constraint_visibility_score`
- `matched_problem`
- `solution_mechanism`
- `usable_artifact`
- `visible_constraint`

これは単に rank のためだけでなく、Track A 出力で `Why selected` を表示し、LLM 生成が「それっぽい紹介」に流れるのを防ぐためである。

## 7. 運用時に解釈の幅が出る部分

### 7.1 「問題」と「解決機構」の切り分け

同じ語が問題にも解決にも見える場合がある。

例: `domain adaptation`

- 問題として読む: 分布差による性能劣化
- 解決機構として読む: adaptation 手法そのもの

運用ルール:

- `why_problem` と `concern` に出る語は problem 寄りに扱う。
- `goal` に出る動詞・成果物語は capability / artifact 寄りに扱う。
- 迷う場合は problem と capability の両方に入れてよいが、出力では `matched_problem` と `solution_mechanism` を分けて表示する。
- `bert-text` や `digital-twin` のようなハイフン区切りは、`bert text` / `digital twin` と同じ問題語一致として扱う。

### 7.2 人気と実用性の混同

stars / downloads / likes は採用シグナルだが、問題解決性の証拠ではない。

運用ルール:

- 人気指標は `Reliability Score` または adoption の補助に置く。
- `Problem-Solution Fit` には、問題語、解決語、実行証拠、評価証拠が本文・card・metadata に存在する場合だけ加点する。
- `awesome` / tutorial / course / link list は、問題解決の実装証拠ではなく案内情報に寄るため、source type を問わず fit score を抑える。

### 7.3 完成済みと放置の区別

更新が少ない repository は、完成済みの場合と放置の場合がある。

運用ルール:

- `deprecated`, `unmaintained`, `archived` は強い減点。
- `stable`, `finished`, `maintenance mode` は、README に使用条件やサポート方針があれば即除外しない。
- Track A では、制約として `visible_constraint` に残す。

### 7.4 demo / Space の扱い

動く demo は強い実行証拠だが、研究・実務で再利用可能とは限らない。

運用ルール:

- demo は `Execution Evidence` に加点する。
- code、model、dataset、license、paper link が無い demo は `Reliability Score` 側で抑える。

### 7.5 DOI record の扱い

Zenodo / DataCite は artifact ではなく paper-only record も返す。

運用ルール:

- files / resource type / related identifiers / GitHub link / dataset/software type があるものを優先。
- paper-only record は、Track B 論文探索に近いため Track A では低めに扱う。

### 7.6 クエリ数とレートリミット

source type × intent でクエリを増やすと、API 呼び出しが増える。

運用ルール:

- 既定は intent 3本程度に抑える。
- `per_page` は小さくし、収集後の dedup/rerank で精度を上げる。
- `use_problem_search=True` では、最初の query が上限を満たしてもそこで打ち切らず、intent ごとに少数候補を集めてから rerank する。
- 非 Git source の focused query は上位3つの `problem_terms` を anchor にし、`problem_only` は上位2語の fallback として最後に回す。
- 失敗した source は全体を落とさず、他 source の候補を返す。

## 8. 現行実装範囲

実装済み:

- `ProblemSearchPlan`
- `QuerySpec`
- GitHub / GitLab / Hugging Face / Zenodo / DataCite の query bundle 対応
- `Problem-Solution Fit Score`
- `source_meta` への fit score / rationale 保存
- unified collector の `(Problem-Solution Fit, Reliability)` rank
- Markdown / MCP 出力での `Problem-Solution Fit` と `Why selected` 表示

未実装:

- LLM による `ProblemSearchPlan` 抽出
- GitHub code search API による file/path evidence の直接取得
- issue 本文検索による problem symptom evidence
- maintainer diversity / release recency の詳細 LMA
- score weight の複数テーマ較正

## 9. 次の改善候補

1. `ProblemSearchPlan` を LLM なしヒューリスティックと LLM 支援の2段にする。
2. GitHub code search を別 collector として追加し、`path:examples`, `filename:pyproject.toml`, `Dockerfile` などを evidence にする。
3. issue / discussion 検索を追加し、`visible_constraint` を実運用の詰まりに寄せる。
4. 複数テーマで smoke test し、`Problem-Solution Fit` の閾値を決める。
