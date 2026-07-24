<!-- CURRENT-START / ここだけを常に最新に保つ。ここより下は履歴で、読むのは必要時のみ。 -->
## 現在地（2026-07-25）
- フェーズ: **実装は完了・Phase 1 の Done 判定待ち**。検索クエリ精度 Phase 2（bybridge）/ Phase 3（byserendipity）、キー無し委譲ループ（`delegate_finalize` ＋ 各 MCP の `structured` フラグ）、byrepo の A-RS1/A-RS2 配点移行、`fill_track_entries` の統合テストまで全て `[x]`。完了記録は `docs/archive/task-history.md` へ退避済み。
- 進行中: **MCP サーバとして実稼働中**（`byserendipity` / `byrepo` / `bybridge` / `bynote_link_concepts` / `delegate_finalize` がツールとして利用可能なことを 2026-07-25 に確認）。Track A「Git 実用アンカー設計」は設計5項目とも完了（`docs/specs/track_a_git_anchor_design.md`）。
- 次の一手:
  1. **Track B 品質評価を実施して Phase 1 を閉じる** — ①複数テーマでサンプル生成し「遠いが構造一致」の1本が安定して出るか ②Anomaly（無意味接続）と近接（マイオピア）の混入がないか ③「役に立つ可能性の仮説」が論文固有の発見に基づくか ④飽和ノート時に弱い候補で水増しされないか、を確認し **`docs/quality_eval.md` §4 表・§5 総評に記入**（ルーブリックと再現コマンドは整備済み）。
  2. Track A の discussion 観測は **GitHub Discussions が REST に一覧エンドポイントを持たず GraphQL 専用**のため保留中。着手するなら GraphQL 経路の導入から（dependents も同じ理由で対象外）。
- ★ブロッカー/外部待ち: 上記1の残5件は**全て「実 LLM API キーが必要」または「人間の質的判断が必要」**。**実装が Done 判定を追い越しており、人間が評価しない限り Phase 1 を閉じられない**のが唯一かつ最大のボトルネック。
- 直近の重い判断: **Web 化・課金は現時点では実装しない**（必要になったら Phase 2 として再評価）。PRF は bybridge の異分野目的と衝突するため不採用とし Track A 収集へ再配置。`spec.md` §7 の**スコア設計値（0.20 / 0.50 / 0.35）は不変**という禁則を守ること。判断の経緯は `DECISION_LOG.md`。
<!-- CURRENT-END -->

# 作業タスクリスト

`roadmap.md`からブレークダウンした、具体的な作業タスクを管理します。

---

## 作業中 (In Progress)

- [/] Track A Git実用アンカー設計
    - [x] 研究テーマに直接関連する OSS / GitHub repository を検索・収集する条件を定義する
    - [x] Track A を「近接論文アンカー」だけでなく「直接使える実装・制約・失敗パターンのアンカー」として再定義する
    - [x] Git 由来情報の信頼性評価（stars / activity / license / issue quality / last commit / README completeness）を設計する
    - [x] Track B の遠類推と混同しない表示区分・出力フォーマットを設計する
    - [x] 設計結果を `plan.md` 変更案または `docs/specs/` の設計メモにまとめる（`docs/specs/track_a_git_anchor_design.md`）
- [/] Phase 1 Done 判断: Track B 品質評価
    - [x] 評価ルーブリック・再現コマンド・記入式テーマ横断表を `docs/quality_eval.md` に整備（旧20本方針から現行 contrarian 4部構成へ刷新）
    - [ ] 複数テーマでサンプル生成し、「遠いが構造一致」の1本が安定して出るか確認する（実 LLM API 必要）
    - [ ] Anomaly（無意味接続）と近接（マイオピア）が混入していないか確認する
    - [ ] 「役に立つ可能性の仮説」が論文固有の発見に基づいているか確認する
    - [ ] 飽和ノート発生時に弱い候補で水増しされないことを確認する
    - [ ] 品質評価結果を `docs/quality_eval.md` の §4 表・§5 総評に追記する

---

## 未着手 (To Do)

- [x] 検索クエリ精度 Phase 2（bybridge）: co-citation 強度＋betweenness 代理（分野多様性）でブリッジ再ランク、ホームドメイン除外を L0 concepts → `dominant_field_ids`（primary_topic.field 除外）へ移行（**PRF は bybridge の異分野目的と衝突のため不採用＝Track A 収集へ再配置**）
- [x] 検索クエリ精度 Phase 3（byserendipity）: 標的化抽象（機能語へ再記述＋構造制約保持）、HyDE/Query2doc 接地＋OpenAlex semantic search、QA-Expand 多面化、round-trip / quality-gate の実行前検証
- [x] ローカル化: MCPクライアント委譲（キー無し運用・docs/research/mcp_subscription_delegation.md）
    - [x] (a) bybridge raw_only ＋ structured 整形でキー無し一周（`src/pipeline/delegate.py` ＋ MCP `bybridge` の `structured` フラグ）
    - [x] (b) classify.py の数値ゲート（anomaly/serendipity/struct_depth/near-domain cap/output_floor/M3）を LLM 採点から独立した純関数 `apply_post_gates` として切り出し post-gate 化
    - [x] (c) エージェント採点を受け取る JSON スキーマ定義＋委譲経路を追加（`finalize_delegated_document` ＋ MCP `delegate_finalize`）
    - [x] (d) byrepo/Track A の委譲（信頼性スコア＝決定論選別のためキー無し構造組み立てで完結。MCP `byrepo` の `structured` フラグ）
- [x] A-RS1: byrepo Pillar 2 (LMA) 改善
    - [x] 完成判定の床（採用シグナル＋過去 issue 活動＋高クローズ率の条件付きで 12〜15点床止め）を実装する
    - [x] 候補プール内相対正規化（プールをドメインサンプルとみなし相対順位で LMA を付与）を実装する
- [x] A-RS2: byrepo Pillar 1 配点移行（README 成熟度 → 時間・他人系シグナル）。GITHUB_TOKEN 事実上必須化とセット
    - [x] 先手: CI 実行履歴＋リリース刻みを verified maturity（最大12点）として導入し、リッチシグナル取得時のみ README 系をスケールして移譲する
    - [x] 「他人」系シグナル（外部コントリビュータ数 / owner 以外の起票者）を third_party（最大6点）として導入する（dependents は REST 非提供のため対象外）
- [/] Track A Git practical anchors に discussion 観測や score 内訳表示の改善を追加する
    - [x] score 内訳表示の改善: total `/100`・各 Pillar の max（/30 /25 /20 /25）・スコアリングモード（rich: time+people / README-only）を Track A Markdown に表示
    - [ ] discussion 観測: GitHub Discussions は REST に一覧エンドポイントが無く GraphQL 専用（dependents 同様）。GraphQL 経路の導入が必要なため保留
- [x] LLMモックを使った `fill_track_entries` の統合テストを追加する
- [x] `roadmap.md` の Phase 1 現況を、Step 9 / R2 / R3 / R5 / M3 実装済みの状態に同期する
- [ ] Web化・課金は現時点では実装しない。必要になったら Phase 2 として再評価する

---

## 完了 (Done)

完了記録は [`docs/archive/task-history.md`](docs/archive/task-history.md) へ移設した（判断の経緯は `DECISION_LOG.md`）。
