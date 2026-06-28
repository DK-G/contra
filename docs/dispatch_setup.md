# Dispatch セットアップ（Claude Code on the web で by シリーズを委譲モードで回す）

このドキュメントは、contra を **Claude Code on the web（Dispatch＝クラウドセッション）** で
そのまま回すための環境設定をまとめる。ゴールは、Dispatch した新セッションが
**bybridge を含む by シリーズを「キー不要の委譲モード」で実行できる**こと。

## 0. 何が要るか（最重要）

委譲モードでは LLM 判定・生成は**呼び出し側エージェント（あなた＝Claude/Opus）自身の推論**で行う
（設計の正本: [`docs/research/mcp_subscription_delegation.md`](research/mcp_subscription_delegation.md)）。
したがって必要なのは **LLM API キーではない**。要るのは次の3つだけ:

1. **計算ホスト** — Python 3.10+（依存は標準ライブラリ中心）
2. **OpenAlex への egress** — `api.openalex.org` へ HTTPS で到達できること
3. **ツール登録** — contra の stdio MCP サーバが Dispatch セッションに登録されていること

このうち **2 の OpenAlex egress が肝**。contra は近傍シードを OpenAlex から取得して初めて
bridge プールを作る。ここが開いていないと bybridge は **0 件で止まる**（直近の Dispatch 失敗の
真因はキー未設定ではなく、egress ポリシーが `api.openalex.org` を 403 で拒否していたこと）。

## 1. ネットワークポリシー（Web UI でしか変えられない）

> **重要:** ネットワークポリシーは Claude Code on the web の **環境編集ダイアログの「Network access」**
> でのみ変更できる。**コードや設定ファイルからは変えられない**（このリポジトリの `.mcp.json` や
> `.claude/settings.json` では設定不可）。セッション内からも変更できない。

### 推奨: Custom + 必要ドメインを許可

環境編集ダイアログで **Network access を `Custom`** にし、**Allowed domains** に1行ずつ追加する:

```
api.openalex.org
```

↑ **bybridge / by シリーズの必須**。これだけで委譲モードの by シリーズは回る。

`--fulltext`（OA 全文補強）も使う場合のみ、さらに次を追加:

```
arxiv.org
www.ebi.ac.uk
api.fatcat.wiki
api.core.ac.uk
doi.org
dx.doi.org
```

**「Also include default list of common package managers」はチェックを維持する**
（pypi / GitHub の既定許可が残り、`git push` や `pip` を壊さない）。

### 代替: Full（全許可）

個人 / 研究用途なら **Network access を `Full`** にすれば全ドメイン許可で一発。
ドメインを個別管理したくなければこちらでよい。

### 反映タイミング

ポリシーは**環境単位**で効く。保存後は**新しいセッションを起こし直す**と反映される
（稼働中のセッションには遡って効かない）。

## 2. ツール登録（このリポジトリに同梱済み）

このブランチには Dispatch 用の設定が既にコミットされている。追加作業は不要。

- **[`.mcp.json`](../.mcp.json)** — contra の stdio MCP サーバをプロジェクトスコープで登録する。
  起動コマンドは POSIX 形式で、リポジトリルートを cwd として（プロジェクトスコープの
  MCP サーバはワークスペースルートから起動される）次を実行する:

  ```
  python -u -m src.cli.main --mcp
  ```

  これで Dispatch セッションから次の MCP ツールが使える:
  `bybridge_collect` / `byserendipity_discover` / `byrepo_search` /
  `bynote_link_concepts` / `delegate_finalize`。

  > Linux コンテナで `python` が見つからない場合は `python3` に読み替える
  > （`.mcp.json` の `command` を `python3` に変更）。Windows ローカルでは
  > [`scripts/run_mcp.cmd`](../scripts/run_mcp.cmd) を使う。

- **[`.claude/settings.json`](../.claude/settings.json)** — SessionStart フックを登録する。
  Dispatch した各セッションの開始時に [`.claude/hooks/session_start.py`](../.claude/hooks/session_start.py)
  が走り、次を1回だけ報告する（リトライ・迂回はしない）:
  - Python 3.10+ の確認
  - `api.openalex.org` への到達性プローブ:
    - OK なら **`OpenAlex reachable`**
    - 403 / 失敗なら **`OpenAlex egress blocked — allow api.openalex.org in this
      environment's Network access (Custom)`**

  後者が出たら、上の §1 に従って Web UI で `api.openalex.org` を許可し、セッションを起こし直す。

## 3. 委譲モードでの bybridge 実行（キー無しループ）

運用定義の正本は [`docs/agent_rules/bybridge.md`](agent_rules/bybridge.md)。要点だけ:

1. **(contra・キー無し) 生候補収集**: `bybridge_collect` を `raw_only=true` で呼ぶ。
   contra が近傍シード→bridge プール→`cites:` 交差候補→ホームドメイン除外までを
   決定論＋OpenAlex のみで実行し、生候補を返す（LLM 不使用＝キー不要）。
2. **(エージェント) 採点**: 各候補を `purpose_sim` × `mechanism_dist` 等で採点する
   （あなた自身の推論。API キー不要）。
3. **(contra・キー無し) post-gate と出力**: 採点済み候補を `delegate_finalize` に渡すと、
   決定論ゲート（anomaly / near-cap / serendipity / hollow / percentile / output_floor / M3）が
   再適用され、Track B markdown が返る。

CLI からの素振り確認（OpenAlex が開いていれば実結果、ブロック中ならクリーンに「egress blocked」相当を報告）:

```bash
python scripts/run_bybridge.py data/samples/theme_military_c2_multiagent.json
```

## 4. 制約（重要）

- ネットワークポリシーは**セッション内から変更できない**。`api.openalex.org` が 403 / タイムアウトなら
  **リトライ・迂回せず**「`api.openalex.org` を許可してほしい」と報告して止めること。
- スコア設計値（`purpose_sim × mechanism_dist`、`0.20 / 0.50 / 0.35` 等）や `models.py` は
  変更しない（[`spec.md`](../spec.md) 禁則）。この環境整備で touch するのは実行環境設定のみ。
- 委譲モードの想定ユーザーは**作者自身（個人 / 研究用途）**。製品バックエンドとして
  不特定多数に叩かせる形にはしない。
