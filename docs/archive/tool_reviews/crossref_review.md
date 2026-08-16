# Crossref (crossref.org) 調査レポート（contra への活用可否）

> 一般論文サイト総覧 #2。OpenAlex 基準（[`openalex_review.md`](openalex_review.md)）と比較して評価。
> 調査手段: crossref.org REST API ドキュメント＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://www.crossref.org/> / API: <https://api.crossref.org/>

---

## 0. 結論（最重要）

**contra には冗長（追加不要）。OpenAlex が Crossref を取り込んだ上位互換だから。**
Crossref は DOI 登録機関で、**出版社が登録したメタデータ（~156–180M、2B+ 引用リンク、一部 abstract）**を
**無料・キー不要**（polite pool）で提供する。だが **OpenAlex はこの Crossref を主要な取り込み元**にしており、
さらに **概念/Topics 階層・OA リンク・統一引用**を上乗せしている。contra が Crossref を直接叩いても
**新しい母集団も距離信号も得られない**。

---

## 1. Crossref とは

- **正体**: DOI 登録エージェンシー。19,000+ 会員（出版社）が登録したメタデータの集約・配布。
- **API**: REST、**無料・サインアップ不要・キー不要**（email で polite pool）。メタデータは原則著作権対象外で再利用自由。
- **規模**: ~156–180M レコード、**2B+ 引用リンク**。funder/license/ORCID/ROR、**abstract（出版社が登録した分のみ）**。
- **レート**: 2025-12 改定（ヘッダで通知）。Metadata Plus（有料）で上限緩和。

---

## 2. contra への活用評価（OpenAlex 基準との差分）

| 観点 | Crossref | OpenAlex（基準） | contra への含意 |
|---|---|---|---|
| 立ち位置 | DOI 登録の**上流レジストリ** | Crossref 等を**集約**した下流カタログ | OpenAlex が Crossref を内包 |
| 母集団 | 156–180M | 250M+（Crossref＋他） | **OpenAlex が広い** |
| 概念/距離 | **なし** | Concepts/Topics 階層 | 距離は OpenAlex のみ |
| 引用 | 2B+ リンク | `referenced_works`（Crossref 等由来） | **重複**、OpenAlex で足りる |
| abstract | 出版社登録分のみ（plaintext） | inverted index（=同じ要旨を復元可） | **差は実質なし**（後述） |
| OA 全文リンク | license のみ（PDF 位置なし） | `oa_url` あり | 全文入口は OpenAlex |

**abstract の誤解を排す**: 「abstract が薄い」課題は *要旨が短い* のではなく *全文でない* こと。OpenAlex の
inverted index は要旨**全文**を復元できるため、Crossref の plaintext abstract に替えても**情報量は増えない**。
全文補強は引き続き provider 層（arXiv/CORE/IA Scholar）の役割で、Crossref は無関係。

### 2-2. 唯一の理論的差分（採用には至らない）
- **鮮度**: Crossref は登録の最上流ゆえ OpenAlex の取り込みラグより僅かに新しい場合がある。だが contra の
  「遠い構造類推」探索に分単位の鮮度は不要 → 採用理由にならない。
- **手法/記憶層**: 学ぶ要素なし（レジストリ）。

---

## 3. 結論の一言

Crossref は **OpenAlex のさらに上流**であり、contra から見れば **OpenAlex に完全に包含される**。
新しい母集団・距離・全文のいずれも供給しないため **不採用（OpenAlex 直叩きで足りる）**。
「Crossref を足すか？」への答えは「OpenAlex が既に Crossref を持っている」。

---

## 付記: 一次情報

- REST API（無料・キー不要・polite pool）: <https://www.crossref.org/documentation/retrieve-metadata/rest-api/>
- レート改定（2025-12）: <https://www.crossref.org/blog/announcing-changes-to-rest-api-rate-limits/>
