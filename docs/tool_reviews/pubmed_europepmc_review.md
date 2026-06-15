# PubMed / Europe PMC 調査レポート（contra への活用可否）

> 一般論文サイト総覧 #4。OpenAlex 基準（[`openalex_review.md`](openalex_review.md)）＋ arXiv（[`arxiv_review.md`](arxiv_review.md)）と
> 比較して評価。生物医学版の「ドメイン専門インデックス」として固有価値があるか。
> 調査手段: NLM E-utilities / Europe PMC REST ＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://pubmed.ncbi.nlm.nih.gov/> / <https://europepmc.org/> / API: E-utilities, Europe PMC REST

---

## 0. 結論（最重要）

1. **生物医学版の arXiv＝加算候補 ⭕（OpenAlex を補完する精度＋全文の専門源）。**
   発見の広さは OpenAlex が MEDLINE を内包済みで足りるが、PubMed/Europe PMC は OpenAlex に無い
   **(a) MeSH（精緻な生物医学概念階層）/ (b) OA 全文（9M+）/ (c) プレプリント統合 / (d) テキストマイニング注釈**
   を持つ。arXiv（STEM 精度）と同じ位置づけで、**生物医学テーマの精度・全文を厚くする副次源**。

2. **入口は Europe PMC REST に一本化するのが良い。** Europe PMC は **PubMed＋PMC 全文＋31 プレプリントサーバ
   （bioRxiv/medRxiv 含む）＋注釈**を1つの REST API で提供。生 E-utilities より扱いやすい。
   → これにより総覧 #8（bioRxiv/medRxiv）は**Europe PMC に概ね包含**される。

3. **一般則の確認**: 「OpenAlex＝広さ／ドメイン専門インデックス＝精度・全文」。arXiv=STEM、Europe PMC=生物医学、
   という**ドメイン専門源を OpenAlex の上に重ねる**設計が、recall×precision 両立の筋（README 示唆 #9）。

---

## 1. PubMed / PMC / Europe PMC とは

| サービス | 中身 | API |
|---|---|---|
| **PubMed** | 36M+ 生物医学引用（MEDLINE 等）。**MeSH** 統制語彙で索引、abstract あり | **E-utilities**（無料、3 req/s／キーで 10/s） |
| **PMC** | OA 全文アーカイブ。2.8M+ が **BioC XML/JSON** でテキストマイニング可 | bulk / API |
| **Europe PMC** | 42M+ abstract、**9M+ 全文**、**31 サーバのプレプリント**（650k+、53k 全文）、**2B+ 注釈** | **REST**（無料）＋ Annotations API |

---

## 2. contra への活用評価（OpenAlex / arXiv 基準との差分）

### 2-1. 発見コーパス
- **△ 広さは不要（OpenAlex が MEDLINE 内包）**。ただし arXiv と同様、**機構が明示的＋MeSH 索引**で
  **構造一致の精度が高い** → 生物医学テーマでは**副次的検索対象**として価値（README 示唆 #9 の精度軸）。

### 2-2. 手法 / インフラ層 ← 加算候補

**(A) MeSH = 生物医学のクリーンな距離信号 … ★★**
- MeSH は専門家がキュレートした概念階層。OpenAlex Topics（全分野・自動）より**生物医学内では精緻**。
  `concept_distance` の生物医学ケースで距離・近傍判定を補強できる（arXiv カテゴリと同じ役）。生物医学限定が制約。

**(B) Europe PMC OA 全文 = provider 層に追加 … ★★★**
- 9M+ 全文・2.8M+ がテキストマイニング可。**生物医学 OA 論文の全文補強 provider** として provider 層に入る
  （arXiv→CORE/IA Scholar と並ぶ生物医学版）。byserendipity/bybridge の mechanism 判定を厚くする。

**(C) プレプリント統合 = bioRxiv/medRxiv の入口 … ★★**
- Europe PMC が 31 プレプリントサーバを統合 → **#8 bioRxiv/medRxiv を個別に叩かず Europe PMC で賄える**。

**(D) テキストマイニング注釈（遺伝子/疾患/生物/関係）… ★（限定）**
- 2B+ の entity/relation 注釈。生物医学論文の Purpose/Mechanism 抽出の補助になりうるが、entity 特化で
  contra の抽象的構造マッチングへの寄与は限定的。記録に留める。

### 2-3. ポジショニング
arXiv の双子（ドメイン専門の精度＋全文）。OpenAlex（広さ）を主役に、**STEM=arXiv / 生物医学=Europe PMC** を
重ねる二段構え。Europe PMC は REST 一本で全文・プレプリント・注釈・（PubMed 経由で）MeSH に届く点が実装上優れる。

---

## 3. フロー別まとめ

| フロー | MeSH 距離(A) | 全文 provider(B) | プレプリント(C) |
|---|---|---|---|
| byserendipity | ★★（生物医学の距離精度） | ★★★（全文補強） | ★★ |
| bybridge | ★（判定補強） | ★★（判定補強） | ★ |
| byrepo / bynote | — | — | — |

---

## 4. 制約整合・推奨

- **stdlib のみ**: Europe PMC REST / E-utilities は HTTP+JSON/XML。キーは任意（レート緩和のみ）。新規 pip 依存なし。
- **ドメイン限定**: 生物医学のみ。OpenAlex（広さ）を主役に据えた上での精度・全文の副次源（arXiv と同じ扱い）。
- **推奨アクション**:
  1. **provider 層に Europe PMC（OA 全文）を追加**: 生物医学 OA 論文の全文補強。差し替え可能 provider IF に組み込む。
  2. **生物医学テーマで Europe PMC を副次検索対象に**（MeSH 距離つき）。引用は OpenAlex/S2 と分担。
  3. **#8 は Europe PMC で代替**: bioRxiv/medRxiv はプレプリント統合経由で取得。

---

## 5. 結論の一言

PubMed/Europe PMC は **arXiv の生物医学版＝加算候補**。OpenAlex の広さに、**MeSH の距離精度・OA 全文・
プレプリント統合**を生物医学ドメインで上乗せする。入口は **Europe PMC REST に一本化**するのが実装上最適で、
これで bioRxiv/medRxiv（#8）も概ね賄える。

---

## 付記: 一次情報

- E-utilities（無料・3/s・キーで 10/s・MeSH）: <https://www.nlm.nih.gov/dataguide/eutilities/utilities.html>
- Europe PMC REST（42M abstract / 9M 全文 / プレプリント / 注釈）: <https://europepmc.org/RestfulWebService>
- Europe PMC in 2023（規模・機能）: <https://academic.oup.com/nar/article/52/D1/D1668/7442539>
