# scite (scite.ai) 調査レポート（contra への活用可否）

> 本ドキュメントは、Smart Citations を提供する scite を調査し、contra への活用可否を判定した記録。
> Semantic Scholar の引用インテントと比較し、bybridge / 出力「注意点」フィールドへの効きを評価する。
> 調査手段: scite.ai / API ドキュメント＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://scite.ai/>（商用 SaaS / 有料 API）
> 関連: [`semantic_scholar_review.md`](semantic_scholar_review.md)（引用インテント）, [`consensus_review.md`](consensus_review.md)

---

## 0. 結論（最重要）

1. **検索先にはならない（商用・ライセンス全文・有料 API）。** scite は出版社との indexing 契約で得た
   **280M 全文記事**から **1.6B+ の引用ステートメント**を分類。API はあるが**有料**（Personal $20/月）で、
   contra の「stdlib・コスト最小・キー最小」方針と衝突。

2. **scite の "支持/反論/言及" は、bybridge には S2 引用インテントの方が適切。**
   scite は引用の**態度**（supporting / contrasting / mentioning）を測る。一方 contra の bybridge が欲しいのは
   「共有参照が**構造的(methods/results)な bridge** か」で、これは **S2 の intent（background/methods/results、無料）**
   が直接答える。**bridge 品質には S2 が上位**。

3. **scite 固有の価値は1点: 「反論引用」→ 出力『注意点』フィールドの裏づけ。**
   contra の4部構成の最後「注意点」は、提示した遠ドメイン論文の**留保**を述べる枠。scite の
   **contrasting 引用＋信頼性タリー**は「この知見は文献上で**反論・係争されている**」を示せる ＝ 注意点の honesty 強化。
   ただし **contrasting は全体の 0.8% と希少**で信号が薄く、かつ有料 API ゲート。**actionable 優先度は低**。

---

## 1. scite とは

- **正体**: スマート引用インデックス（商用）。引用を文脈つきで提示し、深層学習で態度分類。
- **Smart Citations**: 各引用を **supporting / contrasting / mentioning**＋確信度で分類。
  分布は概ね **mentioning 92.6% / supporting 6.5% / contrasting 0.8%**。
- **コーパス**: 280M 全文記事 → 1.6B+ 引用ステートメント（出版社契約＋OA）。
- **機能**: 信頼性ダッシュボード（論文ごとの支持/反論タリー）、reference check、検索、assistant。
- **API/価格**: 全機能 API あり。Personal $20/月、Plus $12/月（年額）。Institutional はカスタム。

---

## 2. contra への活用評価

### 2-1. 発見コーパス
- **❌ 不要**。商用・ライセンス全文・有料 API。母集団は OpenAlex で足り、引用の質は S2 で補える。

### 2-2. 手法 / インフラ層

**scite 態度分類 vs S2 引用インテント（用途の違い）**

| | scite（態度） | S2（intent） | contra での適所 |
|---|---|---|---|
| 何を測るか | 引用が**支持/反論/言及** | 引用が**背景/手法/結果**のため | — |
| bybridge の bridge 品質 | △（態度は構造性を示さない） | ◎（methods/results=構造的 bridge） | **S2 が上位・無料** |
| 出力「注意点」 | ◎（contrasting=係争の明示） | △ | **scite が固有・ただし有料/希少** |
| コスト | 有料 $20/月 | 無料（キー要） | S2 優位 |

**(A) bybridge … S2 で足りる（scite 不要）。** 構造的 bridge の選別は intent で行うのが筋。
**(B) 出力「注意点」… scite が唯一固有だが優先度低。** 「反論引用あり」を caution に添えるのは honesty 上は良いが、
  contrasting が 0.8% と希少で、有料 API ゲート。**当面は見送り**、将来 caution を強化する際の選択肢として記録。

### 2-3. ポジショニング
scite は Consensus と同じ**証拠評価（収束）**系だが、**反論(dissent)を可視化**する点はわずかに contrarian 寄り。
ただし機構は「**ドメイン内の主張に対する賛否**」であり、contra の核「**遠ドメインの構造類推**」とは層が違う。混同しない。

---

## 3. 結論の一言

scite は **bybridge には S2（無料・intent）が上位**で不要、**唯一固有なのは「反論引用 → 出力『注意点』の裏づけ」**だが、
**希少信号＋有料 API ゲート**で優先度は低い。「caution フィールドを将来強化するなら検討する選択肢」として記録に留める。

---

## 付記: 一次情報

- Smart Citations（supporting/contrasting/mentioning・分布・手法）: QSS (MIT Press) "scite: A smart citation index"
- コーパス（1.6B+ 引用ステートメント / 280M 全文）: <https://scite.ai/data-and-services>
- API: <https://api.scite.ai/docs>
