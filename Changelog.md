# Change Log（開発概要 + diff.mdスナップショット）

## 運用ルール
- `diff.md` を更新（上書き）する **直前**に、必ずこのファイルの先頭へ1エントリ追記します。
- ここは履歴（追記のみ）です。過去のエントリを書き換えることはありません。
- 目的は「後から開発の経緯を復元できること」です。詳細なdiffはGitの履歴を参照します。

---

## 2026-09-01（CL-0096） F-17 対処: byrepo `関係度` ラベルの正体は Reliability の帯だった——theme 関連度の帯に差し替え、係数を同じ行に描画

### 概要
* **同日2件目。** seihai 8/27 の「唯一有用な frouros が『中』、無関係な Kats / security-investigator が『高』」の真因: `build_track_a_entries` が `relationship_level` を `_reliability_level(reliability_score)`＝**品質の帯**から作っていた。theme 関連度はラベルにどこにも入っておらず、F-03（順位に関連度を入れた 8/21）の姉妹経路の数え上げ漏れ。8/29 の精緻化「逆転ではなく無関係」がそのまま正しい。3件の順位スコア（62.0 / 51.0 / 47.0）から Reliability を逆算すると 62 / ≈90 / ≈83 で、旧ラベル 中/高/高 が計算で再現する。
* **実装（加算的・可逆・順位不変）**: (1) `track_a.py` に `anchor_relevance()` / `relevance_level()` 新設、`関係度` = theme 関連度の帯（高 ≥0.67／中 ≥0.35／低 <0.35。0.33 が低に落ちること・下限が既存の低関連度警告 0.35 と一致することで較正）。(2) `output_spec.py` でラベルと係数を同じ行に（`関係度: 高（theme関連度 1.0）`）。(3) Reliability の帯は `Reliability Score` 行に別名で残る。
* **実測 before/after**（新規 `scripts/f17_label_probe.py`・offline 再演）: frouros 中→**高(1.0)**、Kats 高→**低(0.33)**、security-investigator 高→**低(0.33)**。before は seihai の表を文言まで再現。順位・順位スコアは不変。
* 新規回帰3件（3件すべてが `78fb9f0` で落ちることを確認）。旧契約を固定していた既存テスト1件を新契約に更新。**410 → 413 tests: 413 pass**。GitHub トークン無しのため実 API E2E は未実施。
* **残**: 係数自体が語の一致（F-13/F-14）なので、8/31 型の run では全件「高」になる。ラベルはその欠陥を隠さず見せる。

---

## 2026-09-01（CL-0095） F-19 対処: 接地失敗の「不一致」と「照合不能」を分け、材料欠落との因果を同じ文に書く

### 概要
* **直す対象は照合ロジックではなく計器だった。** seihai は `byserendipity raw_only` の候補5件を採点し、`source_quote` を abstract から**逐語で**抜いて `delegate_finalize` に渡したのに 5/5 が接地失敗した。原因は呼び手が `title`/`abstract` を echo していなかったこと（seihai の自己診断は正しい）。問題は**その失敗の伝え方**で、`source_quote が候補の title/abstract に存在しない（逐語一致が必要）` は呼び手に**自分の引用が捏造だったのか**を先に疑わせた。材料欠落の警告は別ブロックに「該当欄は空のまま描画されます」＝体裁の問題として出ており、両者の因果はどこにも書かれていなかった。
* **機序**: `verify_grounding` は `source_quote` を `material["title"] + material["abstract"]` に対してのみ照合する。両欄が空なら干し草の山そのものが無いので、**正しい針でも `not in ""` が真になる**。空の干し草に対する不一致は不一致ではない。
* **実装（加算的・可逆・シグネチャ非変更）**: (1) `照合不能` を `不一致` から分離（`_UNVERIFIABLE_MARK`・テーマ側にも同型分岐）。(2) 部分 echo（title あり・abstract なし）は不一致のまま `※ ただし abstract が送られていません——…` を併記。**全欄揃った不一致は従来どおり無条件**（捏造を甘くしない・ガードテスト有）。(3) `echo_completeness_warnings` に `★ この欠落は接地検証も不能にします` を追加（欠落が `title`/`abstract` を含むときだけ）。(4) `src/mcp_server.py` の接地失敗ブロック見出しに因果 ※ 行（`has_unverifiable_failure()` で判定）。(5) 書式バグ1件: `履歴記録 N 件` が `extra` の後ろに連結されて**最後の箇条書きの尻に貼り付いていた**のを、カウンタ＝見出し行／箇条書き＝その下、に直した。
* **実測 before/after**（新規 `scripts/f19_grounding_message_probe.py`＝seihai 当日の投入を実 API 無しで再演。同一候補・同一引用・同一スコア）: (1) `id`＋採点欄のみ → before は seihai が受け取った文言を**そのまま再現**、after は `照合不能: …（引用の誤りではなく材料欄の欠落が原因です）`＋見出し ※＋警告 ★。(2) 全欄 echo → 両方とも接地成立（**非退行**）。(3) 新規に検査した部分 echo → 不一致＋原因候補の併記。
* 新規回帰テスト6件。うち**4件が `875dd1d` に対して落ちることを確認済み**（残る2件は非退行ガード）。**404 → 410 tests: 410 pass**。
* **seihai 側への申し送り**: S-90（材料はプログラムで抜き出してそのまま echo）は維持されたい。変わるのは踏んだときの復帰速度。

---

## 2026-08-28（CL-0094） F-13 部分対処: bybridge シード段の三層化（field 限定＋semantic シード＋主題整合計器）

### 概要
* **bynote 調査に基づく同日2件目。** F-13（取得段の語彙衝突）の機序を2段特定: (1) シード検索は keywords 数語の表層一致のみでテーマ本文を見ていない (2) `StructuredQuery.field_ids` は実装済みなのに未配線で、0件時の generic-search フォールバックは全分野横断＝ドリフトの扉。
* **実装（加算的・可逆）**: (B) シード段全クエリ＋フォールバックに `primary_topic.field.id` 限定（`seed_field_scope:false` で旧挙動・fail-open）。(C) テーマ本文を `search.semantic` に投げる semantic シードレッグ新設（`collect_seeds_semantic`＋`keep_home_field`＋`merge_seed_pools` 公平配分・`seed_semantic:false` で無効・失敗時は語彙のみ）。(A) `seed_domain_alignment`/`render_seed_alignment` 計器＝home分野一致率＋上位分野名指しを診断に常時出力・50%未満で警告・分野未解決は「判定不能」。
* **実測 A/B/C**（r05/F9 テーマ・実 API）: home一致 50%（旧）→100%（新既定）。semantic レッグ14件は全件 referenced_works 保持で bridge シード成立、内容は明確に主題寄り（Sequence Alignment による約定列比較等）。MCP 実機で最終シード20件中 semantic 由来5件・既存ゲート（F-12/C(iii)/F-01）と共存。
* **残**: 同分野内ドリフト（8/24型）は field 一致率で捕まらない（semantic レッグが実質処方・収穫改善は seihai 次回 run が判定）／byrepo の同型は未対処。
* fallback の契約変更1点: `StructuredQuery.fallback()` は field_ids を**保持**（他フィルタは従来どおり落とす）。既存テスト1件を新契約に更新。
* 新規 `tests/test_seed_field_scope.py` 13ケース＋既存 autouse fixture に semantic レッグの stub 追加。全 **404 tests: 404 pass**。

---

## 2026-08-28（CL-0093） F-18 の真因を特定して対処: 最遠 facet は「引けなかった」のではなく「検索されていなかった」

### 概要
* **2日連続で収穫0だった Very Far facet の正体は、contra 自身が3枚目を1度も検索していなかったこと。** `_collect_track_b_semantic` は facet を順に引いて候補を連結し、`len(works) >= max_count` で break していた。semantic エンドポイントは1リクエスト最大50件・上限は60件なので、**facet 1+2 で枠が埋まり facet 3 のリクエストは発行されない**。A2 距離プロトコルは facet を Near → Far → **Very Far** の順に並べるため、**構造的に必ず最遠の1枚が餓死する**——プロトコルが買おうとしていたものだけが毎回捨てられていた。
* **seihai の観測がそのまま署名だった**: 「facet は3枚なのにリクエストは2件」は取りこぼしではなく、**3枚目を呼んでいない事実の直接の表示**。seihai の2仮説（(a) OpenAlex の類似度足切り／(b) ホームドメイン除外の巻き込み）は**どちらも外れ**で、故障は呼ばれる側でなく呼ぶ側にあった。
* **実装**（加算的・可逆）: (1) 全 facet を必ず検索し、上限を facet 間でラウンドロビン配分（`_interleave_facet_buckets`）——薄い facet は未使用枠を譲るので**候補総数は減らない**。`CollectConfig(facet_fair_share=False)` で旧挙動。(2) **facet 別内訳を診断ブロックに常時出力**（`stats_out` → `_facet_breakdown_line`）＝各 facet の `返却 / ホーム除外・重複後 / 提出` と**収穫0の facet の名指し**。(3) `run_stats_caveat` の「結果への影響なし」を撤回し、HTTP 応答しか見ていない旨と facet 別内訳への誘導に差し替え。
* **実測 before/after**（8/28 の r05/F9 と同一3 facet・実 API・同一セッション A/B）: facet 別提出が **42/18/0 → 20/20/20**、OpenAlex リクエスト **2 → 3**、候補総数は 60 のまま、**新規候補 22/60**。seihai が単独呼び出しでしか引けなかった等価変異体の文献（`Are mutants a valid substitute for real faults` / `The Impact of Equivalent Mutants` / `Automatically detecting equivalent mutants and infeasible paths`）が**3枚同居のまま上位に返る**。before 側は seihai の実測 43/17/0・44/16/0 をほぼそのまま再現した。
* MCP 本番経路（`byserendipity raw_only`）でも実機確認済み（3/3 facet・20/20/20・内訳行が出力に載る）。
* **seihai 側への申し送り**: 当面の運用処方「Very Far は単独呼び出しで引く」は**不要になった**（禁止ではない）。今後 0件の facet が出たら、それは打ち切りではなく検索側の性質である。
* 新規 `tests/test_facet_fair_share.py` 8ケース。全 **390 tests: 390 pass**。
* **同型の残件（起票のみ）**: `_collect_track_b_lexical`（キー経路のフォールバック）に同じ形の break がある。per_query 割当があるため通常は届くが、1ページが割当を超えると同じ餓死が起きうる。本番経路ではないので未対処。

---

## 2026-08-25（CL-0092） F-01 の真の機序を特定して対処: bridge 生存確認ゲート（phantom bridge の除外）

### 概要
* **7週間「巨大ハブ吸着」と呼んできた失敗の正体は、存在しないレコードだった。** 最頻 bridge `W4285719527` は OpenAlex に**作品として存在しない**（`GET /works/...` が 404・`ids.openalex` で count 0）のに、**490万件の参考文献リストに id が残っている**。`referenced_works` は生の参考文献リストなので、統合・削除されたレコードの id が引用側に残り続ける＝**書誌データの傷跡**。2-hop スキャンはプールを1本の `cites:` フィルタに OR で流すため、この phantom 1本が結果を丸ごと飲み込み、出力が「ホームドメインを除いた OpenAlex 最多被引用リスト」に退化していた。
* **判別軸は大きさではなく解決可能性**。同一プール内の死んだ id 5本の被引用数は 4,906,577 / 4,194 / 2,749 / 554 / 59 とばらばらで、生きた最大 bridge は Fama-French(27,948)・GARCH(22,513)＝正統な基礎文献。**中心性ペナルティは小さい phantom を見逃し本物を罰する**——2026-08-18 に計器がこの処方を否定した判断がここでも裏付けられた。
* **実装**（加算的・可逆）: `filter_live_bridges` / `resolve_ids_batched`（`src/pipeline/bridge_diagnostics.py`）＝プール id を 50件ずつ1バッチで解決し、解決しない id を除外。`bridge_liveness:false` で旧挙動。通信失敗・全件 dead 応答はいずれも **fail-open**（プールを空にすると F-12 型の沈黙した収穫ゼロになる）。`collect_citation_candidates` に `bridges=` 引数を追加——これが無いと本体が内部でプールを作り直し、除外した phantom が `cites:` に戻る。
* **実測 before/after**（固定テーマ・同一セッションで A/B）: 最頻 bridge の全候補占有 **98% → 35%**、通行 bridge **2本 → 19本**、共有1本のみの候補 **60/60 → 40/60**、最頻 bridge の正体が **存在しない id → Fama & MacBeth "Risk, Return, and Equilibrium"(15,196)**。上位候補は汎用方法論引用雲（thematic analysis 190,298 / TAM 66,478 / G\*Power）から実証ファイナンスへ。
* **対照実験**: 健全な既存フィクスチャでは死んだ id 2本がいずれも通行量ゼロで、**出力は before/after 完全一致**＝ phantom が居なければ無害。
* **残件（正直に記録）**: 「遠さ」は未改善（after の上位はホームドメイン近傍の実証ファイナンス＝ホームドメイン除外が効いていない疑い）。上位10件窓の集中は 90%→70% で残る。materials 経路は持続的 429 のため実機未確認。
* 新規 `tests/test_bridge_liveness.py` 9ケース。全 **382 tests: 382 pass**。

---

## 2026-08-22（CL-0091） 案X採用: 委譲経路を本番経路に昇格＋束2実装（C(iii)言語ゲート・A2距離プロトコル・bybridge materials）

### 概要
* ユーザー裁定「束１案X採用・束２実装まで進めて」。委譲経路（呼び手エージェント=LLM 役・contra=決定論検証）を **by\* の本番経路に昇格**。
* **bybridge `materials:true`**（新設）: 構造的関連度順・上位窓多様化済みの交差候補を採点可能な materials JSON（bridge_signals 付き）で返す＝byserendipity raw_only の対称形。これで Track B 両ツールが完全な委譲フローを持つ。
* **C(iii) シード言語ゲート**: Work に language を追加（parser で取得）。bybridge シードは既定 'en' 以外を除外（言語コード欠落は fail-open・`seed_language:null` で無効化）。F-12 run 1/3 の「日本語テーマ→日本語機関リポジトリ20/20」の再発防止。除外数は診断に明示。
* **A2 距離プロトコル**: byserendipity raw_only の facets 指示に Near/Far/Very Far の3距離段階を明文化（F-06 のホームドメイン固着への処方）。
* materials の bridge_signals.shared_bridge_count は annotation 副作用でなく直接計算（モックテストが暴いた脆さの修正）。
* 全 **373 tests: 373 pass**。seihai 側 SKILL の委譲フロー化は別コミット（ユーザー承認済み）。

---

## 2026-08-22（CL-0090） 承認済み総合対応の実装: C(順位多様性/構造的関連度)→B(同点解消)→A1(接地契約)

### 概要
* 3系統 NotebookLM ノートで練った総合対応をユーザー承認に基づき実装。詳細は DECISION_LOG 同日エントリと field_observations の各節。
* C: per-bridge 上位窓枠＋構造的関連度ハイブリッド順位（bridge のシード引用数）。上位窓占有 100%→0%・上位の中身が9週間で初めてテーマの構造的隣人に。
* B: purpose_pct 帯内細粒度の同点解消（アンカーはゲートに温存）。委譲スキーマにアンチ同点指針を明文化。
* A1: quote-then-claim 接地契約を委譲経路に実装（LLM 役=呼び手エージェント・contra=決定論検証）。F-04 の捏造形が描画不能になったことを実機確認。
* 全 370 tests: 370 pass。

---

## 2026-08-22（CL-0089） F-12 同日対処: bybridge シード生存確認ゲート＋byrepo 低関連度警告

### 概要
* 今朝の seihai 観測run 1/3 が起票した **F-12**（referenced_works 空のレコードがシード20枠を占有→bridge 0本）を同日対処。seihai 側の処方（vol_sma 0発火の教訓「採用の前に生存確認」）をそのまま採用。
* シード候補を3倍オーバーフェッチし referenced_works 空を除外・除外数を診断に明示・全滅時は F-12 の形を名指し。
* 併記観測の示唆を実装: byrepo は上位アンカーの関連度が全件 0.35 未満のとき語彙衝突警告を出力先頭に付す。
* 実測: 固定テーマで死にレコード24件除外・bridge 集中 52%→27%・通行 bridge 13→21本。**上位10件窓は 100% に戻った（順位付け層の別問題として正直に記録）**。
* 全 **351 tests: 351 pass**。

### 関連タスク
* Task: contra 失敗対処（F-12・S-26 観測run 1/3 への応答）

---

## 2026-08-22（CL-0088） byrepo プール品質の根治: OR クエリ＋best-match／HF密度化／Kaggle柱ラベル修正

### 概要
* ユーザー指示「発見されたバグの対策をウェブで調べて対処」。前日 F-03 処置で発見・未修正だった4残件を処置。
* **検索クエリの根治（真の律速）**: GitHub 公式仕様（REST search）を確認し、(a) include 先頭1語のみ→**全キーワード OR 連結**（演算子5個・256字の公式上限内で予算管理）、(b) `in:name,description,readme` 修飾、(c) **`sort=stars` の撤去＝既定の best-match（関連度）ソートに復帰**、(d) `pushed:` 相対日付化。実測: 同一テーマで首位が deer-flow(★80k・無関係)→**jakorostami/expectation（テーマの理想解・旧クエリではプール不在）**へ。
* **HF カード切り詰め**: GitHub README と同型の [:2000] 切り詰めを発見→密度正規化を適用（定数は git_collect と共有）。
* **Kaggle 柱ラベル**: `reliability_breakdown`（output_spec）新設でソース別柱表示。8/18 の「サブスコア全ゼロ」は Kaggle anchors に GitHub 柱ラベルを印字していた描画バグと確定・解消。構造化レンダラに Kaggle 分岐追加。
* 構造化レンダラにも順位スコア行（Reliability × 関連度係数）を追加。
* 全 **349 tests: 349 pass**。

### 関連タスク
* Task: contra 失敗対処（F-03 残件の根治）

### Diffスナップショット（要約）

```text
# 1. 変更目的 (必須)
byrepo の「本命がプールに入らない」を検索層で根治。密度正規化と柱ラベルをソース横断で整合させる。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/git_collect.py(クエリ再設計+sort設定), src/pipeline/hf_collect.py(密度fit),
src/core/output_spec.py(reliability_breakdown+Kaggle分岐+順位スコア行), src/mcp_server.py(ソース別柱表示),
tests/test_git_collect.py(クエリ新仕様3件), tests/test_hf_collect.py(+3), tests/test_kaggle_collect.py(+3)

# 3. 検証 (必須)
349 tests 全緑。実 API before/after: 旧クエリ vs OR+best-match をプローブ2回＋collect_track_a_works 1回＋MCP 全経路1回。
```

---

## 2026-08-21（CL-0087） F-03/F-09/F-10/F-11(3) 一括対処（ユーザー立ち会い・「ガンガン回して潰す」指示）

### 概要
* **F-03（byrepo・関連度が順位に効かない）**: `theme_fit_score`（各ソースが計算済みだが GitHub では順位に未接続だった）を正規化した relevance を乗算項に導入——`順位スコア = Reliability × (0.35 + 0.65 × relevance)`（`src/pipeline/track_a.py`）。作業中に2つの下位バグを実測で発見・修正: (a) README 照合が先頭2000字切り詰め＝confseq の本命キーワード（5737字目）が fit 0 に潰れていた、(b) 全文照合に変えると巨大 README（frankensqlite 180KB）が偽 relevance 1.0——実データ較正で**密度正規化**（README ヒットは10,000字あたり出現数の部分点・name/desc/topics は全点）に決着。実 API before/after: **8/21 観測と同型テーマで首位 deer-flow（無関係・★80k）→ relevance 0.03 で7位、POPPER（真に関連・rel43）が quality88 を逆転**。keywords 5件上限を MCP スキーマに明記。
* **F-09（delegate_finalize）**: echo 欠落警告＋落選1件ごとの (id, 床, 実測値, 閾値) を「落選内訳」として出力（`_record_rejections` を anomaly/hollow/percentile/output_floor/not_selected 全段に配線）。実機で全行の出力を確認。
* **F-10（byserendipity）**: `has_causal_pm=False` の候補に `purpose_sim` 上限 partial(0.45) を機械適用（`_apply_causal_cap`）。LLM 経路と delegate post-gate の両方。実機で 0.56→0.36 への降格と tight 候補との分離を確認。
* **F-11(3)**: OpenAlex 取得の RUN_STATS（requests/retried/gave_up）を MCP 層で毎回リセットし、異常時のみ「⚠ 取得診断」行を結果本文へ追記＝「収穫ゼロ」と「取得失敗」を出力上で区別。
* **F-04/F-05/F-06/F-08 は見送り**（LLM キー無しで「実装したら走らせる」を守れないため）。field_observations に着手条件（キー有効性の先行確認）を明記。
* 全 **341 tests: 341 pass**。

### 関連タスク
* Task: contra 失敗対処デーの延長（ユーザー裁定「今ここでガンガン回して潰す」）

### Diffスナップショット（要約）

```text
# 1. 変更目的 (必須)
残存 F-xx のうちキー不要で実装→実測まで完結できる4系統を一括処置。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/track_a.py, src/pipeline/git_collect.py, src/pipeline/classify.py,
src/pipeline/delegate.py, src/mcp_server.py, src/openalex/client.py,
tests/test_anchor_rank.py(新規), tests/test_causal_cap.py(新規),
tests/test_delegate_observability.py(新規), tests/test_openalex_client_retry.py(拡張),
docs/field_observations_seihai.md, Changelog.md, DECISION_LOG.md

# 3. 検証 (必須)
新規/拡張テスト 26ケース＋実 API 実測: byrepo before/after 3回（切り詰め版/naive全文版/密度版）、
delegate_finalize 実機1回（F-09/F-10 同時確認）、README 実測プローブ2回（密度較正の一次データ）。
```

---

## 2026-08-21（CL-0086） F-11(1) OpenAlex リトライ／時計依存テストの修理／S-26 試験再開の反映

### 概要
* 同日の対処デー報告に対するユーザー裁定3件を実施。
* **S-26 解除（ユーザー裁定「１解除で」）**: seihai 日次 SKILL の bybridge 停止注記3箇所を「2026-08-21 試験再開」へ更新（4種に復帰・最初の3回は観測run・3回とも旧様式なら恒久除外）。seihai 台帳 `docs/open-recommendations.md` の S-26 行にも再開を追記（seihai 側コミット `af3c4af`）。※SKILL・台帳の編集はユーザー在席・明示指示によるもので、無人ルーティンの「seihai を触らない」制約の例外。
* **F-11(1) 実装（「(1)を今実装でできたらその後試して」）**: `src/openalex/client.py` の `get` に 429/5xx/タイムアウト系の指数バックオフ・リトライ（既定2回、`max_retries=0` で旧挙動＝可逆）。429 以外の 4xx は即時失敗のまま。新規 `tests/test_openalex_client_retry.py` 6ケース。実経路（bybridge raw）1回完走を確認。(2) polite pool は据え置き（個人情報送出の判断を伴うため）。
* **時計依存テストの修理（「おススメの通り対処して」）**: `tests/test_git_collect.py::test_lma_floor_never_lowers_a_fresh_score` の `pushed_at` ハードコード（2026-06-10）を「現在から5日前」の相対日付に変更。書かれた2週間後から測定能力を失い、以後常に赤かった。`_is_completed_stable` の assert も追加し「floor が新鮮なスコアを引き下げない」を実際に検証する形に戻した。
* **全 314 tests: 314 pass＝スイート全緑**（2026-08-18 から続いた常時赤を解消）。

### 関連タスク
* Task: contra 失敗対処デー 2026-08-21 の後続（ユーザー裁定分）

### Diffスナップショット（要約）

```text
# 1. 変更目的 (必須)
一過性 429 が「収穫ゼロ」に化ける経路を断つ（F-11(1)）。常時赤のテストが次の本物の失敗を隠す状態を解消する。

# 2. 変更概要 (必須)
変更ファイル: src/openalex/client.py, tests/test_openalex_client_retry.py(新規), tests/test_git_collect.py, docs/field_observations_seihai.md, Changelog.md, DECISION_LOG.md
（リポジトリ外）seihai 日次 SKILL の停止注記3箇所・seihai docs/open-recommendations.md S-26 行。

# 3. 検証 (必須)
tests/test_openalex_client_retry.py 6ケース（429リトライ成功/5xx/上限/非対象4xx即時失敗/タイムアウト/retries=0の旧挙動）。
全体 314 tests: 314 pass。実機 bybridge raw 経路1回完走（診断値は F-07 処置後と同一）。
```

---

## 2026-08-21（CL-0085） bybridge F-07 処置: 重複シードの折り畳み＋1シード群あたりの bridge プール占有上限

### 概要
* スケジュールタスク `contra-failure-remediation` の2回目。`docs/field_observations_seihai.md` の **F-07**（同一 proceedings の重複レコード2件が bridge プール50枠を丸ごと占領し、多様性保証のラウンドロビン段が一度も走らない）を対処。F-01（7週連続・seihai 側で呼び出し停止）の**真の機序**。
* 処置前に同一テーマで実行し **F-07 を9週目として再現**（2シードが 50/50 本、残り18シードが 0 本）。
* `src/pipeline/collect.py` の `_bridge_pool_from_seeds` のみ変更。(1) 新規 `_seed_group_ids` で重複シードレコードを折り畳む（正規化DOI一致／正規化タイトル一致／**参考文献集合の Jaccard ≥ 0.9**）。(2) 1シード群あたりの占有上限 `cap // 4` を**共有 ref 階層にも**適用。(3) 上限は天井ではなく公平規則——他に出せるシードが無ければ backfill が従来どおりプールを満たす（単一シード入力の挙動は不変）。
* **実測 before/after**（F-02 の計器がそのまま出力）: 最頻 bridge の**上位10件占有率 100% → 0%** / 通行 bridge **6本 → 13本** / bridge 寄与のあるシード **2/20 → 8/20** / 主題に最も近いシード `AlphaAgent` の寄与 **0本 → 9本** / 重複 proceedings 群の占有 **50枠 → 9枠**。最頻 bridge の正体が「冠動脈疾患」(2,128) から **「Returns to Buying Winners and Selling Losers」(Jegadeesh & Titman・11,577)＝主題ドメインの文献**へ。
* **残件も記録**: 最頻 bridge が**全候補**に占める割合は 50% → 52% とほぼ不変で、候補の主題適合性もこの処置では改善が確認できていない。F-01 の残余として `docs/field_observations_seihai.md` に明記した。
* 併せて **F-11 を新規起票（未対処）**: OpenAlex を匿名プール・リトライ無しで叩いており、一過性の 429 が「収穫ゼロ」と区別できない。

### 関連タスク
* Task: contra 失敗対処デー（F-07＝F-01 の真因への処方。seihai 側 S-26 の停止解除は人間判断）

### Diffスナップショット（要約）

```text
# 1. 変更目的 (必須)
bybridge の bridge プールが「重複した名簿型 proceedings 2件」に占領される F-07 を断つ。F-01 として7週間記録されてきた症状の真因。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/collect.py, tests/test_collect_citation.py, docs/field_observations_seihai.md, DECISION_LOG.md, Changelog.md
_seed_group_ids(新規・重複レコード折り畳み) ＋ _bridge_pool_from_seeds に per-seed-group quota(cap//4) と backfill。呼び出し側・MCP シグネチャ・スコア・順位付けは非変更。

# 3. 検証 (必須)
tests/test_collect_citation.py に6ケース追加。全体 308 tests: 307 pass（既存不具合 test_lma_floor_never_lowers_a_fresh_score のみ失敗・本変更と無関係）。
実機 raw 経路を before/after 各1回（git stash で切替）実行し、F-02 の診断ブロックの数値で比較。
```

---

## 2026-08-18（CL-0084） bybridge 実行診断（F-02）: 使ったシードと通った bridge を出力に出す

### 概要
* スケジュールタスク `contra-failure-remediation` の初回実行。`docs/field_observations_seihai.md` の **F-02**（bybridge が使用シードを返さないため、失敗が「シード検索の失敗」か「bridge が汎用ハブに吸われた」か区別できない）を対処。
* 新規 `src/pipeline/bridge_diagnostics.py`：シード射影 / bridge 通行量 / 集中度メーター（純関数・API コスト 0）＋ 表示する bridge だけを **OpenAlex 1コール**で命名するフェイルソフトなラベル解決。
* `src/mcp_server.py` の `_execute_bybridge` に配線。既定 ON、`diagnostics:false` で従来の件数1行に戻る（加算的・可逆・シグネチャ非破壊）。交差候補ゼロの経路でもシードを出す。
* **初日に F-01 の診断を否定**：`bridge 寄与` 列が「20シード中18件が寄与0本、残る2件が50枠すべてを占有」と示し、真因が巨大ハブ吸着ではなく**重複 proceedings レコードによるプール占領**だと確定（新規 F-07 として起票）。中心性ペナルティは実装しなくて正解だった。

### 関連タスク
* Task: contra 失敗対処デー（F-02＝計器、F-01 の処方より先に入れる）

### Diffスナップショット（要約）

```text
# 1. 変更目的 (必須)
bybridge の失敗切り分けを可能にする。計器なしに処方を入れると「効いたか分からない」で終わるため、F-01 の処方より先に F-02 を入れる。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/bridge_diagnostics.py(新規), src/mcp_server.py, tests/test_bridge_diagnostics.py(新規), data/samples/theme_seihai_strategy_generation.json(新規・再現用固定テーマ), docs/field_observations_seihai.md, DECISION_LOG.md, Changelog.md
seed_rows / bridge_usage / bridge_concentration / resolve_work_labels / render_diagnostics ＋ MCP の diagnostics フラグ（既定 true）。

# 3. 確認方法 (必須)
新規 11 ケース＋全体 302 tests(301 pass / 1 は本変更前から失敗している既存不具合 test_git_collect.py::test_lma_floor_never_lowers_a_fresh_score)。
実機: 固定テーマで raw / structured / 交差候補ゼロ の3経路を実行し before/after を実測。
before=「収集診断: シード 20 件 / bridge プール 50 本 / 交差候補 60 件」の1行のみ。
after=シード20件全リスト（bridge 寄与つき）＋通行 bridge 5本（名前・被引用数）＋集中度（最頻 bridge が上位10件の100%・全体の50%）。
ランキングは不変（計器であって処方ではない）。
```

---

## 2026-06-15（CL-0083） ローカル化 段階(d): byrepo/Track A 委譲（委譲シリーズ a-d 完了）

### 概要
* Track A（byrepo）のキー無し構造組み立てを実装し、委譲シリーズ(a)〜(d)を完了。`build_track_a_entries` ＋ `assemble_keyless_track_a_document` ＋ MCP `byrepo` の `structured` フラグ。
* 設計要点: Track A は選別＝決定論の信頼性スコアのため再ゲート不要（Track B の delegate_finalize より単純）。

### 関連タスク
* Task: ローカル化（MCPクライアント委譲）段階(d) ＝シリーズ完了

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
byrepo/Track A をキー無しで一周できるようにし、委譲シリーズ(a-d)を完了する。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/delegate.py, src/mcp_server.py, tests/test_delegate.py, DECISION_LOG.md, task.md, diff.md, Changelog.md
build_track_a_entries（信頼性スコア降順）＋assemble_keyless_track_a_document（structured 整形）＋MCP byrepo structured フラグ。

# 3. 確認方法 (必須)
python3 -m pytest tests/ -q → 191 passed。import src.mcp_server OK。

# 4. 既知の課題・リスク (必須)
実エージェントによる採点ループの実運用手順化（roadmap #10 とセット）、agentmemory 統合は未着手。スコア設計値は不変。
```

---

## 2026-06-15（CL-0082） ローカル化 段階(c): エージェント採点 JSON スキーマ＋委譲経路

### 概要
* 呼び出し側エージェントの採点を受け取り `apply_post_gates` に流す委譲経路と JSON スキーマを実装。`finalize_delegated_document` ＋ MCP ツール `delegate_finalize`。
* エージェントがどう採点しても、anomaly/hollow 等の数値床は contra 側 post-gate が機械的に再適用。LLM・API キー不使用。

### 関連タスク
* Task: ローカル化（MCPクライアント委譲）段階(c)

### Diffスナップショット（要約）
> `diff.md`を上書きする直前の内容から、以下の要約項目をコピーします。

```text
# 1. 変更目的 (必須)
3段委譲フローの [3]（contra post-gate）を MCP 経由で完結させ、エージェント採点を受け取る JSON スキーマと委譲経路を定義する。

# 2. 変更概要 (必須)
変更ファイル: src/pipeline/delegate.py, src/mcp_server.py, tests/test_delegate.py, DECISION_LOG.md, task.md, diff.md, Changelog.md
候補素材＋採点の JSON 契約、work_from_material/normalize_agent_scores/finalize_delegated_document、MCP delegate_finalize ツールを追加。

# 3. 確認方法 (必須)
python3 -m pytest tests/ -q → 189 passed。import src.mcp_server OK。

# 4. 既知の課題・リスク (必須)
段階(d)（byrepo 委譲）は未着手。スコア設計値は不変。実エージェントによる採点ループの実運用手順化は roadmap #10 とあわせて。
```

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
