# Unpaywall (unpaywall.org) 調査レポート（contra への活用可否）

> 一般論文サイト総覧 #3。OpenAlex 基準（[`openalex_review.md`](openalex_review.md)）と比較して評価。
> provider 層（[`arxiv_review.md`](arxiv_review.md), [`core_review.md`](core_review.md)）で名前は既出。本稿で正式評価＋連鎖を訂正。
> 調査手段: api.unpaywall.org / OpenAlex blog ＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://unpaywall.org/> / API: `https://api.unpaywall.org/v2/{doi}?email=...`

---

## 0. 結論（最重要）

1. **OpenAlex `oa_url` に包含され、別ステップとしては冗長。**
   Unpaywall は **OpenAlex と同じ OurResearch が運営**し、**OpenAlex の OA 情報（`oa_url`/`oa_locations`）は
   Unpaywall 由来**。contra は OpenAlex から works を得るので、**OA 位置は既に手元にある**。Unpaywall を
   別途叩く必要はない。

2. **【訂正】provider 層の連鎖から Unpaywall を独立ステップとして外す。**
   以前「arXiv → **Unpaywall** → CORE → IA Scholar」と書いたが、**Unpaywall ≒ OpenAlex `oa_url`** なので重複。
   正しくは **「arXiv（クリーン全文）→ CORE / IA Scholar（OA 全文）→ OpenAlex `oa_url` の PDF を取得・抽出（汎用フォールバック）」**。
   Unpaywall の機能は **`oa_url` に畳み込まれている**。

3. **Unpaywall は"位置"であって"全文"ではない。** 返すのは OA コピーの URL。本文取得・抽出は別途必要で、
   その役は arXiv/CORE/IA Scholar（実体）と OpenAlex `oa_url`（汎用）が担う。

---

## 1. Unpaywall とは

- **正体**: 有料論文の**合法な無料コピー（OA 版）の所在**を解決する DB。50,000+ ソースを巡回、**30M+ 論文**。
- **運営**: 非営利 **OurResearch**（**OpenAlex / Unsub と同じ組織**）。OpenAlex と OA メタデータ形式が共通。
- **API**: **無料・キー不要**（email 必須）。`/v2/{doi}?email=...`。高速（~50ms）。
- **性質**: DOI → 最良 OA ロケーション（PDF URL 等）。**本文そのものは返さない**。

---

## 2. contra への活用評価（OpenAlex 基準との差分）

| 観点 | Unpaywall | OpenAlex（基準） | 含意 |
|---|---|---|---|
| 運営 | OurResearch | OurResearch（**同一**） | データ共通 |
| OA 位置 | best OA location | `oa_url`/`oa_locations`（**Unpaywall 由来**） | **重複** |
| 入力 | DOI 単位で解決 | works に OA 位置を内包 | contra は OpenAlex 経由で既に保持 |
| 本文 | なし（位置のみ） | なし（位置のみ） | 全文は provider（arXiv/CORE）が担う |

### 2-2. 唯一の独立利用ケース（contra では非該当）
- **裸の DOI しか無い**場合の OA 解決には有用。だが contra は OpenAlex works を起点にするため、**この状況は起きない**。
- 鮮度（最新の OA 化）を厳密に追う用途はありうるが、遠ドメイン探索には不要。

---

## 3. provider 層の確定形（本稿での訂正を反映）

```
全文補強の解決順:
  1) arXiv（arXiv-id があれば最優先：キー不要・LaTeX/PDF クリーン）
  2) CORE / IA Scholar（非 arXiv の OA 全文・実体）
  3) OpenAlex `oa_url` の PDF を取得・抽出（= Unpaywall 由来の汎用フォールバック）
発見・OA 位置の起点は OpenAlex（Unpaywall を内包）。違法経路は恒久不採用。
```

---

## 4. 結論の一言

Unpaywall は **OpenAlex `oa_url` に畳み込まれた OA ロケータ**で、contra では**別途叩かない（冗長）**。
本稿の価値は **provider 層の連鎖から Unpaywall を独立ステップとして外す訂正**にある。
全文の"実体"は arXiv/CORE/IA Scholar、"位置"は OpenAlex `oa_url` で完結する。

---

## 付記: 一次情報

- Unpaywall API（無料・email・キー不要）: <https://unpaywall.org/products/api>
- OurResearch が OpenAlex/Unpaywall/Unsub を運営・データ共通: OpenAlex blog（unpaywall カテゴリ）
