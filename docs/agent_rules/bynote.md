---
name: bynote
description: メモの概念リンクを起点に、調査・一次資料統合・意思決定まで進める統一 named flow。Contra MCP は Purpose/Mechanism 分解と Serendipity Bridge 生成を担当する。
---

# Bynote

`bynote` はメモ分析と Phase 0 の戦略設計を分けず、一つの flow として扱う。
Contra の `bynote_link_concepts` は、この flow の概念リンク工程を実行する MCP ツールであり、別名のルーチンではない。

## Purpose

- 曖昧なメモや仮説を Purpose（何を実現したいか）と Mechanism（どう実現するか）に分解する
- 別ドメインの構造類推と Serendipity Bridge の問いから、調査の視野を広げる
- 外部調査とプロジェクト一次資料を統合し、実行可能な方針へ収束させる

## Invocation

- `bynote`
- `bynote で進めて`
- `bynote で整理して`
- `フェーズ0から進めて`
- `このメモから類推先を出して`

## Inputs

- `note_content`（必須）: 分析対象のメモ、アイデア、設計仮説。会話と一次資料から組み立ててよい
- `theme_overview`（任意）: メモを適用する背景テーマ
- プロジェクト一次資料: README、task、plan、仕様、既存コード、判断ログ

## Workflow

1. 今回決める対象を一つに絞り、関連する一次資料から `note_content` と `theme_overview` を作る。
2. Contra MCP の `bynote_link_concepts` を呼び、次を得る。
   - Purpose / Mechanism
   - 類推可能な別ドメイン 2〜3件と接続理由
   - Serendipity Bridge の問い
   - 背景テーマへの接続ロジック
3. 出力を調査仮説として扱い、NotebookLM Deep Research 等で外部資料を収集する。MCP出力だけを根拠に結論を出さない。
4. 外部資料とプロジェクト一次資料を統合し、実装コスト、運用コスト、リスク、可逆性、既存構成、ユーザー価値で選択肢を比較する。
5. 推奨方針を確定し、重要な判断は `DECISION_LOG.md` に残す。

## MCP Execution

- ツール名: `mcp__contra__bynote_link_concepts`（ホストにより接頭辞が異なる場合は、末尾が `bynote_link_concepts` の Contra ツールを使う）
- 実装: `src/mcp_server.py::_execute_bynote`
- 現行実装は `gpt-4o-mini` を呼ぶため、`OPENAI_API_KEY` と `api.openai.com` への到達性が必要で、API利用料が発生しうる。
- ツールが使えない場合は、呼び出し側エージェントが同じ4項目を推論して先へ進める。概念リンク工程の不在だけで Phase 0 全体を止めない。

## Output Expectations

- 今回のテーマ
- Purpose / Mechanism
- 類推ドメインと接続理由
- Serendipity Bridge の問い
- 使用した調査ノートと主要資料
- 比較した選択肢
- 推奨方針と理由
- 判断記録と次の実装ステップ

