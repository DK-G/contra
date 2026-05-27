# Multi-Agent Coordination Protocol (Interchangeable Agents)

このドキュメントは、Antigravity, Claude, Codex, Jules などの複数の AI エージェントが、同じプロジェクトで円滑に交代・協調するための運用マニュアルです。

## 1. エージェントの役割と交換可能性

- **等価エージェント**: Antigravity, Claude, Codex は、互いに交換可能な主要作業主体です。
- **スペシャリスト**: Jules は、精密なリファクタリングや最終的な磨き上げを担当します。
- **引継ぎの原則**: どのエージェントが作業を開始しても、残されたドキュメントと Git 履歴だけで次のエージェントが 100% のコンテキストを復元できる状態を維持します。

## 2. 標準命名フロー (Named Flows)

作業の再現性を高めるため、以下のキーワードを用いて特定のワークフローを起動します。

| Flow Name | Description | Key Procedures |
| :--- | :--- | :--- |
| **`bynote`** | 戦略・知識統合 | `research_start` -> `poll` -> `import` -> `query` |
| **`bythink`** | 論理設計・設計 | `sequential_thinking` -> 設計案比較 -> `ARCHITECTURE.md` |
| **`bystitch`** | UI/UX 生成 | `generate_screen` -> `apply_design_system` -> `UI_DNA.md` |
| **`byjules`** | 最適化・磨き | 課題抽出 -> `byjules` 実行 -> 性能検証 |
| **`bysearch`** | 技術調査 | `search_web` -> `firecrawl` -> `RESEARCH_NOTES.md` |
| **`bygit`** | 引継ぎ・同期 | Commit `[agent]` -> `task.md` 更新 -> `walkthrough.md` |

## 3. Git 運用ルール

### 3.1 Mandatory Commit Prefixes
コミットメッセージの先頭に、作業したエージェント名を必ず含めてください。
- `[antigravity]: add feature X`
- `[claude]: fix bug in Y`
- `[codex]: refactor Z`
- `[jules]: optimize performance of A`

### 3.2 Handoff Checkpoint
エージェントを切り替える直前（トークン制限、休憩、他プロジェクトへの移動）には、必ず以下の作業を行ってください。
1. **Git Commit & Push**: 現在の変更を全てコミットし、プッシュする。
2. **Task Update**: `task.md` の完了した項目に `(by @agent_name)` を追記する。
3. **Walkthrough Entry**: `walkthrough.md` に「現在の到達点」と「次に行うべき具体的な一歩」を残す。

## 4. ツールセットの利用基準

以下の「精鋭 6 ツール」を標準として使い、認知負荷を最小限に抑えます。

1. **NotebookLM**: プロジェクト全体の戦略と過去の経緯の統合参照。
2. **Sequential Thinking**: 複雑なロジックを段階的に紐解く際の思考ログ。
3. **Stitch**: Premium UI の生成とデザイン DNA の維持。
4. **GitHub (MCP)**: Issue, PR, Review の一括管理。
5. **Jules**: 難易度の高いリファクタリングと最適化。
6. **Brave Search**: 外部の最新ライブラリ仕様やドキュメントの補完。
