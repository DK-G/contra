# Standard Tool Configuration Guide

このプロジェクトで使用する「精鋭 6 ツール」のセットアップと活用方法のガイドです。

## 1. deep-research（旧 `bynote`。2026-10-12 に NotebookLM から置き換え）
- **目的**: 不確実な判断の前に、根拠の強さを分けた調査報告書を 1 本作る。
- **設定**: 鍵もログインも要らない。手順と置き場所の正本は `D:\dev\docs\skills\bynote.md`。
- **活用**: 問いを 1 つに絞って回し、報告書の結論と「不明」の一覧を判断の材料にする。メモの概念リンク（`bynote_link_concepts`）は別物で、[`docs/agent_rules/bynote.md`](docs/agent_rules/bynote.md) を参照。

## 2. Sequential Thinking (`bythink`)
- **目的**: AI の「考えの跡」を可視化し、設計ミスを未然に防ぐ。
- **設定**: Anthropic 系の思考プロセス、または Markdown での段階的考察。
- **活用**: アーキテクチャ決定前に 5 ステップ以上の深掘りを行い、`ARCHITECTURE.md` に結果を記録する。

## 3. Stitch (`bystitch`)
- **目的**: 手作業では不可能な「プレミアムな質感」の UI を数秒で生成する。
- **設定**: プロジェクトごとに `stitch-metagmo` などの MCP サーバーを接続。
- **活用**: `generate_screen_from_text` でプロトタイプを作り、`apply_design_system` でブランドカラーを適用する。

## 4. GitHub MCP
- **目的**: リポジトリ操作とコミュニケーションを AI 内で完結させる。
- **設定**: パーソナルアクセストークンを MCP サーバーに設定済みであることを確認。
- **活用**: `create_pull_request` や `get_issue` を介して、タスクの進捗を同期する。

## 5. Jules (`byjules`)
- **目的**: 「動くコード」を「美しいコード」に昇華させる。
- **設定**: Google Jules の MCP 連携、または IDE 統合機能。
- **活用**: 複雑な TypeScript の型定義や、React のパフォーマンス最適化が必要な局面で `byjules` フローを呼び出す。

## 6. Brave Search / Firecrawl (`bysearch`)
- **目的**: LLM の知識カットオフを打破し、今この瞬間の正解を取得する。
- **設定**: Brave Search API または Firecrawl MCP。
- **活用**: ライブラリの最新メジャーアップデート、API の破壊的変更の調査に使用する。
