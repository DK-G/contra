---
name: bybridge
description: contra の citation 2-hop bridge 収集を独立フローとして実行し、近傍シードの共有引用文献を経由した別ドメイン候補を選別・出力する named flow。委譲（キー無し・追加課金ゼロ）が既定。
---

# Bybridge

この文書は contra における **citation 2-hop bridge flow** の運用定義とする。
会話では `bybridge で回して` または `bridge 経由で集めて` の形で呼び出す。

## Purpose

- 近傍シード論文の **共有引用文献（bridge）** を経由して、引用グラフ上は接続しているのにホームドメイン外にある論文を拾う
- byserendipity（semantic クエリによる遠ドメイン探索）とは別経路の、**引用構造ベース** の交差候補を供給する
- キーワード検索では到達できない「同じ基礎文献を踏む別分野」を可視化する

## Invocation

次のような明示依頼を受けたらこの flow を優先する。

- `bybridge`
- `bybridge で回して`
- `bridge 経由で集めて`
- `citation 2-hop だけ回して`
- `共有引用から遠い論文を引いて`

## 実行モード（委譲が既定）

**委譲（キー無し・追加課金ゼロ）を既定とする。** bybridge の収集（近傍シード→bridge プール→`cites:` 交差候補→ホーム除外→betweenness/共有数注記）は **すべて決定論＋OpenAlex のみで LLM 不使用**。よって `bybridge_collect` を `raw_only=true` で呼べば、エージェントの採点を待たずに生候補を取得できる。LLM が要るのは採点とプローズだけで、それは呼び出し側エージェント（Claude）が自分の推論で代行する＝メータ API キー不要。

## Workflow（委譲キー無しループ）

1. **（contra MCP・キー無し）生候補収集**: `mcp__contra__bybridge_collect` を `raw_only=true` で呼ぶ。contra が近傍シードを収集し、共有 referenced_works から bridge プールを構築、`cites:` で bridge を引用する候補を集めてシードのホームドメイン（primary_topic.field）を除外し、各候補に共有 bridge 本数＋betweenness（異分野連結度）を注記して **生候補リストを返す**。
   - 4部構成まで決定論で整形したいだけなら `raw_only=true, structured=true`（`assemble_keyless_bridge_document`）でキー無しの構造化 Track B ドキュメントが得られる（採点 0.0 のプレースホルダ）。
2. **（エージェント）採点**: 返ってきた各候補を SOLVENT（purpose × mechanism）で採点する。`purpose_sim`（<0.20 で anomaly 棄却）・`mechanism_dist`・`structural_depth`（<0.50 で hollow 棄却）・`has_causal_pm`・`connection_label`・`serendipity_rationale` を付与（byserendipity と同じ採点契約）。bridge 由来候補は betweenness/共有数が高いものを優先的に吟味する。
3. **（contra MCP・キー無し）post-gate と出力**: 採点済み候補を `mcp__contra__delegate_finalize` に渡し、決定論ゲート（anomaly / near-cap / serendipity / hollow / percentile / output_floor / fallback / M3）を再適用して Track B markdown を得る。
4. **（エージェント）プローズ仕上げ**: 4部構成を磨く（論文固有の発見に基づく）。

自己完結（メータ）モード＝`bybridge_collect` を `raw_only` 無しで呼ぶと contra が `select_track_b(use_llm=True)` と生成 LLM を呼ぶ（従量課金）。無人バッチ等でのみ使う。

## Inputs

- `ThemeInput`
- `bridge_count`（最終出力件数）
- `seed_count`（bridge プール構築に使う近傍シード数）
- `raw_only`（委譲では true）／`structured`（キー無し構造化整形が欲しいとき）
- `output_floor`（post-gate 段）

## Output Expectations

- 候補ごとに次を含める
  - 共有 bridge 本数 / 異分野ブリッジ（betweenness）
  - serendipity score（採点後）
  - 4部構成
- 収集診断（シード数 / bridge プール数 / 交差候補数）を冒頭に示す

## Non Goals

- semantic クエリによる遠ドメイン探索（byserendipity の領分）
- GitHub repository の実用性評価（byrepo の領分）
- 引用ネットワークの全量可視化
- bridge そのもの（基礎文献）の本文分析
