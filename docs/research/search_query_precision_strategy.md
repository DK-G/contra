# 情報収集クエリ精度の向上戦略（全経路の基盤 → bybridge / byserendipity）

> bynote 調査（NotebookLM Deep Research、77ソース、ノート `Contra Search Query Precision` `145af5df-c39f-45ea-8d1e-329a99995c65`、2026-06-23）。
> 事前調査: Consensus（`mcp__...__search`）と alphaXiv（arXiv `discover_papers`）の実走で、各エンジンの精度レバーを実測。
> 目的: contra の **論文検索クエリそのものの精度** を上げる。選別段（purpose_sim × mechanism_dist）・生成3部は過去 bynote で成熟済みだが、**収集クエリ**には専用調査が無かった。これを「全経路で再利用できる基盤レイヤ」として先に導入し、その上に bybridge / byserendipity の精度向上を載せる。

---

## 0. 結論（最重要）

contra の検索精度のボトルネックは **語彙でなく「クエリの構造化と接地」** にある。

1. **フィールド限定 ＞ 汎用全文**。現状の Track A / Track B は OpenAlex の汎用 `search=`（全文・stemming・shallow な語の共起）にキーワードを丸投げしている。OpenAlex 公式は「`search=` は語レベルの浅い一致しか取れず、`filter=`（Topic 等の内部分類）で正確に絞れ」と明言。さらに **`search=` は `filter=` の 10倍課金**（$1 vs $0.10/1000）。
2. **purpose_sim × mechanism_dist は正しいが、選別段にしか効いていない**。「near-purpose / far-mechanism」は cross-domain 類推検索の確立原理（Analogy Search Engine / ARCS）だが、contra はこれを**選別でしか使っていない**。**クエリ生成の時点**で適用すべき。
3. **LLM 自由生成クエリは byserendipity の使用域でこそ失敗する**。IR 研究が名指しする失敗域＝「未知（hallucinated entities）」「曖昧（popularity bias で人気解釈に収束）」は、byserendipity の遠ドメイン生成クエリの条件そのもの。処方は **エビデンス接地（HyDE / Query2doc）＋多面化（QA-Expand）＋実行前検証（round-trip / quality-gate fallback）**。

→ **Phase 1（基盤・全経路）** 共有クエリ精度レイヤ → **Phase 2** bybridge（引用ブリッジ）→ **Phase 3** byserendipity（類推クエリの接地・検証）の順で導入する。

---

## 1. Phase 1 — 共有クエリ精度レイヤ（contra 全体に転用）

全 collect 経路（Track A シード / Track B / bybridge シード / byrepo Git query）が呼ぶ**単一のクエリビルダ**を新設し、以下の原則を実装する。

### 1.1 フィールド限定検索を第一級にする（OpenAlex）

- **`filter=` を既定、`search=` は補助**。汎用全文は recall 用、precision は filter で取る。
- **Topic 階層フィルタ**（concepts は OpenAlex で非推奨化）: `Domain → Field → Subfield → Topic` の4階層。
  - 例: `filter=primary_topic.field.id:17`（Computer Science）。Field ID は固定（CS=17, Math=26, Physics&Astronomy=31, Psychology=32, Engineering=22, Materials=25, Neuroscience=28, Economics=20, Medicine=27 …）。
  - **名前で filter せず ID へ解決する**（"MIT"/"Smith" 等は曖昧）。テーマの近傍シードが持つ `primary_topic` から Field/Subfield ID を抽出して再利用できる（追加取得ゼロ）。
- **タイトル/アブストへの限定**: `filter=title_and_abstract.search:<terms>`（legacy だが現役。`.search.no_stem` で stemming 無効化＝厳密一致）。OpenAlex は将来的に top-level `search=` ＋ AI semantic search を推奨しているので、**長い入力（pseudo-abstract 等）には semantic search 経路**を使い分ける（Phase 3 で活用）。
- **boolean / 範囲**: filter 内で `,`=AND、`|`=OR（最大100値）、`!`=NOT。年は `publication_year:2018-2025` または `from_publication_date:`。
- **コスト副益**: filter 主体化で API クレジットが約 1/10。

### 1.2 「レキシカル錨 ＋ 意味的意図」の二層クエリ

裸キーワードの寄せ集めは弱い。alphaXiv の `keywords`（厳密一致の錨）＋`question`（意味的意図）が示す通り、**錨（正確な手法・術語）＋スコープ（Topic/Field filter）＋意図文**の三点を分離した**構造化クエリオブジェクト**を生成する。文字列でなく `{anchor_terms, field_ids, year_range, route: filter|search|semantic}` を返す。

### 1.3 拡張より再定式化

盲目的な query expansion は precision を下げうる（特に下記 Phase 3 の失敗域）。**フィールド制約での再定式化**を優先し、expansion は接地・検証付き（Phase 3）でのみ行う。

### 1.4 各エンジンの作法（使い分けの指針）

| エンジン | 機構 | 精度の出し方 | contra での役割 |
|---|---|---|---|
| **OpenAlex** | full-text(`search`) ＋ 構造化 `filter` ＋ AI semantic search | filter（Topic/year/type）主体、semantic は長文入力で | 主データ源（収集の本体） |
| **arXiv** | フィールド演算子 `ti:/abs:/cat:` ＋ boolean `AND/OR/ANDNOT` | `cat:` で分野限定＋`abs:` で術語限定 | CS/物理/数学の最新プレプリント補完 |
| **Consensus** | RAG（埋め込み合成、演算子なし） | 自然文で sub-domain を文に織り込む（❌"Biodiversity"→✅"Biodiversity of terrestrial plants in the southern hemisphere"）、Yes/No 方向性質問 | 査読済みの収斂確認・evidence 合成（収集でなく裏取り） |

---

## 2. Phase 2 — bybridge（引用ブリッジの精度）

### 2.1 現状の位置づけ（正しい）

bybridge の「シードの共有 referenced_works を経由」は **bibliographic coupling**（2文献が共通の第三文献を引用）そのもの。large-scale study では **coupling が research front の表現でやや優位**（co-citation ＞ direct citation）。現設計は妥当。

### 2.2 追加すべきもの

- **Document Co-Citation Analysis（DCA）＋ betweenness centrality**: cross-domain ブリッジには、シードと**一緒に引用される**文献（co-citation）が効く。DCA は分野横断で承認された "concept symbols"（手法・枠組み）を拾い、**betweenness centrality** で「分断された学術コミュニティを繋ぐ橋」文献を特定できる。bridge 候補の順位付けに coupling 数だけでなく centrality を加える。
- **PRF（擬似適合フィードバック）で bridge クエリを拡張**: 上位シードから salient な術語を Rocchio/RM3 流に抽出し、`cites:` 候補収集のクエリへ重み付き注入（ノイズ語は除外）。

### 2.3 限界の明示（Track B 併用の根拠）

古典的引用指標は **強い紐帯（formal citation）に最適化**され、引用リンクが疎なときの**弱い紐帯・framing shift・概念的橋**を取りこぼす。**だから bybridge 単独では弱い紐帯ブリッジに届かず、byserendipity（類推）との二刀流が正当**。bybridge は「引用で地続きの異分野」、byserendipity は「引用では繋がらないが構造で繋がる異分野」を担う。

---

## 3. Phase 3 — byserendipity（類推クエリの接地・検証）

### 3.1 中核の是正: purpose/mechanism をクエリ時にも適用

cross-domain 類推検索は keyword の "domain fixation"（自分野語彙への固着＝表層一致）を、**purpose（何のためか）と mechanism（どう動くか）への分解**で越える。原理は **"near in purpose, far in mechanism"**（purpose で近傍プールを取り、mechanism 次元で home domain を遠ざける）＝contra の `purpose_sim × mechanism_dist` と同一。**これを選別だけでなくクエリ生成に持ち込む。**

### 3.2 設計対立の解消: 「テーマ語排除」ではなく「標的化抽象」

現コード `generate_track_b_queries` は「テーマの surface keyword を**絶対に入れない**・抽象構造語だけ」へ振り切っている（ホーム引き戻しを嫌って）。だが類推検索研究は逆を戒める:

- **標的化抽象（Targeted Abstraction）**: 問題をドメイン中立な機能語へ再記述する（"reduce thermal conductivity in ceramic" → "prevent energy transfer across a boundary"）。
- **ただし構造的制約は残す**: 全部を抽象化すると analogy が遠すぎて実用不能（anomaly 化）。core relational structure に効く制約（"翼は semi-rigid で平ら" 等）は保持する。

→ 現状の「全抽象化」は**過抽象でノイズ源**になっている可能性が高い。**機能語への再記述＋構造制約の保持**へ修正する（テーマ語そのものは排除しつつ、構造を規定する語は残す、の中間）。

### 3.3 LLM 生成クエリの失敗を接地で潰す

IR 研究の名指しする失敗域＝byserendipity の使用域:
- **未知クエリ**: 背景知識不足を補おうと LLM が**存在しない実体/無関係語を hallucinate**。
- **曖昧クエリ**: **popularity bias** で人気解釈に偏り、有効な少数派解釈を除外＝coverage が縮む。

処方（いずれも notebook ソースで効果実測あり）:
- **HyDE / Query2doc（pseudo-document 接地）**: 裸キーワードでなく、「その遠ドメインにありそうな仮想アブストラクト」を LLM 生成し、**その埋め込みで OpenAlex semantic search**（短query→長doc の意味ギャップを埋める）。Query2doc は BM25 を +3〜15%。
- **QA-Expand（多面化）**: 単一の狭いクエリでなく、**複数の異なる facet 質問**（複数の遠ドメイン）へ分解してから検索＝popularity-bias の収束を防ぐ（既存の「5ドメイン生成」を facet 設計として強化）。最大 +13%。
- **PRF（HyDE 文書への BM25 feedback）**: 生成文から術語を選別・重み付け（noisy/common 語を除去）。naive concat より +4〜6%。

### 3.4 実行前検証レイヤ（欠けている本丸）

生成クエリを**実行前に検証**して、ハルシネーション/過抽象のクエリを捨てる。contra は既に `_clean_query`（x/×除去）程度しか持たない。

- **Round-trip / on-target filtering**: 生成クエリは「自分の根拠文書を top-N で再取得できる」場合のみ採用。lexical 一致＋concept レベル類似の二段で、語ズレによる過剰棄却を防ぐ。
- **非空・構造一致チェック**: 各生成クエリを実行し、0件 or home-domain 収束したものは破棄。
- **judge 省略/書換え**: pseudo-document を judge LLM に通し、無関係/曖昧は空にしてから合成。
- **Quality gate（Corrective RAG）**: 拡張が閾値を割ったら、**ベースライン検索（Phase 1 の filter 主体クエリ）へフォールバック**して悪い素材を下流に流さない。

---

## 4. 実装フェーズへのマッピング（コードアンカー）

### Phase 1（基盤・先行）
- 新規 `src/pipeline/query.py`: `StructuredQuery` データクラス（anchor_terms / field_ids / subfield_ids / year_range / route）＋ `to_openalex_params()`（filter 主体に描画）＋ Topic ID 解決ヘルパ（近傍シードの `primary_topic` から ID 抽出）。
- `src/pipeline/collect.py`: `_query_from_theme` / `_query_variants` を新ビルダ呼び出しへ置換。`{"search": q}` 一辺倒をやめ filter 経路を既定化（汎用 search は fallback）。
- `src/openalex/client.py`: 改修不要（任意 params を通す）。任意で semantic search エンドポイント／topic 解決を薄く追加。
- 既存テストの収集系を「filter 経路でも候補が取れる」へ拡張。

### Phase 2（bybridge）
- `collect_citation_candidates` 系: co-citation 収集（シードと共に引用される works）＋ betweenness centrality による bridge 順位付けを追加。bridge クエリに PRF 術語注入。
- coupling 数のみの順位付けに centrality 項を加える（既存の「共有 bridge 本数」注記は保持）。

### Phase 3（byserendipity）
- `generate_track_b_queries`: ①標的化抽象プロンプト（機能語へ再記述＋構造制約保持）②QA-Expand 風の facet 分解 ③HyDE pseudo-abstract オプション ④**実行前検証**（非空/home収束/round-trip でフィルタ、全滅時は Phase 1 ベースラインへフォールバック）。
- 選別段（`classify.py` の purpose_sim × mechanism_dist）は**不変**（クエリ側で近purpose/遠mechanismを先取りするだけ。スコア設計値 0.20/0.50/0.35 等は据え置き、`spec.md` 禁則順守）。

> **実装済み (2026-06-23)** — 新規 `src/pipeline/serendipity_query.py`（標的化抽象＋遠 facet＋HyDE 仮想アブスト生成 `generate_serendipity_facets`、相補的結合 `build_semantic_query`、検証 `validate_semantic_results`/`home_field_fraction`/`exclude_home_field`）＋ `query.py` の `route="semantic"` 配線＋ `collect.py` の `collect_track_b` 主経路化（語彙 fallback）。**★`search.semantic` は実在する埋め込み/ANN エンドポイントと実機確認**（§3.3「OpenAlex semantic search」は仮説でなく実体・上位50件固定・`primary_topic.field.id:!` 否定と非合成のためホーム除外はクライアント側）。round-trip は contra に単一根拠文書が無いため**「非空＋ホーム収束チェック」へ適応**（concept 類似は選別段の責務として重複させない）。実機 A/B で語彙より構造的精度が上＝net-positive（詳細は `DECISION_LOG.md`）。

---

## 5. トレードオフ / 可逆性

- **可逆性高**: Phase 1 はクエリ構築層の差し替え（client/選別/スコア設計値は不変）。Phase 3 はプロンプト＋検証フィルタの追加で、選別ロジックに触れない。
- **コスト**: filter 主体化で OpenAlex クレジットは減。Phase 3 の HyDE/QA-Expand は LLM 呼び出し増（委譲経路ならエージェント側推論で吸収）。検証で 0件クエリを早期棄却するので無駄な収集 round は減る。
- **リスク**: 標的化抽象の「構造制約を残す」さじ加減は経験調整が要る（過抽象/過具体の両端を避ける）。検証レイヤの round-trip 閾値も校正対象。いずれも段階導入＋テストで詰める。

---

## 6. 主要ソース（ノート `145af5df` 内）

- **OpenAlex Developers**: Search / Filter / Fields Overview / Keys & Concepts / Works（`search` vs `filter`、10x コスト、Topic 階層、boolean、`title_and_abstract.search`、semantic search）。
- **arXiv API**（field prefixes・boolean・sort）、**Semantic Scholar / Consensus** 公式（RAG・自然文クエリ作法・Quick/Pro/Deep）。
- **Query2doc**（pseudo-document、BM25 +3〜15%）、**HyDE / Revisiting BM25 Feedback with HyDE**（PRF on 生成文）、**QA-Expand**（facet 多面化 +13%）、**LLM-based Query Expansion Fails for Unfamiliar and Ambiguous Queries**（失敗域＝未知/曖昧、popularity bias）。
- **Bibliographic coupling / Co-citation / Document Co-Citation Analysis**（coupling≳co-citation≫direct、DCA＋betweenness で cross-domain ブリッジ、強紐帯偏重の限界）。
- **Accelerating Innovation Through Analogy Mining / Analogy Search Engine / ARCS（Analog Retrieval by Constraint Satisfaction）**（purpose/mechanism 分解、near-purpose/far-mechanism、標的化抽象と構造制約保持）。

ノートは `nlm notebook query 145af5df-c39f-45ea-8d1e-329a99995c65 "<question>"` で再利用可能。
