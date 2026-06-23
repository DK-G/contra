# DBLP (dblp.org) 調査レポート（contra への活用可否）

> 一般論文サイト総覧 #9。OpenAlex 基準＋ arXiv（[`arxiv_review.md`](arxiv_review.md)）と比較。CS 専門書誌。
> 調査手段: dblp.org / blog.dblp.org ＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://dblp.org/> / dump: DROPS（XML/RDF, CC0）

---

## 0. 結論（最重要）

**不採用。abstract/全文を持たず構造マッチングに使えない。CS の精度は arXiv が担う。**
DBLP は **8M+ の CS 文献**を 32 年間キュレートした高品質書誌（無料・キー不要・CC0、XML/RDF dump）だが、
**abstract も全文も（ほぼ）引用も無いメタデータ専門索引**。contra の中核（Purpose/Mechanism の構造照合）は
要旨/全文を要するため、**DBLP 単独では判定材料が無い**。CS のドメイン精度は **arXiv（cs.*・全文）**＋ OpenAlex で足りる。

---

## 1. DBLP とは

- **正体**: 計算機科学の書誌データベース（32 年・キュレート・品質チェック）。
- **規模**: 8M+ CS 文献（全 CS サブ分野）。
- **アクセス**: query API ＋ 月次 XML/RDF dump（DROPS）。**無料・キー不要・CC0**。
- **内容**: タイトル・著者・会議/誌・年・DOI。**abstract / 全文なし。引用も基本なし**。**著者名寄せ（person ID）が高品質**。

---

## 2. contra への活用評価（OpenAlex / arXiv 基準との差分）

| 観点 | DBLP | OpenAlex / arXiv | 含意 |
|---|---|---|---|
| abstract/全文 | **なし** | OpenAlex 要旨 / arXiv 全文 | **構造照合に使えない**（致命的） |
| CS 発見 | CS のみ・メタのみ | OpenAlex(全分野)+arXiv(cs 全文) | 上位互換が既存 |
| 著者名寄せ | **高品質（強み）** | OpenAlex authorships | contra は**著者軸を避ける**（近傍シグナル, ResearchRabbit 参照）→ 強みが効かない |
| 引用/距離 | なし | OpenAlex 引用/concepts | 寄与なし |

- DBLP の**唯一の強み＝著者曖昧性解消**は、contra が**意図的に避ける共著/著者軸**（マイオピア要因）に属し、活かす場面がない。

---

## 3. 結論の一言

DBLP は **CS 書誌の金字塔だが、abstract/全文が無く contra の構造照合には不適**。
強みの著者名寄せも contra の設計（著者軸を避ける）と噛み合わない。**CS 精度は arXiv、発見は OpenAlex** で足り、
**DBLP は不採用**。

---

## 付記: 一次情報

- DBLP（8M+ CS 文献・CC0・XML/RDF dump）: <https://dblp.org/> / <https://blog.dblp.org/>
