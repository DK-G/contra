---
name: bybridge
description: contra の citation 2-hop bridge 収集を独立フローとして実行し、近傍シードの共有引用文献を経由した別ドメイン候補を選別・出力する named flow。
---

# Bybridge

この文書は contra における **citation 2-hop bridge flow** の運用定義とする。
会話では `bybridge で回して` または `bridge 経由で集めて` の形で呼び出す。

## Purpose

- 近傍シード論文の **共有引用文献（bridge）** を経由して、引用グラフ上は接続しているのにホームドメイン外にある論文を拾う
- byserendipity（LLM クエリによる遠ドメイン探索）とは別経路の、**引用構造ベース** の交差候補を供給する
- キーワード検索では到達できない「同じ基礎文献を踏む別分野」を可視化する

## Invocation

次のような明示依頼を受けたらこの flow を優先する。

- `bybridge`
- `bybridge で回して`
- `bridge 経由で集めて`
- `citation 2-hop だけ回して`
- `共有引用から遠い論文を引いて`

## Inputs

- `ThemeInput`
- `bridge_count`（最終出力件数）
- `seed_count`（bridge プール構築に使う近傍シード数）
- `raw_only`（true なら LLM 選別・生成を行わず交差候補リストのみ返す）
- 必要なら `output_floor`

## Workflow

1. テーマから近傍シード論文を収集する（`collect_and_filter`）
2. シードの referenced_works から bridge プールを構築する（共有参照優先 + round-robin）
3. OpenAlex `cites:` フィルタで bridge を引用する候補を収集し、シードの L0 ホームドメインを除外する（`collect_citation_candidates`）
4. 各候補が踏んだ bridge 本数を注記する
5. `raw_only` でなければ、シード由来の theme profile を使って `purpose_sim × mechanism_dist` で選別する（`select_track_b`）
6. 4部構成（概要 / 関連性 / 仮説 / 注意点）を生成する

## Output Expectations

- 候補ごとに次を含める
  - 共有 bridge 本数
  - serendipity score（LLM 選別時）
  - 4部構成（LLM 選別時）
- 収集診断（シード数 / bridge プール数 / 交差候補数）を冒頭に示す

## Non Goals

- LLM クエリによる遠ドメイン探索（byserendipity の領分）
- GitHub repository の実用性評価（byrepo の領分）
- 引用ネットワークの全量可視化
- bridge そのもの（基礎文献）の本文分析
