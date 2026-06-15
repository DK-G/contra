# Change Log（開発概要 + diff.mdスナップショット）

## 運用ルール
- `diff.md` を更新（上書き）する **直前**に、必ずこのファイルの先頭へ1エントリ追記します。
- ここは履歴（追記のみ）です。過去のエントリを書き換えることはありません。
- 目的は「後から開発の経緯を復元できること」です。詳細なdiffはGitの履歴を参照します。

---

## 2026-06-15（CL-0081） ローカル化 段階(b): 数値ゲートの post-gate 純関数化

### 概要
* `select_track_b` の決定論ゲートを LLM 採点/judge から分離し、純関数 `apply_post_gates` として切り出した。エージェント採点に対し LLM 不使用で anomaly/near-cap/serendipity/hollow/percentile/output-floor/fallback/M3 を再適用する「コードの硬い床」。
* `select_track_b` も同じ純関数を共有するよう refactor（挙動不変・スコア設計値不変）。

### 関連タスク
* Task: ローカル化（MCPクライアント委譲）段階(b)

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
委譲設計の多層防御として、数値ゲートを LLM 採点から独立した純関数（post-gate）に切り出し、エージェント採点にも同じ硬い床を機械的に適用できるようにする。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/classify.py, tests/test_post_gates.py（新規）, DECISION_LOG.md, task.md, diff.md, Changelog.md
_serendipity_scored / _hollow_filter / _quality_gate_and_build を共有純関数化し、apply_post_gates を新設。select_track_b も同関数を呼ぶよう refactor。

# 3. 確認方法 (必須)
python3 -m pytest tests/ -q → 185 passed（refactor 後も Track B テスト全 green＝挙動不変）。

# 4. 既知の課題・リスク (必須)
段階(c)（エージェント採点 JSON スキーマ＋委譲経路）、(d)（byrepo 委譲）は未着手。スコア設計値（0.20/0.50/0.35/0.10/0.5）は不変。
```

---

## 2026-06-15（CL-0080） ローカル化 段階(a): bybridge キー無し structured 一周（MCPクライアント委譲）

### 概要
* `docs/research/mcp_subscription_delegation.md` の委譲方式を採用し、段階(a)を実装。`src/pipeline/delegate.py`（純関数）で、決定論選別→structured 整形→OutputDocument を **API キー無し**で一周。
* MCP `bybridge` に `structured` フラグを追加（`raw_only=true, structured=true` でキー無し 4部 Markdown）。

### 関連タスク
* Task: ローカル化（MCPクライアント委譲）段階(a)

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
LLM 判定・生成を contra 自身の API キーから外し、呼び出し側エージェントの推論へ委譲する設計の第一歩として、bybridge をキー無しで一周できるようにする。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/delegate.py（新規）, src/mcp_server.py, tests/test_delegate.py（新規）, DECISION_LOG.md, task.md, diff.md, Changelog.md
決定論選別（near_domain pre-filter＋共有bridge順）＋structured 整形（LLM不使用）で OutputDocument を生成。MCP bybridge に structured フラグ。

# 3. 確認方法 (必須)
python3 -m pytest tests/ -q → 179 passed。mcp_server import OK。

# 4. 既知の課題・リスク (必須)
structure/serendipity スコアは LLM 判定待ちで 0.0（委譲先が補充）。段階(b)以降（数値ゲートの純関数化・post-gate、エージェント採点スキーマ）は未着手。用途は作者自身に限定。
```

---

## 2026-06-15（CL-0079） Phase 1 Done 評価ルーブリックの整備（docs/quality_eval.md 刷新）

### 概要
* `docs/quality_eval.md` を旧20本方針から現行 contrarian 4部構成へ全面刷新。Done 定義・5テーマ・再現コマンド・記入式ルーブリック表を整備し、roadmap #10（人間品質評価）を「実行して埋めるだけ」の状態にした。
* 実 LLM API＋人間判断が必要なため、評価実行そのものは本セッション（無認証）では未実施。

### 関連タスク
* Task: Phase 1 Done 判断（評価ルーブリックの整備を完了、評価実行は保留）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
roadmap #10（Phase 1 Done 判断）を前進させるため、品質評価を再現可能な手順＋記入式ルーブリックとして整備する。

# 2. 変更概要 (必須)
変更ファイル: docs/quality_eval.md（全面刷新）, task.md, diff.md, Changelog.md
旧20本方針の観点を現行4部構成へ刷新。Done 定義・5テーマ・再現コマンド・1本ごと観点・テーマ横断ルーブリック表を定義。

# 3. 確認方法 (必須)
doc レビュー。コード変更なし（python3 -m pytest tests/ -q → 111 passed 維持）。

# 4. 既知の課題・リスク (必須)
評価実行は実 LLM API＋人間判断が必要で無認証セッションでは不可。Codex/人間が API キー在席環境で §4 表を埋める。
```

---

## 2026-06-15（CL-0078） Track A score 内訳表示の改善

### 概要
* Track A Markdown の Reliability Score 行に total `/100`・各 Pillar の max・スコアリングモードタグ（rich: time+people / README-only）を追加し、A-RS1/A-RS2 で導入したシグナルを読み手が解釈できるようにした。
* discussion 観測は GitHub Discussions が GraphQL 専用のため保留。

### 関連タスク
* Task: Track A の discussion 観測 / score 内訳表示の改善（後者を実装）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
A-RS1/A-RS2 で導入した Pillar スコアを Track A 出力で解釈可能にするため、score 内訳表示（max・モード）を改善する。

# 2. 変更概要 (必須)
変更ファイル: src/core/output_spec.py, tests/test_export_render.py, task.md, diff.md, Changelog.md
Reliability Score 行に /100 と各 Pillar の max、scoring mode タグを追加。Verified Maturity /12・Third-Party /6 も max 付きに統一。

# 3. 確認方法 (必須)
python3 -m pytest tests/ -q → 111 passed

# 4. 既知の課題・リスク (必須)
discussion 観測は GitHub Discussions が REST 一覧なし（GraphQL 専用）のため保留。roadmap #10（人間品質評価）は実 LLM API＋人間判断が必要で本セッションでは未実施。
```

---

## 2026-06-15（CL-0077） A-RS2 続編: Pillar 1 に「他人」系シグナルを追加（A-RS2 完了）

### 概要
* 時間系（先手）に続き「他人」系シグナル（外部コントリビュータ＋非 owner 起票者）を Pillar 1 に導入し、A-RS2 を完了とした。
* `_third_party_score`（最大6点）を新設。README 系を 0.4 倍へ更にスケールし、時間系12＋他人系6で再配分。dependents は REST 非提供のため対象外。

### 関連タスク
* Task: A-RS2 続編（byrepo Pillar 1「他人」系）／ roadmap A-RS2（完了）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
A-RS2 続編: 生成で水増しできないもう一方のシグナル class「他人」（外部コントリビュータ / 非 owner 起票者）を Pillar 1 に導入する。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/git_collect.py, src/core/models.py, src/core/output_spec.py, tests/test_git_collect.py, DECISION_LOG.md, roadmap.md, task.md, diff.md, Changelog.md
_third_party_score（最大6）= 外部コントリビュータ（/contributors）＋非 owner 起票者（issues 再利用）。Pillar 1 rich モードを README 0.4倍＋verified 12＋third_party 6 へ再配分。owner_login 保持、_fetch_issue_signal 5-tuple 化。

# 3. 確認方法 (必須)
python3 -m pytest tests/ -q → 110 passed

# 4. 既知の課題・リスク (必須)
dependents は GitHub REST 非提供のため対象外（将来 GraphQL 要検討）。外部コントリビュータ取得で repo あたり REST 約3増（トークン前提）。Pillar 配点全体の再較正は roadmap #10 の人間品質評価とあわせて。
```

---

## 2026-06-15（CL-0076） A-RS2: Pillar 1 配点移行の先手（CI実行履歴＋リリース刻み）を実装

### 概要
* 懸念2（README 成熟度が vibe coding 時代に水増し容易）への対応として、Pillar 1 の配点を「時間」系シグナルへ段階移行する先手を実装。
* `_verified_maturity_score`（リリース刻み＋CI健全性、最大12点）を新設。リッチシグナル取得時のみ README 系を 0.6 倍へ移譲。GITHUB_TOKEN 在席時のみ自動有効化。

### 関連タスク
* Task: A-RS2（byrepo Pillar 1 配点移行・先手）／ roadmap A-RS2

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
A-RS2: Pillar 1 の README 偏重を是正し、生成で水増しできない「時間」系シグナル（CI 実行履歴＋リリース刻み）へ配点を段階移行する。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/git_collect.py, src/core/models.py, src/core/output_spec.py, src/cli/main.py, tests/test_git_collect.py, DECISION_LOG.md, roadmap.md, task.md, diff.md, Changelog.md
_verified_maturity_score（cadence+ci, 最大12）を新設。リッチシグナル取得時のみ README 系を 0.6 倍へスケール。include_rich_signals=None はトークン在席時のみ自動有効。CLI --git-rich-signals で上書き。

# 3. 確認方法 (必須)
python3 -m pytest tests/ -q → 107 passed

# 4. 既知の課題・リスク (必須)
「他人」系シグナル（contributors/dependents）は未着手。リッチシグナルは API コスト増のためトークン前提。トークン在席時は README のみ満点 repo が相対降格（狙い通り）。
```

---

## 2026-06-15（CL-0075） A-RS1: Pillar 2 (LMA) 候補プール内相対正規化を実装（A-RS1 完了）

### 概要
* 改善方針候補2「候補プール内相対正規化」を実装し、A-RS1（候補1＋候補2）を完了とした。
* `_apply_pool_relative_lma` を追加。候補プールをドメインサンプルとみなし、push 鮮度のプール内相対順位で LMA を補正。`max` 意味論で新鮮 repo は不変、追加 API コストゼロ。

### 関連タスク
* Task: A-RS1（byrepo Pillar 2 改善）／ roadmap A-RS1（完了）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
A-RS1 改善方針候補2「候補プール内相対正規化」を実装し、成熟ドメインで全 repo が stale でも最も手入れされた repo が浮上するようにする。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/git_collect.py, tests/test_git_collect.py, DECISION_LOG.md, roadmap.md, task.md, diff.md, Changelog.md
_apply_pool_relative_lma を追加し collect_track_a_git_repos の後段で適用。GitCollectConfig.pool_relative_lma で切替。

# 3. 確認方法 (必須)
python3 -m pytest tests/ -q → 99 passed

# 4. 既知の課題・リスク (必須)
A-RS2（Pillar 1 配点移行）は未着手。順位は magnitude を無視するヒューリスティック（天井 12点・max 意味論で被害は限定）。
```

---

## 2026-06-15（CL-0074） A-RS1: Pillar 2 (LMA) 完成判定の床を実装

### 概要
* byrepo Reliability Score の Pillar 2 (LMA) が「完成した安定ライブラリ」を最も強く罰する問題（DECISION_LOG 2026-06-12 懸念1）を、改善方針候補1「完成判定の床」で緩和した。
* `_is_completed_stable` を新設し、採用シグナル＋過去 issue 活動＋高クローズ率を満たす stale repo の LMA を 12〜15点で床止め。issue の open/closed 件数を構造化保持。

### 関連タスク
* Task: A-RS1（byrepo Pillar 2 改善）／ roadmap A-RS1

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
A-RS1: byrepo Reliability Score の Pillar 2 (LMA) が「完成した安定ライブラリ」を最も強く罰する問題を、改善方針候補1「完成判定の床」で緩和する。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/git_collect.py, src/core/models.py, tests/test_git_collect.py, DECISION_LOG.md, roadmap.md, task.md, diff.md, Changelog.md
_lma_score を「鮮度」算出と「完成判定の床」適用の2段構成へ分離。_is_completed_stable を新設。issue の open/closed 件数を GitRepository に構造化保持し source_meta へ露出。

# 3. 確認方法 (必須)
python3 -m pytest tests/ -q → 95 passed

# 4. 既知の課題・リスク (必須)
改善方針候補2（プール内相対正規化）と A-RS2（Pillar 1 配点移行）は未着手。close 率は issue サンプルに基づくヒューリスティック。
```

---

## 2026-06-09（CL-0073） named flow 追加（byrepo / byserendipity）

### 概要
* Track A と Track B の回し方を `byrepo` / `byserendipity` として named flow 化した。

### 関連タスク
* Task: named flow の整備

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
Track A と Track B の回し方を named flow として独立定義し、bynote のように呼び出し名で扱えるようにする。

# 2. 変更概要 (必須)
変更ファイル: docs/agent_rules/byrepo.md, docs/agent_rules/byserendipity.md, AGENT_COORDINATION.md, task.md, diff.md, Changelog.md
Track A 用 byrepo と Track B 用 byserendipity を追加し、named flow 一覧へ登録した。

# 3. 確認方法 (必須)
Get-Content -Raw docs/agent_rules/byrepo.md
Get-Content -Raw docs/agent_rules/byserendipity.md
Get-Content -Raw AGENT_COORDINATION.md

# 4. 既知の課題・リスク (必須)
現時点では named flow の定義追加であり、自動ディスパッチ機構そのものは実装していない。
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-06-09（CL-0072） Track A Reliability Score と issue 観測の追加

### 概要
* Track A Git practical anchors に issue signal と Reliability Score を追加し、Markdown 出力へ反映した。

### 関連タスク
* Task: Track A Git practical anchors の issue 観測と Reliability Score 実装

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
Track A Git practical anchors の信頼性評価を実装し、issue 観測と Reliability Score を表示できるようにする。

# 2. 変更概要 (必須)
変更ファイル: src/core/models.py, src/pipeline/git_collect.py, src/core/output_spec.py, tests/test_git_collect.py, tests/test_export_render.py, task.md, diff.md, Changelog.md
issue サンプル取得、Reliability Score 算出、Work.source_meta への保持、Track A Markdown への score / issue signal 表示を追加した。

# 3. 確認方法 (必須)
& 'C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall src\core\models.py src\pipeline\git_collect.py src\core\output_spec.py tests\test_git_collect.py tests\test_export_render.py
$env:PYTHONPATH='.'; & 'C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\test_git_collect.py
$env:PYTHONPATH='.'; & 'C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\test_export_render.py

# 4. 既知の課題・リスク (必須)
GitHub discussion 観測は未実装。
Reliability Score は暫定配点であり、人手で重み調整が必要な可能性がある。
compileall は Windows 上の既存 __pycache__ 置換で PermissionError が出る場合があるが、テスト実行自体は成功している。
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-06-09（CL-0071） Track A Git collector の Track A パイプライン接続

### 概要
* GitHub repository を `Work` に正規化し、Track A の既存分類・生成・Markdown 出力へ接続した。

### 関連タスク
* Task: Track A Git practical anchors の Track A パイプライン接続

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
Track A の Git collector を既存の Track A 分類・生成・出力パイプラインへ接続する。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/git_collect.py, src/pipeline/generate.py, src/core/output_spec.py, src/cli/main.py, tests/test_git_collect.py, tests/test_export_render.py, task.md, diff.md, Changelog.md
GitHub repository を Work に正規化して Track A 既存パイプラインへ流し込み、CLI 収集元と Track A 表示を Git practical anchor 前提へ更新した。

# 3. 確認方法 (必須)
& 'C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall src\cli\main.py src\core\output_spec.py src\pipeline\generate.py src\pipeline\git_collect.py tests\test_git_collect.py tests\test_export_render.py
$env:PYTHONPATH='.'; & 'C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\test_git_collect.py
$env:PYTHONPATH='.'; & 'C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\test_export_render.py

# 4. 既知の課題・リスク (必須)
GitHub API の rate limit 回避や issue / discussion 観測は未実装。
Reliability Score はまだ算出しておらず、現時点では stars 等を生値表示している。
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-06-09（CL-0070） Track A Git collector の最小実装

### 概要
* `GitRepository` モデルと GitHub API 最小クライアントを追加し、Track A Git 実用アンカー向けの repository / README 取得 collector を実装した。

### 関連タスク
* Task: Track A Git実用アンカーの最小 collector 実装

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
Track A の Git 実用アンカー化に向けて、GitHub から repository 候補と README を取得する最小 collector を追加する。

# 2. 変更概要 (必須)
変更ファイル: src/core/models.py, src/github/client.py, src/pipeline/git_collect.py, tests/test_git_collect.py, task.md, diff.md, Changelog.md
GitRepository データモデル、GitHub REST API 最小クライアント、Track A Git collector、モックテストを追加した。

# 3. 確認方法 (必須)
& 'C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall src\github src\pipeline\git_collect.py tests\test_git_collect.py
$env:PYTHONPATH='.'; & 'C:\Users\52hae\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\test_git_collect.py

# 4. 既知の課題・リスク (必須)
まだ Track A の既存分類・出力パイプラインには未接続。
GitHub API の rate limit 回避や issue / discussion 観測は未実装。
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-06-09（CL-0069） Track A Git実用アンカー設計メモの追加

### 概要
* `docs/specs/track_a_git_anchor_design.md` を追加し、Track A の Git 版を実用アンカーとして再定義した。

### 関連タスク
* Task: Track A Git実用アンカー設計

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
Track A の Git 実用アンカー設計を前に進めるため、検索条件・信頼性評価・出力区分を設計メモとして明文化する。

# 2. 変更概要 (必須)
変更ファイル: docs/specs/track_a_git_anchor_design.md, task.md, diff.md, Changelog.md
Track A を Git 実用アンカーとして再定義する設計メモを追加し、task.md の設計タスク完了を反映した。

# 3. 確認方法 (必須)
Get-Content -Raw docs/specs/track_a_git_anchor_design.md
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
まだ設計段階であり、GitHub 検索APIや README / issue 取得の実装方式、レート制限、認証要否は未確定。
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0068） Plan B+GeminiCLI方針の反映

### 概要
* `task.md`に二段階仕上げ（Plan B→GeminiCLI）のタスクを追加した。

### 関連タスク
* Task: GeminiCLIで関係性/要約/注意点を更新する後処理フロー設計

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
Plan B+GeminiCLIの二段階仕上げ方針をタスクに反映するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
Plan B+GeminiCLI後処理のタスクを追加し、方針変更を記録。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0067） LLM生成モードの追加

### 概要
* OpenAI Responses API を使ったPlan B（LLM）生成を追加した。

### 関連タスク
* Task: LLM生成（Plan B）の追加

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
LLM生成モード（Plan B）を追加し、自然文生成を選択可能にするため。

# 2. 変更概要 (必須)
変更ファイル: src/openai_client.py, src/pipeline/generate.py, src/cli/main.py, diff.md, Changelog.md
OpenAI Responses API を使う LLM 生成モードを追加し、plan_a/plan_b を CLI で切替可能にした。

# 3. 確認方法 (必須)
Get-Content -Raw src/cli/main.py
Get-Content -Raw src/pipeline/generate.py
Get-Content -Raw src/openai_client.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0066） 生成モードの追加

### 概要
* `--gen-mode`で生成モードを切り替えられるようにした。

### 関連タスク
* Task: 生成モード切替の追加

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
生成モードを切り替え可能にし、A/Bの出力を区別できるようにするため。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/generate.py, src/cli/main.py, diff.md, Changelog.md
--gen-modeを追加し、simple/structuredの生成ルールを選択可能にした。

# 3. 確認方法 (必須)
Get-Content -Raw src/cli/main.py
Get-Content -Raw src/pipeline/generate.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0065） 生成文の簡易化

### 概要
* `src/pipeline/generate.py`で簡易要約と関連性文を生成するようにした。

### 関連タスク
* Task: 生成品質の最小改善

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
仮文の生成をやめ、簡易要約と関連性文を出力するため。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/generate.py, src/cli/main.py, diff.md, Changelog.md
abstract要約とキーワード一致による関係性文を生成するように修正。

# 3. 確認方法 (必須)
Get-Content -Raw src/cli/main.py
Get-Content -Raw src/pipeline/generate.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0064） リンクと付録情報の出力反映

### 概要
* 出力MarkdownにDOI/OpenAlexリンクと取得情報を反映した。

### 関連タスク
* Task: 出力整形の情報充実

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
出力にリンクと取得情報を反映し、実体に合う付録情報にするため。

# 2. 変更概要 (必須)
変更ファイル: src/core/models.py, src/core/output_spec.py, src/cli/main.py, diff.md, Changelog.md
DOI/OpenAlexリンクと取得情報（取得日/検索条件/フィルタ条件）を出力に反映。

# 3. 確認方法 (必須)
Get-Content -Raw src/core/output_spec.py
Get-Content -Raw src/cli/main.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0063） 収集クエリとログの調整

### 概要
* includeキーワード優先のクエリ生成に修正し、収集件数ログを追加した。

### 関連タスク
* Task: 実論文出力の安定化

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
収集クエリと実行ログを調整し、収集状況を把握できるようにするため。

# 2. 変更概要 (必須)
変更ファイル: src/cli/main.py, src/pipeline/collect.py, diff.md, Changelog.md
includeキーワード優先のクエリ生成に修正し、収集件数ログを追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/pipeline/collect.py
Get-Content -Raw src/cli/main.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0062） 収集・分類の挙動改善

### 概要
* abstract必須を解除し、クエリ生成と分類の挙動を改善した。

### 関連タスク
* Task: 実論文出力の安定化

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
実論文が出力されるよう収集・分類の挙動を改善するため。

# 2. 変更概要 (必須)
変更ファイル: src/cli/main.py, src/pipeline/collect.py, src/pipeline/classify.py, diff.md, Changelog.md
abstract必須を解除、クエリ優先順を修正、分類を件数比例に変更。

# 3. 確認方法 (必須)
Get-Content -Raw src/pipeline/collect.py
Get-Content -Raw src/pipeline/classify.py
Get-Content -Raw src/cli/main.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0061） OpenAlex収集E2E確認タスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: OpenAlex収集ありのE2E実行確認（theme.json）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex収集ありのE2E実行確認タスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0060） 収集→出力フローのCLI接続

### 概要
* `src/cli/main.py`に収集→分類→生成→出力の接続フローを実装した。
* `task.md`で接続タスク2件をDoneへ移動した。

### 関連タスク
* Task: 収集→分類→生成→出力の接続作業（CLI通常フローに統合）
* Task: 収集結果をMarkdown出力へ反映（collect→classify→generate→export）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
収集→分類→生成→出力をCLI通常フローに接続するため。

# 2. 変更概要 (必須)
変更ファイル: src/cli/main.py, task.md, diff.md, Changelog.md
収集→分類→生成→出力の接続フローをCLIに実装し、タスクを一部Done化。

# 3. 確認方法 (必須)
Get-Content -Raw src/cli/main.py
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0059） 収集→出力接続タスクの追加

### 概要
* `task.md`に収集→分類→生成→出力の接続タスクを追加した。

### 関連タスク
* Task: 収集→分類→生成→出力の接続作業（CLI通常フローに統合）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
収集→出力の接続作業をタスク化するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
収集→分類→生成→出力の接続タスクを追加。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0058） 1テーマ=1Markdown出力整形タスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: 1テーマ=1Markdownの出力整形（ファイル名規則含む）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
1テーマ=1Markdown出力整形タスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0057） 1テーマ=1Markdown出力整形の明文化

### 概要
* `output_markdown_spec.md`に1テーマ=1ファイルの出力整形と命名ルールを追記した。

### 関連タスク
* Task: 1テーマ=1Markdownの出力整形（ファイル名規則含む）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
1テーマ=1Markdownの出力整形ルールを明文化するため。

# 2. 変更概要 (必須)
変更ファイル: output_markdown_spec.md, diff.md, Changelog.md
1テーマ=1ファイルの出力整形と命名ルールを追記。

# 3. 確認方法 (必須)
Get-Content -Raw output_markdown_spec.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0056） 3行構成テンプレートタスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: 3行構成テンプレートの生成ルール定義（関係性/要約/注意点）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
3行構成テンプレートタスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0055） 3行構成テンプレート生成ルールの明文化

### 概要
* `output_markdown_spec.md`に3行構成テンプレートの生成ルールを追記した。

### 関連タスク
* Task: 3行構成テンプレートの生成ルール定義（関係性/要約/注意点）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
3行構成テンプレートの生成ルールを明文化するため。

# 2. 変更概要 (必須)
変更ファイル: output_markdown_spec.md, diff.md, Changelog.md
3行構成テンプレートの生成ルールを追記。

# 3. 確認方法 (必須)
Get-Content -Raw output_markdown_spec.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0054） 無関係論文4章割り当てタスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: 無関係論文セクションの4章割り当てロジック設計

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
無関係論文4章割り当てタスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0053） 無関係論文4章割り当てロジックの明文化

### 概要
* `output_markdown_spec.md`に無関係論文の4章割り当てルールを追記した。

### 関連タスク
* Task: 無関係論文セクションの4章割り当てロジック設計

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
無関係論文セクションの4章割り当てロジックを明文化するため。

# 2. 変更概要 (必須)
変更ファイル: output_markdown_spec.md, diff.md, Changelog.md
無関係論文の4章割り当てルールを追記。

# 3. 確認方法 (必須)
Get-Content -Raw output_markdown_spec.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0052） 分類ルールタスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: 関連/広域/無関係の分類ルールを定義（判定軸と比率）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
分類ルールタスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0051） 分類ルールの明文化

### 概要
* `openalex_api_memo.md`に分類ルール（判定軸/比率）を追記した。

### 関連タスク
* Task: 関連/広域/無関係の分類ルールを定義（判定軸と比率）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
関連/広域/無関係の分類ルールを明文化するため。

# 2. 変更概要 (必須)
変更ファイル: openalex_api_memo.md, diff.md, Changelog.md
判定軸と比率を追記。

# 3. 確認方法 (必須)
Get-Content -Raw openalex_api_memo.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0050） 取得数制御タスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: 取得数制御（合計500本）と過不足時の補充ルール設計

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
取得数制御タスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0049） 取得数制御ルールの明文化

### 概要
* `openalex_api_memo.md`に取得数制御と補充ルールを追記した。

### 関連タスク
* Task: 取得数制御（合計500本）と過不足時の補充ルール設計

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
取得数制御と補充ルールの最小方針を明文化するため。

# 2. 変更概要 (必須)
変更ファイル: openalex_api_memo.md, diff.md, Changelog.md
取得数制御/補充/過剰時のルールを追記。

# 3. 確認方法 (必須)
Get-Content -Raw openalex_api_memo.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0048） abstract優先フィルタタスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: abstractあり優先のフィルタ実装

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
abstractあり優先のフィルタタスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0047） abstract優先フィルタの追加

### 概要
* `src/pipeline/filter.py`にabstract優先の並び替え関数を追加した。

### 関連タスク
* Task: abstractあり優先のフィルタ実装

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
abstractあり優先のフィルタ実装を追加するため。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/filter.py, diff.md, Changelog.md
abstract優先の並び替え関数を追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/pipeline/filter.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0046） 収集パイプライン雛形タスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: 収集パイプライン雛形（検索→候補→フィルタ）を作成

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
収集パイプライン雛形タスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0045） 収集パイプライン雛形の追加

### 概要
* `src/pipeline/collect.py`に検索→候補→フィルタの最小パイプラインを追加した。

### 関連タスク
* Task: 収集パイプライン雛形（検索→候補→フィルタ）を作成

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
収集パイプライン雛形（検索→候補→フィルタ）を追加するため。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/collect.py, diff.md, Changelog.md
収集→フィルタの最小パイプライン関数を追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/pipeline/collect.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0044） 結果の停止条件タスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: OpenAlex結果の停止条件（十分数/低関連/空ページ）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex結果の停止条件タスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0043） 結果の停止条件の明文化

### 概要
* `openalex_api_memo.md`に停止条件を追記した。

### 関連タスク
* Task: OpenAlex結果の停止条件（十分数/低関連/空ページ）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex結果の停止条件を明文化するため。

# 2. 変更概要 (必須)
変更ファイル: openalex_api_memo.md, diff.md, Changelog.md
停止条件（十分数/空ページ/低関連）を追記。

# 3. 確認方法 (必須)
Get-Content -Raw openalex_api_memo.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0042） abstract復元失敗時の扱いタスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: OpenAlex abstract復元失敗時の扱い

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex abstract復元失敗時の扱いタスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0041） abstract復元失敗時の扱いの明文化

### 概要
* `openalex_api_memo.md`にabstract復元失敗時の扱いを追記した。

### 関連タスク
* Task: OpenAlex abstract復元失敗時の扱い

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex abstract復元失敗時の扱いを明文化するため。

# 2. 変更概要 (必須)
変更ファイル: openalex_api_memo.md, diff.md, Changelog.md
abstract復元失敗時のルールを追記。

# 3. 確認方法 (必須)
Get-Content -Raw openalex_api_memo.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0040） フィールド欠損ポリシータスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: OpenAlexレスポンスのフィールド欠損ポリシー定義

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlexフィールド欠損ポリシータスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0039） フィールド欠損ポリシーの明文化

### 概要
* `openalex_api_memo.md`にフィールド欠損時の扱いを追記した。

### 関連タスク
* Task: OpenAlexレスポンスのフィールド欠損ポリシー定義

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlexレスポンスのフィールド欠損ポリシーを明文化するため。

# 2. 変更概要 (必須)
変更ファイル: openalex_api_memo.md, diff.md, Changelog.md
必須/許容フィールドの欠損ルールを追記。

# 3. 確認方法 (必須)
Get-Content -Raw openalex_api_memo.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0038） 重複排除ポリシータスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: OpenAlex重複排除ポリシー（ID/DOI重複の扱い）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex重複排除ポリシータスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0037） 重複排除ポリシーの明文化

### 概要
* `openalex_api_memo.md`にID/DOI重複排除ルールを追記した。

### 関連タスク
* Task: OpenAlex重複排除ポリシー（ID/DOI重複の扱い）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex重複排除ポリシー（ID/DOI）を明文化するため。

# 2. 変更概要 (必須)
変更ファイル: openalex_api_memo.md, diff.md, Changelog.md
重複排除の判定キーとルールを追記。

# 3. 確認方法 (必須)
Get-Content -Raw openalex_api_memo.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0036） リトライ/バックオフ方針タスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: OpenAlexリトライ/バックオフ方針の策定

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlexリトライ/バックオフ方針タスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0035） リトライ/バックオフ方針の明文化

### 概要
* `openalex_api_memo.md`にリトライ/バックオフの最小方針を追記した。

### 関連タスク
* Task: OpenAlexリトライ/バックオフ方針の策定

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlexリトライ/バックオフの最小方針を明文化するため。

# 2. 変更概要 (必須)
変更ファイル: openalex_api_memo.md, diff.md, Changelog.md
リトライ/バックオフ方針を追記。

# 3. 確認方法 (必須)
Get-Content -Raw openalex_api_memo.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0034） ページング/レート制御タスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: OpenAlexページング/レート制御の方針確定

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlexページング/レート制御タスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0033） ページング/レート制御方針の明文化

### 概要
* `openalex_api_memo.md`にページング/レート制御の最小方針を追記した。

### 関連タスク
* Task: OpenAlexページング/レート制御の方針確定

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlexページング/レート制御の最小方針を明文化するため。

# 2. 変更概要 (必須)
変更ファイル: openalex_api_memo.md, diff.md, Changelog.md
ページング/レート制御の最小方針を追記。

# 3. 確認方法 (必須)
Get-Content -Raw openalex_api_memo.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0032） OpenAlex検索クエリ拡張タスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: OpenAlex検索クエリの拡張（include/exclude/field/goalの重み付け）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex検索クエリ拡張タスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0031） OpenAlex検索クエリ拡張の明文化

### 概要
* `openalex_api_memo.md`に重み付け方針を追記した。

### 関連タスク
* Task: OpenAlex検索クエリの拡張（include/exclude/field/goalの重み付け）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex検索クエリの拡張方針（重み付け）を明文化するため。

# 2. 変更概要 (必須)
変更ファイル: openalex_api_memo.md, diff.md, Changelog.md
include/exclude/field/goalの重み付け方針を追記。

# 3. 確認方法 (必須)
Get-Content -Raw openalex_api_memo.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0030） OpenAlex検索クエリ設計タスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: OpenAlex検索クエリ設計（入力→検索語の生成ルール）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex検索クエリ設計タスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0029） OpenAlex検索クエリ設計の明文化

### 概要
* `openalex_api_memo.md`に入力→検索語の生成ルールを追記した。

### 関連タスク
* Task: OpenAlex検索クエリ設計（入力→検索語の生成ルール）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex検索クエリ設計（入力→検索語の生成ルール）を明文化するため。

# 2. 変更概要 (必須)
変更ファイル: openalex_api_memo.md, diff.md, Changelog.md
入力→検索語の生成ルールを追記。

# 3. 確認方法 (必須)
Get-Content -Raw openalex_api_memo.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0028） OpenAlex最小利用方針タスクの完了反映

### 概要
* `task.md`で該当タスクをDoneへ移動した。

### 関連タスク
* Task: OpenAlex APIの最小利用方針を整理（必須フィールド・取得順）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex APIの最小利用方針を整理タスクを完了へ移動するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
To Doの該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-11（CL-0027） OpenAlex最小利用方針の明文化

### 概要
* `openalex_api_memo.md`に必須フィールドの優先度と取得順を追記した。

### 関連タスク
* Task: OpenAlex APIの最小利用方針を整理（必須フィールド・取得順）

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex APIの最小利用方針（必須フィールド・取得順）を明文化するため。

# 2. 変更概要 (必須)
変更ファイル: openalex_api_memo.md, diff.md, Changelog.md
必須フィールドの優先度と取得順を追記。

# 3. 確認方法 (必須)
Get-Content -Raw openalex_api_memo.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0026） 分類ロジックの改良

### 概要
* `src/pipeline/classify.py`にキーワードスコアリングを追加した。

### 関連タスク
* Task: 関連/広域/無関係の分類ルールを定義

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
分類ロジックをキーワードベースに改良し、暫定精度を上げるため。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/classify.py, diff.md, Changelog.md
include/excludeキーワードによるスコアリングとラウンドロビン分配を追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/pipeline/classify.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0025） OpenAlexタスクの再細分化

### 概要
* `task.md`のOpenAlex関連タスクをより詳細に分割した。

### 関連タスク
* Task: OpenAlexタスク分解

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex関連タスクをさらに細分化し、実装観点を明確にするため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
OpenAlex検索・取得・停止条件・重複排除などのタスクを追加。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0024） エクスポート雛形の追加

### 概要
* `src/pipeline/export.py`にMarkdown出力関数を追加した。

### 関連タスク
* Task: 1テーマ=1Markdownの出力整形

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
Markdown出力用のエクスポート雛形を追加するため。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/export.py, diff.md, Changelog.md
OutputDocumentのMarkdown出力関数を追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/pipeline/export.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0023） 生成雛形の追加

### 概要
* `src/pipeline/generate.py`に仮生成ロジックを追加した。

### 関連タスク
* Task: 3行構成テンプレートの生成ルール定義

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
生成ロジックの雛形を追加し、OutputEntry生成の基盤を用意するため。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/generate.py, diff.md, Changelog.md
OutputEntryの仮生成関数を追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/pipeline/generate.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0022） フィルタ雛形の追加

### 概要
* `src/pipeline/filter.py`にフィルタ関数を追加した。

### 関連タスク
* Task: abstractあり優先のフィルタ実装

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
収集済みWorkのフィルタリング雛形を追加するため。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/filter.py, diff.md, Changelog.md
abstract有無フィルタと件数制限の関数を追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/pipeline/filter.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0021） 収集テスト手順の追記

### 概要
* `docs/cli_usage.md`に`--collect-test`手順を追記した。

### 関連タスク
* Task: CLI運用整備

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex収集テスト手順を追記し、CLIの利用方法を補完するため。

# 2. 変更概要 (必須)
変更ファイル: docs/cli_usage.md, diff.md, Changelog.md
--collect-testの手順とパラメータ説明を追加。

# 3. 確認方法 (必須)
Get-Content -Raw docs/cli_usage.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0020） 収集テストCLIの追加

### 概要
* `src/cli/main.py`に収集テスト用のコマンドを追加した。

### 関連タスク
* Task: OpenAlex収集テスト

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex収集の最小テストコマンドをCLIに追加するため。

# 2. 変更概要 (必須)
変更ファイル: src/cli/main.py, diff.md, Changelog.md
--collect-testオプションと収集確認フローを追加。

# 3. 確認方法 (必須)
python -m src.cli.main --collect-test --input data\samples\theme.json --per-page 5 --max-pages 1

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0019） OpenAlexテスト手順の追記

### 概要
* `docs/cli_usage.md`にOpenAlexテストコマンドを追記した。

### 関連タスク
* Task: CLI運用整備

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlexテスト手順を明文化し、CLIの利用方法を補完するため。

# 2. 変更概要 (必須)
変更ファイル: docs/cli_usage.md, diff.md, Changelog.md
OpenAlexテストコマンドとパラメータ説明を追記。

# 3. 確認方法 (必須)
Get-Content -Raw docs/cli_usage.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0018） OpenAlexテストCLIの追加

### 概要
* `src/cli/main.py`にOpenAlexテスト用のコマンドを追加した。

### 関連タスク
* Task: OpenAlex接続テスト

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlex APIを呼んで正規化まで通す最小CLIコマンドを追加するため。

# 2. 変更概要 (必須)
変更ファイル: src/cli/main.py, diff.md, Changelog.md
--openalex-testオプションと取得確認フローを追加。

# 3. 確認方法 (必須)
python -m src.cli.main --openalex-test --query "domain shift" --per-page 3

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0017） OpenAlex正規化の追加

### 概要
* `src/openalex/parser.py`にレスポンス正規化を追加した。

### 関連タスク
* Task: OpenAlex正規化

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
OpenAlexレスポンスの正規化を追加し、Work型への変換を可能にするため。

# 2. 変更概要 (必須)
変更ファイル: src/openalex/parser.py, diff.md, Changelog.md
abstract復元とWork変換ロジックを追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/openalex/parser.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0016） 品質評価観点の整理

### 概要
* `docs/quality_eval.md`を追加し、評価観点を明文化した。

### 関連タスク
* Task: 品質評価観点の整理

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
品質評価観点を整理し、出力確認の基準を明文化するため。

# 2. 変更概要 (必須)
変更ファイル: docs/quality_eval.md, task.md, diff.md, Changelog.md
評価観点をドキュメント化し、タスクをDone化。

# 3. 確認方法 (必須)
Get-Content -Raw docs/quality_eval.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0015） サンプルテーマ3件の生成

### 概要
* サンプル入力2件を追加し、出力生成を完了した。

### 関連タスク
* Task: サンプルテーマ3件の生成・レビュー

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
サンプルテーマ3件の生成と出力確認を完了し、タスクに反映するため。

# 2. 変更概要 (必須)
変更ファイル: data/samples/theme_social.json, data/samples/theme_energy.json, task.md, diff.md, Changelog.md
追加/更新: サンプル入力2件を追加し、出力を生成。

# 3. 確認方法 (必須)
python -m src.cli.main --input data\samples\theme_social.json --out output\sample_social
python -m src.cli.main --input data\samples\theme_energy.json --out output\sample_energy

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0014） モック論文の追加

### 概要
* 出力Markdownにモック論文1件を出力するようにした。

### 関連タスク
* Task: MVP出力の見た目確認

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
MVP出力にサンプル論文1件を含め、見た目と構造を確認できるようにするため。

# 2. 変更概要 (必須)
変更ファイル: src/core/output_spec.py, diff.md, Changelog.md
モック論文1件を初期セクションへ挿入するロジックを追加。

# 3. 確認方法 (必須)
python -m src.cli.main --input data\samples\theme.json --out output
Get-Content -Raw output\brainstorm_output.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0013） セクション構成タスクの完了反映

### 概要
* `task.md`で「出力Markdownのセクション構成を確定」をDoneへ移動した。

### 関連タスク
* Task: 出力Markdownのセクション構成を確定

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
出力Markdownのセクション構成タスクを完了として反映するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
task.mdで該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0012） CLI使用手順の明確化

### 概要
* `docs/cli_usage.md`に出力ファイル名を追記した。

### 関連タスク
* Task: CLI運用整備

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
CLI出力ファイル名を明示し、利用者が成果物を把握しやすくするため。

# 2. 変更概要 (必須)
変更ファイル: docs/cli_usage.md, diff.md, Changelog.md
CLI実行手順に出力ファイル名を追記。

# 3. 確認方法 (必須)
Get-Content -Raw docs/cli_usage.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0011） サンプル入力と出力確認

### 概要
* `data/samples/theme.json`を作成し、CLIでMarkdown出力を確認した。

### 関連タスク
* Task: MVP出力確認

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
MVP確認用のサンプル入力を追加し、Markdown出力の実行確認を可能にするため。

# 2. 変更概要 (必須)
変更ファイル: data/samples/theme.json, diff.md, Changelog.md
サンプル入力を作成し、CLIで出力生成を確認。

# 3. 確認方法 (必須)
python -m src.cli.main --input data\samples\theme.json --out output
Get-Content -Raw output\brainstorm_output.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0010） 最小Markdown出力経路の追加

### 概要
* 解析前でも雛形のMarkdownが出力できるようにした。

### 関連タスク
* Task: MVPの最小出力

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
MVPとしてMarkdown出力が得られる最小経路を用意するため。

# 2. 変更概要 (必須)
変更ファイル: src/core/output_spec.py, src/cli/main.py, diff.md, Changelog.md
最小のMarkdown構成生成ロジックと出力処理を追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/core/output_spec.py
Get-Content -Raw src/cli/main.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0009） CLI入力読み込みの最小実装

### 概要
* `src/cli/main.py`に入力JSON読み込みと正規化出力を追加した。

### 関連タスク
* Task: CLI入力読み込み

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
CLIで入力JSONを読み込み、正規化結果を出力できる最小実装を追加するため。

# 2. 変更概要 (必須)
変更ファイル: src/cli/main.py, diff.md, Changelog.md
JSON読み込みとバリデーションのフローを追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/cli/main.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0008） スキーマ定義タスクの完了反映

### 概要
* `task.md`で「入力→内部表現のスキーマ定義」をDoneへ移動した。

### 関連タスク
* Task: 入力→内部表現のスキーマ定義

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
入力→内部表現のスキーマ定義タスクを完了として反映するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
task.mdで該当タスクをDoneへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0007） 内部モデルの追加

### 概要
* `src/core/models.py`にデータモデルを追加した。

### 関連タスク
* Task: 入力→内部表現のスキーマ定義

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
内部表現のデータモデルを定義し、Phase 1の構造を明確化するため。

# 2. 変更概要 (必須)
変更ファイル: src/core/models.py, diff.md, Changelog.md
Theme/Work/Outputのデータモデルを追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/core/models.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0006） 入力スキーマの実装

### 概要
* `src/core/input_schema.py`にバリデーション/正規化を実装した。

### 関連タスク
* Task: 入力→内部表現のスキーマ定義

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
CLI入力の正規化とバリデーションを行うための最小実装を追加するため。

# 2. 変更概要 (必須)
変更ファイル: src/core/input_schema.py, diff.md, Changelog.md
docs/input_min_spec.mdに準拠したバリデーション/正規化ロジックを追加。

# 3. 確認方法 (必須)
Get-Content -Raw src/core/input_schema.py

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0005） 入力仕様の最小セット確定

### 概要
* Phase 1のCLI入力の最小要件を明文化した。
* `task.md`で当該タスクを完了に移動した。

### 関連タスク
* Task: 入力仕様の最小セット確定

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
入力仕様の最小セットを確定し、Phase 1のCLI入力要件を明文化するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, diff.md, Changelog.md
追加ファイル: docs/input_min_spec.md
入力仕様の最小セットを定義し、タスクをDone化。

# 3. 確認方法 (必須)
Get-Content -Raw docs/input_min_spec.md
Get-Content -Raw task.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0004） memo運用の整理

### 概要
* `memo.md`を長文共有用の空テンプレに戻した。
* CLI実行手順を`docs/cli_usage.md`へ移動した。

### 関連タスク
* Task: 運用ルール調整

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
memo.mdを長文共有用に戻し、運用ルールに沿って機能的な記述をdocsへ移すため。

# 2. 変更概要 (必須)
変更ファイル: memo.md, diff.md, Changelog.md
追加ファイル: docs/cli_usage.md
memo.mdの内容を簡素化し、CLI実行手順をdocs/cli_usage.mdへ移動。

# 3. 確認方法 (必須)
Get-Content -Raw memo.md
Get-Content -Raw docs/cli_usage.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0003） CLI実行テンプレ追加

### 概要
* `scripts/run_cli.ps1`に最低限の実行テンプレを追加した。

### 関連タスク
* Task: Phase 1準備

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
Phase 1のCLI実行テンプレを追加し、実行方法を固定するため。

# 2. 変更概要 (必須)
変更ファイル: scripts/run_cli.ps1, diff.md, Changelog.md
scripts/run_cli.ps1に最小実行テンプレを追加。

# 3. 確認方法 (必須)
Get-Content -Raw scripts/run_cli.ps1

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0002） CLI雛形と仕様メモの追加

### 概要
* Phase 1のCLI雛形ディレクトリと空ファイルを作成した。
* 入力/収集/出力の仕様メモと実行手順を整備した。

### 関連タスク
* Task: Phase 1準備

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
Phase 1の準備として、CLI雛形と仕様ドキュメント、運用ファイルの整備を反映するため。

# 2. 変更概要 (必須)
変更ファイル: task.md, memo.md, diff.md, Changelog.md
追加ファイル: input_schema.md, openalex_api_memo.md, output_markdown_spec.md, cli_directory_layout.md
新規ディレクトリ: scripts/, src/, docs/, data/, output/ と配下
CLI雛形ファイルを追加し、仕様メモをdocs/へ配置

# 3. 確認方法 (必須)
Get-ChildItem -Force
Get-Content -Raw task.md
Get-Content -Raw memo.md
Get-Content -Raw cli_directory_layout.md

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## 2026-02-10（CL-0001） 初期ドキュメント整備と仕様メモ作成

### 概要
* 本計画向けにテンプレート群を調整し、運用ファイルをメインへ配置した。
* 入力/収集/出力の最小仕様メモを追加した。

### 関連タスク
* Task: 初期ドキュメント整備

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
プロジェクト運用ファイルを本計画に合わせて整備し、Phase 1実装に必要な仕様メモを追加するため。

# 2. 変更概要 (必須)
変更ファイル: agent.md, task.md, roadmap.md, RoadMap.md, input_schema.md, openalex_api_memo.md, output_markdown_spec.md
追加ファイル: diff.md, review.md, Changelog.md, Gemini.md, memo.md
テンプレートを本計画向けに調整し、入力/収集/出力の仕様メモを作成。

# 3. 確認方法 (必須)
各ファイルの内容確認: Get-Content -Raw <file>

# 4. 既知の課題・リスク (必須)
なし
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---

## YYYY-MM-DD（CL-####） [変更の要旨を一文で記述]

### 概要
* [変更点のサマリーを1〜3行で記述]

### 関連タスク
* Task: [関連するタスクIDなどを記述]

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
...

# 2. 変更概要 (必須)
...

# 3. 確認方法 (必須)
...

# 4. 既知の課題・リスク (必須)
...
```

### レビュー結果（レビュー後に追記）
> `review.md`でのレビュー完了後、その内容をここに要約して記録する。
*   **結果**: [PASS / PASS WITH NOTES / BLOCK]
*   **コメント**:
    *   [レビューコメントをここに記述]

---
