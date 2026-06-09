# byrepo 収集・評価品質の改善戦略 (Track A Git practical anchors)

> bynote 調査（NotebookLM Deep Research、12ソース、ノート `Contra byrepo OSS Discovery Strategy` 00f94e59、2026-06-09）。
> 目的: byrepo（Track A Git practical anchors）における「有用なOSS・リポジトリの発見・評価・選定」の精度と実用性を向上させ、Track B（論文による遠類推）に対する堅牢な「実務の足場」としての機能を強化する。

---

## 1. 検索（Discovery）の高度化

単にキーワードを並べるだけでなく、開発プロセスや実装物としての特徴をクエリレベルで狙い撃ちする。

*   **Scoping & Targeted Search**:
    *   テーマ固有の主要パッケージや構成ファイルを明示的にターゲットにする。
        *   例: Python であれば `filename:pyproject.toml` や `filename:setup.py`。
        *   JavaScript であれば `filename:package.json` での依存関係検索。
    *   `demo in:readme` または `in:name`, `in:description` を追加し、単なるライブラリコードではなく「動くデモやサンプル」を意図的に引き寄せる。
*   **APIレベルでのノイズ事前除外**:
    *   GitHub Search API クエリに `pushed:>2025-01-01` などのアクティビティフィルタを含めることで、すでに長期間放置されているリポジトリを API レベルで足切りし、レートリミットを節約する。
    *   極端に低品質なリポジトリを防ぐため、`stars:>5` などの最小エンゲージメント条件をクエリに標準で組み込む。

---

## 2. 品質・活動度（Quality & Activity）の多次元評価

スター数や最終コミット日といった表層的な「バニティメトリクス（虚栄の指標）」を廃し、実質的な利用度と保守状況を測る。

*   **Fork-to-Star Ratio**:
    *   スター数は単なる「受動的ブックマーク」であることが多い。これに対し、フォークは「実際にビルド・カスタマイズしようとした開発者アクション」の証拠である。
    *   一般にデベロッパー向けツールや実装性の高いプロジェクトでは `1:10`（フォーク数がスター数の10%以上）程度の比率が健全とされる。この比率が極端に低いリポジトリ（例: スターは多いがフォークがほぼゼロ）は実用性が薄いリンク集やバズワードプロジェクトの可能性が高いため、Adoption の加点率を下げるかペナルティを課す。
*   **LMA (Level of Maintenance Activity) への移行**:
    *   「1年以内にコミットがあるか」という二値判定は unmaintained プロジェクトの 75% を見逃す（放置されているが、軽微な自動修正などでコミット履歴だけは動いているケースが多いため）。
    *   代替指標として、**「最大連続無コミット日数 (Maximum Consecutive Idle Days)」** や **「直近3ヶ月ごとのコミット密度」** を LMA 指標として加味する。
*   **Bus Factor & Maintainer Diversity**:
    *   単一の開発者の貢献率（Max Contributions by single developer）が極端に高い、あるいは組織的多様性（Maintainer Diversity）が低いプロジェクトは、単一障害点（SPOF）を抱えており継続性にリスクがある。

---

## 3. README解析によるドキュメント成熟度評価

リポジトリの README はプロジェクトの成熟度を測る最大のシグナルである。

*   **Why と When の検出**:
    *   先行研究（SMUなどのREADMEカテゴリ分析）によると、ほぼすべての README（97%）は **What (概要)** を書き、88.5%は **How (使い方)** を書く。
    *   しかし、高品質で成熟したプロジェクトは **Why (なぜこのツールが必要か、競合との違い/メリット - 25.7%にのみ存在)** や **When (ロードマップ、現在のステータス - 21.4%にのみ存在)** を明記している。
    *   見出しに `objective`, `purpose`, `why`, `status`, `roadmap`, `plan` などのキーワードが含まれているかを heuristics 的に検出し、これらがある場合に README スコアを大幅に加点する。
*   **コードブロックや構造の豊富さ**:
    *   README 内の `@abstr code section` (コードブロックの数) や `@abstr hyperlink` (外部リンク) の出現頻度をチェックし、実装アンカーとしての「具体例の豊富さ」をスコアリングに反映する。

---

## 4. Issue/PRによる運用ヘルスチェック

Issue と Pull Request は、運用中の「詰まりどころ」や「コミュニティの生存」を示す最もリアルタイムな指標である。

*   **ゼロIssueの罠 (Zero Issues Trap) の回避**:
    *   スター数が数百〜数千あるにもかかわらず、Open/Closed ともに Issue が極端に少ないリポジトリは、「実際には使われていない」「ドキュメントが不十分でユーザーが諦めている」負のシグナルである。
    *   適度な Issue 数があり、かつそれらがクローズされている比率が高い（Issue Resolution Velocity）リポジトリを優先する。
*   **セキュリティと堅牢性**:
    *   `vulnerability` や `security` に対する明示的な報告窓口（coordinated vulnerability disclosure）やセキュリティポリシーファイル (`SECURITY.md`) があるか、また LTS（長期サポート）の宣言があるかを評価する。

---

## 5. Repository Reliability Score の再設計（100点満点）

これまでの暫定配点を、NotebookLM の実証データに基づき4つの親ピラーに再構築する。

### Pillar 1: Implementation & Documentation Confidence (配点: 30点)
*   **Framework & Dependency Alignment (10点)**: 配置ファイル（`package.json` 等）における必要パッケージの記述・一致度。
*   **README Mature Categories (10点)**: "What/How" に加え、"Why" (目的/優位性) と "When" (ロードマップ/状況) の heuristics 的検出。
*   **Code Examples & Assets (10点)**: README 内のコードブロック数、インストール手順の具体性。

### Pillar 2: Maintenance Activity Level (LMA) (配点: 25点)
*   **Commit Continuity & Density (15点)**: 直近更新日（Updated Year/Days Since）に加えて、更新頻度や最大連続放置日数の少なさ。
*   **Developer Diversity (10点)**: バスファクターの低さ（特定個人への極端なコミット集中がないこと）。

### Pillar 3: Community Health & Engagement (配点: 20点)
*   **Fork-to-Star Ratio (10点)**: スター数に対するフォーク数の比率（目標 `1:10` 前後）。極端なアンバランス（例: stars=1000, forks=2）は減点。
*   **Active Issue Signal (10点)**: 「ゼロIssueの罠」の回避。Issueが存在し、かつクローズ比率（解決力）が高いこと。

### Pillar 4: Security & Enterprise Practices (配点: 25点)
*   **OSI License Clarity (10点)**: 明示された再利用可能なライセンス（MIT, Apache 2.0等）の有無。
*   **CI/CD & Security Practices (10点)**: 自動テストパイプラインの有無、セキュリティポリシーの有無。
*   **Codebase Completeness (5点)**: 静的解析（TODO/placeholderの少なさ、typosquatting防止の authentic verification）。

---

## 6. 実装フェーズへのマッピング案

`src/pipeline/git_collect.py` に対する具体的な適用箇所は以下の通り。

1.  **`build_track_a_git_query` の拡張**:
    *   テーマ核心語に加えて、言語やエコシステムに応じた設定ファイル名や `demo` などのスコープ語を自動付与する。
2.  **`_fetch_issue_signal` の詳細化**:
    *   単に件数を出すだけでなく、`open / (open + closed)` の比率から解決力を評価し、stars 数に対して極端に issue が少ない場合のペナルティ処理を入れる。
3.  **`_readme_score` の高度化**:
    *   従来の単純なキーワードマッチから、「見出し（`### Why` 等）の判定」と「コードブロック数のカウント」による Heuristics 分類ロジックへ刷新する。
4.  **`_apply_reliability` での Fork-to-Star 比率の算出**:
    *   `repo.forks / repo.stars` を算出し、比率が `0.05` 未満の場合は Adoption スコア（旧stars依存）を段階的に減点する。
