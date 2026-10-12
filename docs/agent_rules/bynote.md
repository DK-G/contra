---
name: bynote_link_concepts
description: メモを Purpose/Mechanism に分解し、類推ドメインと Serendipity Bridge の問いを返す Contra の MCP ツール `bynote_link_concepts` の運用ノート。調査と意思決定の flow（旧 bynote）は 2026-10-12 にハブの deep-research へ移った。
---

# bynote_link_concepts（概念リンク）

**2026-10-12 改訂。** この文書は以前、`bynote` を「メモ分析から Phase 0 の意思決定までの 1 つの flow」として定義していた。その flow の調査と意思決定は、ハブの `deep-research` へ置き換わった（正本: `D:\dev\docs\skills\bynote.md`）。置き換え後の手順は NotebookLM も概念リンクも含まない。

ここに残すのは、Contra の MCP ツール `bynote_link_concepts` の使い方だけである。ツール名は実装（`_execute_bynote`）に合わせて据え置く。

## 何をするツールか

- 曖昧なメモや仮説を Purpose（何を実現したいか）と Mechanism（どう実現するか）に分解する
- 別ドメインの構造類推を 2〜3 件出す
- 前提を入れ替えて発想を跳ばすための問い（Serendipity Bridge）を作る

LLM を 1 回呼ぶだけで、外部の資料は集めない。

## 呼び出し

- `このメモから類推先を出して`
- `Purpose/Mechanism に分けて`

`bynote`・`フェーズ0`・`ディープリサーチ` と言われた場合は、このツールではなくハブの `deep-research` を回す。

## Inputs

- `note_content`（必須）: 分析対象のメモ、アイデア、設計仮説。会話と一次資料から組み立ててよい
- `theme_overview`（任意）: メモを適用する背景テーマ。指定すると、そのテーマへ転用するときの接続ロジックも返る

## 出力

1. Purpose / Mechanism
2. 類推可能な別ドメイン 2〜3 件と、なぜ類推できるか
3. Serendipity Bridge の問い
4. 背景テーマへの接続ロジック（`theme_overview` を渡したときだけ）

## 実行条件

- ツール名: `mcp__contra__bynote_link_concepts`（ホストにより接頭辞が異なる場合は、末尾が `bynote_link_concepts` の Contra ツールを使う）
- 実装: `src/mcp_server.py::_execute_bynote`
- 現行実装は `gpt-4o-mini` を呼ぶため、`OPENAI_API_KEY` と `api.openai.com` への到達性が必要で、API 利用料が発生しうる。委譲モード（キー無し）は無い（[`../dispatch_setup.md`](../dispatch_setup.md) §0.5）。
- ツールが使えない場合は、呼び出し側エージェントが同じ出力を自分で作って先へ進める。

## 出力の扱い

- 出力は調査仮説であり、裏付けなしに採用判断へ直結させない。
- 類推先がホームドメインの中に留まることがある（[`../field_observations_seihai.md`](../field_observations_seihai.md) F-06）。返ってきた類推先がテーマと同じ分野でないかを確かめてから使う。
- 仮説を外部の資料で確かめたいときは、問いの形に直してハブの `deep-research` に渡す。
