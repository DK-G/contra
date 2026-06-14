# tool_reviews — 提案ツール/サイトの見解レポート集

> このフォルダは、外部ツール・サイト・サービスを「contra に活用できるか」という観点で評価した
> 調査レポートを集約する場所。**会話スコープの作業ディレクトリ**であり、検討が一段落したら
> 中身を `docs/research/` へ昇格させるか、フォルダごと処分してよい。

## 進め方（このフォルダの運用ルール）

1. ユーザーが調査対象（ツール / サイト / API）を提案する。
2. 対象を調査し、**contra への活用可否の見解**を作成する。
3. 1対象 = 1 Markdown として本フォルダに格納し、コミットする。

判定の共通枠組み（過去レポートで確立）: 各対象を
- **発見コーパス（検索の走らせ先）** … クエリできる新しい母集団になるか
- **手法（technique）** … 収集/判定の作り方として真似る価値があるか
- **記憶層（memory）** … 出力を蓄積し横断検索できる永続層に効くか

の3用途で評価する。制約（stdlib のみ・`models.py`/スコア設計は不変更）との整合も必ず確認する。

## レポート一覧

| 対象 | レポート | 一言結論 |
|---|---|---|
| OKF / Google `knowledge-catalog` | [`okf_knowledge_catalog_review.md`](okf_knowledge_catalog_review.md) | 公開コーパスではない。効くのは Web Pass（手法）と OKF バンドル化（記憶層） |
| Internet Archive (archive.org) | [`internet_archive_review.md`](internet_archive_review.md) | 発見コーパスは弱。Wayback が byrepo Web Pass のリンク切れを埋める（堅牢化層） |
| Elicit (elicit.com) | [`elicit_review.md`](elicit_review.md) | 製品は contra の対極（収束型）。実利は基盤の Semantic Scholar = SPECTER2 埋め込み（初の有力な追加コーパス／距離軸強化） |
| Consensus (consensus.app) | [`consensus_review.md`](consensus_review.md) | 名前ごと contra の対極（合意=収束）。OpenAlex 再販で検索先にならず。価値は同一性の対照例 |
| Connected Papers (connectedpapers.com) | [`connected_papers_review.md`](connected_papers_review.md) | bybridge と同系統手法（bibliographic coupling）を収束方向に回した双子。妥当性裏づけ＋co-citation拡張＋可視化設計図 |
| Semantic Scholar (semanticscholar.org) | [`semantic_scholar_review.md`](semantic_scholar_review.md) | OpenAlexは据え置きつつ加算する3レイヤー（SPECTER2/推薦/引用インテント）。引用インテントが bybridge の偽bridge除去を原理化 |
| SciSpace (scispace.com) | [`scispace_review.md`](scispace_review.md) | 収束型SaaS 3例目。固有価値は「遠い論文を門外漢へ翻訳」=生成段(関連性/仮説)の語り口の手本 |
| Phind (phind.com) | [`phind_review.md`](phind_review.md) | 開発者版の収束ツール。唯一その収束マインドが Track A(byrepo)と整合。Web Pass の到達点(docs/issues/SOで制約・失敗パターン) |
| Anna's Archive (annas-archive.org) | [`annas_archive_review.md`](annas_archive_review.md) | **採用不可**: 著作権侵害シャドウライブラリ($322M判決/差止)。全文は合法OA(CORE/Unpaywall/IA Scholar)で代替 |
| Google Scholar (scholar.google.com) | [`google_scholar_review.md`](google_scholar_review.md) | **採用不可**: 公式APIなし・ToS禁止・CAPTCHA。広いが触れない。OpenAlex+S2+COREで代替（他Googleツール経由もScholarデータは不可） |
| Papernity (papernity.com) | [`papernity_review.md`](papernity_review.md) | **不採用**: 論文代筆SaaS。目的が代筆で逆、かつAI検出回避を訴求(整合性赤信号)。学ぶものなし |
| ResearchRabbit (researchrabbit.ai) | [`researchrabbit_review.md`](researchrabbit_review.md) | 検索先にならず。価値は4接続タイプ(引用/結合/共著/意味類似)でcontraを座標化。共著=避ける近傍軸、結合/類似は遠さへ反転 |
| Litmaps (litmaps.com) | [`litmaps_review.md`](litmaps_review.md) | 可視化系3例目。唯一の新軸=モニタリング(継続発見)→履歴/M3を土台にした"contra watchモード"の着想。時系列軸は軽い可視化改良 |
| scite (scite.ai) | [`scite_review.md`](scite_review.md) | 支持/反論/言及の態度分類。bybridgeはS2 intent(無料)が上位で不要。固有は「反論引用→出力『注意点』」だが希少+有料で優先度低 |
| CORE (core.ac.uk) | [`core_review.md`](core_review.md) | **採用候補**: 合法・無料・最大のOA全文層(API v3)。「abstractが薄い」課題をbyserendipity/bybridgeで全文補強。Anna's Archiveの合法本命 |
| arXiv (arxiv.org) | [`arxiv_review.md`](arxiv_review.md) | **採用候補(2役)**: ①byserendipityの副次検索対象(STEM=機構可読で構造一致の精度↑) ②全文provider層の筆頭(キー不要+LaTeXクリーン)。OpenAlex=広さ/arXiv=深さ精度。引用エッジ非提供のみ制約(bybridgeはOpenAlex/S2と分担)、構造的欠陥なし |

## 横断的な示唆（8件調査後の総括）

### 1. 「収束 vs 発散」でツールは2群に割れる
調査した SaaS（Elicit / Consensus / SciSpace / Phind）はすべて**収束型**＝関連性・要約・合意・的確な答え。
contra の中核 **Track B は発散**（遠ドメイン構造類推）なので、これらは**思想的に対極**であり、
価値は主に「**contra が何でないか**を映す鏡」。例外は **Phind**：その収束は **Track A（byrepo＝接地）と整合**する。
→ 設計指針: **フロー別に収束/発散の思想を分ける**（Track A は precision、Track B は distance）。

### 2. 「新しい検索先（母集団）」はほぼ出ない
OpenAlex を置き換える公開コーパスは現れず。唯一の加算候補が **Semantic Scholar (S2AG)**。ただし母集団は
OpenAlex 据え置きで、S2 は**3つの加算レイヤー**として効く: SPECTER2 埋め込み（ドメイン距離軸）/
Recommendations（候補拡張）/ **引用インテント（bybridge の偽 bridge 除去を原理化）**。

### 3. 実装の合流点は3つに収束した
- **byrepo Web Pass**（README → docs / GitHub issues / Stack Overflow を出典つき合成）:
  OKF=手法、Phind=到達点の手本と source set、archive.org(Wayback)=リンク切れ復旧。**最有力の最初の一手**。
- **Semantic Scholar 加算レイヤー**: SPECTER2 で `concept_distance` 補強、引用インテントで bybridge 精緻化。
- **OKF バンドル化 = 自前メモリ層 ＋ Connected Papers 流の可視化**: `history.py` 一般化＋Save Page Now で
  citation 恒久化、ノード色=ドメイン距離に意味反転したグラフ提示。

### 4. 制約は一貫してクリア
すべて stdlib・キー不要 or 環境変数化・出力フォーマット/スコア設計不変更の範囲で実現可能。
Track B の `select_track_b` 構造判定にだけは外部シグナル（埋め込み類似・合意・収束）を**混ぜない**こと。

---

## 横断的な示唆（リスト #1–11 バッチ後の追補）

### 5. 篩の結果: 採用候補は「合法・無料・API 整備のインフラ」だけ
このバッチ7件（重複4件は除外）の判定:
- **棄却（reject）**: Anna's Archive（著作権侵害）/ Google Scholar（API なし・ToS 禁止）/ Papernity（代筆・検出回避）。
- **収集には不要（鏡/可視化）**: ResearchRabbit / Litmaps / scite — いずれも S2 上の SaaS で公開 API 弱く、
  価値は contra の座標化（4接続タイプ）や個別アイデアに留まる。
- **採用候補 ⭕**: **CORE (core.ac.uk)** — 合法・無料・最大の OA 全文層。前バッチの **Semantic Scholar** と並ぶ
  "素材として加算価値"のある対象。

### 6. 「全文補強」が確たる実装スレッドに昇格
byserendipity/bybridge の「**abstract が薄く mechanism 判定が弱い**」課題に対し、複数レポートが同じ解に収束:
**arXiv（arXiv-id 最優先・キー不要・LaTeX クリーン）→ Unpaywall → CORE → IA Scholar の順で OA 全文を解決する
差し替え可能な provider 層**（発見は OpenAlex 据え置き）。違法経路（Anna's Archive）は恒久不採用。
→ **byrepo Web Pass と並ぶ、第2の有力な最初の一手**。**arXiv は導入摩擦が最小で provider 層の着手点**。

### 7. 新しい設計アイデア（核ではないが記録）
- **watch / monitor モード**（Litmaps）: テーマ定期再実行＋履歴 diff で新着 bridge を surface（優先度中）。
- **「注意点」フィールドの係争裏づけ**（scite）: contrasting 引用で caution を強化（希少+有料、優先度低）。
- **4接続タイプでの自己定位**（ResearchRabbit）: 結合/類似は遠さへ反転、共著=避ける、引用=使う。

### 8. 一貫した構図
収集の母集団は **OpenAlex を主役に据え置き**、加算価値は **Semantic Scholar（埋め込み/推薦/引用インテント）＋
CORE/arXiv（OA 全文）＋ arXiv（STEM の副次検索対象）** に集約。残りは「contra が何でないか（収束 vs 発散）」を映す鏡。
実装合流点は **①byrepo Web Pass ②OA 全文 provider 層 ③S2 加算レイヤー ④OKF メモリ＋可視化**。

### 9. 検索対象は「広さ × 精度」の2軸で考える（arXiv 再評価より）
ソースを「広さ(recall)＝遠ドメイン射程」だけで測ると誤る。**機構の可読性（mechanism legibility）が高い分野
（arXiv の STEM）は、構造一致の判定精度(precision)が高く偽 bridge を弾きやすい**ため、ジャンル限定でも
良質な検索対象になりうる。**OpenAlex=広さ / arXiv=深さ・精度**の併用が指針。今後ソースを評価する際は
recall だけでなく **「機構がどれだけ明示的に書かれる分野か」** を質の軸として加える。
