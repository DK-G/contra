# DECISION LOG

contra の重要な設計判断を記録する。新しいエントリを先頭に追記する。

---

## 2026-06-15 — ローカル化 段階(b): 数値ゲートを LLM 採点から分離し post-gate 純関数化

**決定**: `select_track_b` の決定論ゲート群を LLM 採点・judge から切り離し、純関数 `apply_post_gates` として切り出した（多層防御のコード床）。

**実装**:
- 共有純関数を新設（いずれも LLM 不使用）:
  - `_serendipity_scored`: anomaly 棄却（`purpose_sim < 0.20`）＋ near-domain mechanism_dist cap（0.5）＋ serendipity = purpose_sim × mechanism_dist。
  - `_hollow_filter`: hollow 棄却（`structural_depth < struct_depth_gate`）。判定欠落は fail-open。因果ゆるめ（`has_causal_pm=False`）は棄却せず caveat 表示。
  - `_quality_gate_and_build`: percentile gate（top30% or floor）→ output_floor → fallback/M3 → MMR 多様化 → OutputEntry 構築。
- `apply_post_gates(scores, id_to_work, ...)`: 上記を束ねる委譲用 post-gate。エージェントが各候補に `{purpose_sim, mechanism_dist, structural_depth, has_causal_pm, connection_label, serendipity_rationale}` を返す前提で、**LLM を一切呼ばず**に anomaly/near-cap/serendipity/hollow/percentile/output-floor/fallback/M3 を再適用する。
- `select_track_b`（既存 LLM 経路）も同じ純関数を呼ぶよう refactor（採点・judge の LLM 呼び出しは従来位置に保持）。**1つのゲート実装を両経路が共有**し、実装の乖離を防ぐ。

**根拠**: 委譲設計の核心＝「賢いが揺らぐエージェント採点の下に、決定論の硬い床を敷く」。ゲートを純関数化することで、エージェントがどう採点しても `purpose_sim < 0.20` の anomaly や hollow をコードが機械的に棄却できる。スコア設計値（0.20/0.50/0.35/0.10/0.5）は不変、ゲートの所在をコード側へ集約しただけ（`spec.md` 禁則順守）。

**検証**: refactor 後も既存 185 件中の Track B 関連テスト（M3 飽和 / score voting / purpose_level 等）が全 green（挙動不変）。`tests/test_post_gates.py` に6ケース追加（anomaly/hollow/near-cap/fallback vs 飽和/因果ゆるめ表示/強候補通過）。

**未着手 / 次**: 段階(c) エージェント採点を受け取る JSON スキーマ定義＋ MCP 委譲経路（収集→生候補返却→エージェント採点→`apply_post_gates`）、段階(d) byrepo/Track A の委譲。

---

## 2026-06-15 — MCPクライアント委譲（サブスク/キー無し運用）を採用、段階(a)に着手

**決定**: `docs/research/mcp_subscription_delegation.md` の「案②: MCPクライアント委譲」を**採用**し、段階導入で着手する。第一歩として段階(a)「bybridge raw_only ＋ structured 整形でキー無し一周」を実装した。

**背景**: LLM 判定・生成を contra 自身の API キー（従量課金）から外し、呼び出し側エージェント（Max サブスクの Claude Code = Opus 4.8 等）自身の推論として実行する。従量$が消え、コスト理由で小型モデルに落としていた制約も外れる。安全弁は**多層防御**（質的判断＝エージェント／絶対外せない数値床＝コードの決定論ゲート）。

**実装（段階 a）**:
- 新モジュール `src/pipeline/delegate.py`（純関数・ネットワーク/LLM 非依存）:
  - `select_bridge_candidates_raw`: 決定論的選別。near_domain（L0/L1 Jaccard）でマイオピアを pre-filter し、共有 citation-bridge 数で順位付け。LLM 不使用。
  - `build_bridge_entries`: distance_score を L0/L1 Jaccard から決定論算出。structure/serendipity は LLM 判定待ちのため 0.0（委譲先のエージェントが補充）。
  - `assemble_keyless_bridge_document`: 決定論選別 → `fill_track_entries(mode="structured")`（LLM を一切呼ばない）→ OutputDocument。**API キー無しで収集→選別→提示の一周が完結**。
- MCP `bybridge` ツールに `structured`（bool, 既定 False）を追加。`raw_only=true, structured=true` でキー無しの 4部構成 Markdown を返す（既存の flat list / LLM 経路は非破壊）。

**根拠**: `--gen-mode structured` と bybridge `raw_only` が既存の足場。structured 整形は決定論で `responses_create` を一切経由しないことをコードで確認。距離は既存 `near_domain_signal` と同じ L0/L1 Jaccard を再利用し、新たなスコア設計値は導入しない（`spec.md` 禁則: スコア設計値 0.20/0.50/0.35 等は不変、ゲートの所在のみコード側に集約していく方針）。

**用途スコープ**: 当面ユーザーは作者自身（個人/研究）。製品バックエンドとして不特定多数に叩かせる形にはしない（Claude Code サブスク想定利用の範囲）。

**検証**: `tests/test_delegate.py` に4ケース（順位付け / near-domain 棄却 / 決定論スコア / キー無しでの4部充足）。全 179 件 green。

**未着手 / 次**: 段階(b) `classify.py` の数値ゲート（anomaly / serendipity / struct_depth / near-domain cap / output_floor / M3）を LLM 採点から独立した純関数として切り出し post-gate 化、段階(c) エージェント採点を受け取る JSON スキーマ定義、段階(d) byrepo/Track A の委譲。

---

## 2026-06-15 — A-RS2 続編: Pillar 1 に「他人」系シグナル（外部コントリビュータ / 非 owner 起票者）を追加

**決定**: 先手（時間系）に続き、生成で水増しできないもう一方のシグナル class「他人」を Pillar 1 に導入した。**dependents（下流利用）は GitHub に公式 REST API がない（HTML の dependents graph のみ）ため対象外**とし、スクレイピングは見送る。

**実装内容**:
- `_third_party_score`（最大6点）を新設＝外部コントリビュータ数（owner を除く、`/contributors`、最大3）＋非 owner issue 起票者数（issues サンプルの重複排除した起票者、最大3）。後者は **A-RS2 先手で既に取得済みの issues ペイロードを再利用**し追加 REST 呼び出しゼロ。前者のみ repo あたり1 REST 増。
- Pillar 1（最大30据え置き）の rich モード配点を再配分: README 系を **0.6 倍 → 0.4 倍**へ更にスケール（completeness 20→8、code 10→4）し、時間系（verified maturity 最大12）＋他人系（third_party 最大6）で構成。8+4+12+6=30。非 rich モードは従来どおり（無認証回帰なし）。
- owner 判定のため search item の `owner.login` を `GitRepository.owner_login` に保持。`_fetch_issue_signal` は `owner_login` を受けて非 owner 起票者を数える（5-tuple 化）。
- 取得失敗は graceful degrade。`source_meta` と Track A Markdown（`Third-Party Signal: N (ext. contributors: …, non-owner reporters: …)`）に露出。

**根拠**: 「他人」シグナル（外部コントリビュータ・非 owner 起票者）は実際の第三者の関与であり、スキャフォールドでは生成不能。README 配点を 0.4 倍まで下げたのは、時間系・他人系の2つの硬いシグナル class が揃ったため README 依存を更に減らす段階移行の継続。

**トレードオフ / 注意**: 外部コントリビュータ取得で repo あたり REST が更に1増（合計 約3増/repo、トークン前提は不変）。dependents は API 非提供のため将来 GraphQL/別経路を要検討。A-RS2 はこれで時間系・他人系の双方を導入完了。Pillar 配点全体の再較正（人間レビュー）は roadmap #10 の品質評価とあわせて実施予定。

**検証**: `tests/test_git_collect.py` に3ケース追加（third_party 段階・rich モードでの Pillar 1 寄与・収集経路での owner 除外カウント）。全 110 件 green。

---

## 2026-06-15 — A-RS2 着手: Pillar 1 配点を README → 「時間」系シグナルへ段階移行

**決定**: 起票済み懸念2（README 成熟度 30点が vibe coding 時代に最も水増し容易なシグナルへ乗っている）への対応として、配点の段階移行の**先手（CI 実行履歴＋リリース刻み）**を実装した。「他人」系（外部コントリビュータ / dependents）は次段に残す。

**実装内容**:
- `_verified_maturity_score`（最大12点）を新設＝`_release_cadence_score`（リリース数による versioning discipline、最大6点）＋`_ci_health_score`（直近 Actions runs の実行＋成功率、最大6点）。いずれも「設定ファイルの存在」でなく「実際にリリースが刻まれ／CI が回って通っている」事実を採点する（スキャフォールドで水増し不能）。
- Pillar 1（最大30点据え置き）を、リッチシグナル取得時のみ **README 系を 0.6 倍にスケール**（completeness 20→12、code density 10→6）し、空いた12点を verified maturity に移譲。**リッチシグナル非取得時は従来の README 重点スコアのまま**（無認証実行に回帰なし）。
- 取得は `_fetch_release_signal`（`/releases`）と `_fetch_ci_signal`（`/actions/runs`）。repo ごと約2 REST 呼び出し増。
- **GITHUB_TOKEN とセット**: `GitCollectConfig.include_rich_signals=None`（既定）はトークン在席時のみ自動有効化（無認証 60 req/h の壁を踏まないため）。`True/False` で明示上書き、CLI `--git-rich-signals/--no-git-rich-signals` で制御。取得失敗は graceful degrade（0点・has_rich_signals は立てる）。
- `source_meta` と Track A Markdown（`Verified Maturity: N (releases: …, CI: ok/sampled passing)`）に露出。

**根拠**: 生成で水増しできないシグナルは本質的に「時間」と「他人」のみ（DECISION_LOG 2026-06-12）。README ヒューリスティックは「AI ツールを使ったか」程度まで情報量が劣化したため、満点が乗る配点を時間系へ移す。完全撤廃せず 0.6 倍に留めるのは段階移行＋無認証フォールバック維持のため。

**トレードオフ / 注意**: トークン在席時は README のみで満点に届いた repo が相対的に降格する（=狙い通りの是正）。リッチシグナル取得は API コスト増のためトークン前提。「他人」系シグナル（contributors / dependents）と Pillar 1 の更なる配点見直しは A-RS2 続編として残す。

**検証**: `tests/test_git_collect.py` に8ケース追加（cadence/ci 段階、verified=cadence+ci、リッチ時の README 降格、リリース/CI クレジット、rich 解決のトークン依存/明示上書き、収集経路での露出）。全 107 件 green。

**未着手 / 次**: A-RS2 続編（「他人」系シグナル）。

---

## 2026-06-15 — A-RS1 完了: Pillar 2 (LMA) に候補プール内相対正規化を追加

**決定**: 懸念1の改善方針候補2「候補プール内相対正規化」を実装し、A-RS1（候補1＋候補2）を完了とする。

**実装内容**（`src/pipeline/git_collect.py`）:
- `_apply_pool_relative_lma(repos)` を追加。同一クエリで収集した候補プールをドメインサンプルとみなし、各 repo の **push 鮮度のプール内相対順位**で LMA を補正する。成熟ドメインで全 repo が stale な場合でも、絶対 tier で全員が最下位（1点）に潰れず、プール内で最も手入れされた repo が浮上する。
- 補正は `relative > 現 lma` のときのみ適用（`max` 意味論）。新鮮な repo の絶対スコアは決して下げない。順位天井は 12点で**完成判定の床（最大15点）より低く**置き、順位だけで「維持＋採用された完成ライブラリ」を上回らないようにした。順位は同点（同日 push）に等しいクレジットを与える。
- プールサイズが 3 未満のときは順位が無情報なため no-op。`GitCollectConfig.pool_relative_lma`（既定 True）で切替可能。`_apply_reliability` の後段で適用し、補正時は4 Pillars から `reliability_score` を再計算。追加 API コストはゼロ。

**根拠**: 候補1（完成判定の床）は「採用＋高クローズ率」の二条件を満たす repo のみを救済するが、シグナルの薄い小規模 repo や issue 履歴のない成熟ライブラリは依然として救えない。プール内相対正規化はメタデータ追加取得なしに「ドメイン全体が stale」を自動補正する補完策。

**検証**: `tests/test_git_collect.py` に4ケース追加（stale ドメインで最新が浮上 / 新鮮 repo は不変 / 小プール no-op / 同点は等クレジット）。全 99 件 green。

**未着手 / 次**: A-RS2（Pillar 1 配点を時間・他人系シグナルへ移行、GITHUB_TOKEN 事実上必須化とセット）。

---

## 2026-06-15 — A-RS1 着手: Pillar 2 (LMA) に完成判定の床を実装

**決定**: 2026-06-12 に起票した懸念1（Pillar 2 が完成した安定ライブラリを最も強く罰する）への改善方針候補1「完成判定の床」を実装した。候補2「候補プール内相対正規化」は引き続き未着手。

**実装内容**（`src/pipeline/git_collect.py`）:
- `_lma_score` を「鮮度（freshness）」算出と「完成判定の床」適用の2段構成に分離。push 経過日数に基づく従来の段階配点（14日=25点 … 1年超=1点）を `freshness` として保持。
- `_is_completed_stable(repo)` を追加。**採用シグナル**（`stars >= 50` または `forks >= 10`）と、**過去の issue 活動＋高クローズ率**（`issue_closed_count > 0` かつ `closed >= open`）の**両方**を満たす stale repo のみを「完成した安定ライブラリ」と判定する。Pillar 3 の「ゼロIssueの罠」と同型に、「完成」と「誰も使っていない」を区別する。
- 該当時は LMA を `freshness` でなく床値で止める: 基本 12点、強採用（`stars >= 200`）は 15点。`max(freshness, floor)` のため新鮮な repo のスコアは下げない。
- issue サンプルの open/closed 件数を `GitRepository.issue_open_count` / `issue_closed_count` に構造化保持（従来は summary 文字列のみ）。`source_meta` にも露出。

**根拠**: 「2年間 push がない＝完成していて修正不要」な小さく完璧なユーティリティが top-3 から脱落する歪みを、撤廃（鮮度ゼロ化）せずに緩和する。互換性腐敗の実害は残るため床は中位（12〜15点）に留め、満点（25点）には戻さない。採用＋クローズ率の二条件で「放置」を床から除外する。

**検証**: `tests/test_git_collect.py` に床の発火/非発火5ケースを追加（強採用→15、中採用→12、未採用/issue履歴なし→1、未解決 issue 滞留→1、新鮮 repo→25）。全 95 件 green。

**未着手 / 次**: 候補2（候補プール内相対正規化）と A-RS2（Pillar 1 配点移行）。

---

## 2026-06-12 — byrepo Reliability Score の構造的懸念2件（起票・実装未着手）

**決定**: Reliability Score（4 Pillars）に以下の構造的懸念があることを認定し、改善方針の候補を記録する。実装は未着手。着手順は懸念1 → 懸念2 を推奨（出力 top-3 への歪みが大きい順）。

### 懸念1: Pillar 2 (LMA, 25点) が「完成した安定ライブラリ」を最も強く罰する

- 現行は `pushed_at` 経過日数のみで採点（14日以内=25点 … 1年超=1点）。「2年間 push がないのは完成していて修正の必要がないから」という小さく完璧なユーティリティ — 車輪の再発明防止の本丸 — が top-3 からほぼ確実に脱落する。
- 更新頻度=信頼の代理指標は活発なエコシステム（MLフレームワーク等）では機能するが、成熟ドメインでは逆相関する。
- ただし鮮度ゼロ化（撤廃）は不可: push が止まったコードにもランタイム更新・依存 CVE・ビルド破壊などの**互換性腐敗**という実害がある。

**改善方針候補**:
1. **完成判定の床**: 「push が古い + open issue 少」だけでは「誰も使っていない」と区別できないため、過去の issue 活動と高クローズ率 + 採用シグナル (stars/forks) を併置する（Pillar 3 の「ゼロIssueの罠」と同型のロジック）。該当時は LMA を 1点でなく 12〜15点で床止め。
2. **候補プール内相対正規化**: 同一クエリで収集した候補プール自体をドメインサンプルとみなし、プール内の相対順位で LMA を付与する。成熟ドメイン同士なら自動的に緩く補正され、追加 API コストはゼロ。

### 懸念2: Pillar 1 (README 成熟度, 30点) のシグナル劣化（2026年時点）

- vibe coding 由来のリポジトリは What/How/Why/When 完備の README を最初から持つため、見出しヒューリスティックの情報量は「AI ツールを使ったか」程度まで劣化している。最大配点 30点が最も水増し容易なシグナルに乗っている。
- 注意: `.github/workflows` やテストディレクトリの「ファイル実在」もスキャフォールドが生成するため、数年で同じ劣化を辿る。生成で水増しできないシグナルは本質的に2種類のみ:
  - **時間**: コミット/リリースタグの時間的分布、CI の実行履歴と直近の成否（Actions API — 設定ファイルの存在ではなく「回って通っている」事実）
  - **他人**: 外部コントリビュータ数、owner 以外の issue 起票者、dependents（下流利用）

**改善方針候補**: 配点を README → 「時間と他人」系へ段階移行する（先手は CI 実行履歴とリリース刻み）。

**制約**: リッチシグナルは repo ごとの REST 呼び出しが増え、未認証の core 60 req/h の壁に当たる。実装は `GITHUB_TOKEN` の事実上必須化とセットで判断する。

---

## 2026-06-09 — OSS探索 (byrepo) 結果に基づく機能導入：MCP・GloVe・agentmemory の採用決定

**決定**: `byrepo` 探索で発見した 3 つの OSS リポジトリから、以下の技術・設計思想を Contra に順次導入・統合することを決定。
1. **MCP サーバー化 (`microsoft/mcp-for-beginners` 参照)**: Contra パイプライン全体を MCP (Model Context Protocol) サーバー化し、外部の IDE エージェント等から直接「視座拡張ツール」として呼び出せる設計へと拡張する。
2. **意味・概念トポロジー距離の統合 (`stanfordnlp/GloVe` 参照)**: ドメイン間の意味的・認定的距離を定量化するため、GloVe 等の分散表現のアライメント思想を採用する（独自ビルドはせず既存ライブラリ経由でベクトル空間アライメントを実装）。
3. **エージェント持続メモリの導入 (`rohitg00/agentmemory` 参照)**: 1回限りの実行で終わらず、過去の探索・選別履歴やユーザーフィードバックを記憶し、周回探索を強化する「持続メモリ」を探索パイプラインへ統合する。

**根拠**:
- 各 OSS のライセンスを調査し、MIT (`mcp-for-beginners`) および Apache-2.0 (`GloVe`, `agentmemory`) ともに商用・私的利用が可能で、Contra にライブラリインポートまたは設計借用として組み込む上で法的に完全に安全であることを確認。
- 実装・検証時にクエリビルドの `NOT` 構文の最適化（バグ修正）および exclusion キーワードの調整を行い、byrepo にて信頼性スコア (Pillars) の精緻な出力とともにこれらのリポジトリを自動発見した。

---


## 2026-06-02 — LLM モデル/プロバイダ方針：マルチプロバイダ化＋品質ランは Claude Haiku 4.5

**決定**: `openai_client` をマルチプロバイダ化し（OpenAI Responses + Anthropic Messages、`--llm-model` でゼロコード切替）、運用は **既定 gpt-4o-mini（激安・探索用）／「本気の1本」は claude-haiku-4-5（最良コスパ）／プレミアムは claude-sonnet-4-6** とする。コード既定は gpt-4o-mini 据え置き（モデルは実行時フラグで選択）。

**根拠（A/B 実測, social 1ラン, ¥150/$, 価格要確認）**:

| モデル | ¥/run | 質 |
|---|---|---|
| gpt-4o-mini | ¥1.8 | 弱い（浅い写像・数値捏造気味） |
| **claude-haiku-4-5** | **¥24** | 優秀 |
| o4-mini | ¥45 | 優秀 |
| claude-sonnet-4-6 | ¥69 | 優秀（僅差で最上） |

- 強3モデル（Haiku/o4-mini/Sonnet）は全て目標品質（深い構造写像・操作化された検証可能仮説・破断点 caution）をクリア。spine 品質の天井は gpt-4o-mini の構造アブダクション限界であり、推論/上位モデルで解消するという R1 調査結論を実証。
- コスパは Haiku 4.5 が最良。1ラン別論文ゆえ強3モデルの質の優劣は統計分離不能（コスト順は信頼可）。

**確認した非結果 / 訂正**:
- prompt caching は両 Claude run で cached_input=0（system ブロックが Anthropic 最小キャッシュ閾値 ~1024tok 未満の可能性）。「caching でコスト相殺」仮説は不成立 → Claude コストは素の値。
- 副次バグ修正: main.py の `--struct-depth-gate default=0.30` が校正値 0.50 を上書きしていた（commit b693223 で定数連動に修正）。

**ローカルLLM却下**: RTX 3060 Ti / VRAM 8GB では、速く動く 7–8B は gpt-4o-mini 以下、効きうる 32B 推論distillは VRAM に乗らず CPU 退避で実用速度が出ない。質の天井対策にはならず却下。

**可逆性**: プロバイダ切替は実行時フラグ、選別ロジック不変。

---

## 2026-06-01 — Track B 生成3部の hollow 対策：転用読みの定石に基づく多段プロンプト化

**決定**: Track B の4部生成のうち②関連性・③仮説・④注意点を、「遠い論文を自テーマへ転用する読み」の確立手順（構造写像/LBD/bisociation/概念ブレンディング/知識ブローカリング/Reading-for-Relevance/情報採餌に共通の4ムーブ）に沿って**多段構造化**し、各部に**FORBIDリスト**を明記する。summary は実Abstract援用で充足済みのため変更しない。

**根拠**: bynote 調査（NotebookLM Deep Research 68ソース、ノート `85d1cd32`、一次資料 `docs/research/reading_for_transfer.md`）。A-1 品質評価で観測した hollow 症状（②カテゴリ言い換え/③"可能性がある"bloat/④定型caution）が、先行研究が明示的に禁止する失敗型と一致した。

**処方**:
1. 生成プロンプト: object-mapping → Shared Relational Structure 明示 → 変数付き candidate-inference 仮説 → 破断点 caution。各部に禁止例を明記。
2. judge ルーブリック（Structural Depth / Applicability / Constraint Adherence 各0-10）でカテゴリ一致を hollow 棄却（次段で校正）。
3. summary は不変。

**トレードオフ / 却下**: 質ゲートを厳しくすると飽和（0件）が増えるが、ユーザー方針「論文選定は重視しない・同一論文の再ピック禁止が効けば周回でカバー」と整合するため許容。プロンプトを勘で調整する案は却下し、定石調査を先行させた。

**可逆性**: プロンプト変更のみ。選別ロジック・データ構造は不変。

**関連**: A-1 評価でのロバストネス修正（commit `28bbecc`）・Abstract truncation 修正（commit `0264d04`）。
